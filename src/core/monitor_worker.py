"""
Background polling: a QThread-based worker that periodically gathers
CPU/Memory/GPU/Disk/Network/Process snapshots and emits Qt signals
with the results. This is the ONLY place in the app that should call
the system/ and process/ readers on a timer — keeping it off the UI
thread is what makes "don't let the Task Manager itself eat CPU"
(section 27) actually achievable, since psutil calls, /proc reads,
and process_iter() all block.

The UI subscribes to `snapshot_ready` and updates widgets in-place
(never rebuilding tables from scratch) to satisfy the "live update
without losing selection/scroll" requirement (section 28) — that
part lives in ui/pages/processes_page.py, this worker just supplies
data at a steady cadence.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal, Slot

from src.process.process_model import ProcessInfo, list_processes
from src.settings.app_settings import AppSettings
from src.system.cpu_monitor import CpuSnapshot, get_cpu_snapshot
from src.system.disk_monitor import DiskIoRate, DiskIoTracker, DiskPartition, get_partitions
from src.system.gpu_monitor import GpuSnapshot, get_gpu_snapshots
from src.system.memory_monitor import MemorySnapshot, get_memory_snapshot
from src.system.network_monitor import NetworkInterfaceSnapshot, NetworkIoTracker
from src.utils.logger import get_logger

logger = get_logger("core.monitor_worker")


@dataclass
class MonitorSnapshot:
    cpu: CpuSnapshot
    memory: MemorySnapshot
    gpus: list[GpuSnapshot]
    disk_partitions: list[DiskPartition]
    disk_io: DiskIoRate
    network: dict[str, NetworkInterfaceSnapshot]
    processes: list[ProcessInfo]


class MonitorWorker(QObject):
    """
    Lives on its own QThread. `start_polling()` is invoked once the
    thread has started (connected to QThread.started), and the loop
    self-schedules via a QTimer that lives on this object's thread
    affinity — never a raw time.sleep() loop, so Qt's event loop
    (and thus thread quit/shutdown) stays responsive.
    """

    snapshot_ready = Signal(object)  # emits MonitorSnapshot
    error_occurred = Signal(str)

    def __init__(self, settings: AppSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._disk_tracker: DiskIoTracker | None = None
        self._net_tracker: NetworkIoTracker | None = None
        self._timer = None  # created lazily on the worker thread
        self._include_system_processes = settings.show_system_processes
        self._include_kernel_threads = settings.show_kernel_threads

    def update_filters(self, include_system: bool, include_kernel_threads: bool) -> None:
        self._include_system_processes = include_system
        self._include_kernel_threads = include_kernel_threads

    def update_interval(self, interval_ms: int) -> None:
        if self._timer is not None:
            self._timer.setInterval(max(200, interval_ms))

    @Slot()
    def start_polling(self) -> None:
        # Imported and constructed here (not __init__) so tracker
        # state is primed on the worker thread, not the caller's.
        from PySide6.QtCore import QTimer

        self._disk_tracker = DiskIoTracker()
        self._net_tracker = NetworkIoTracker()

        self._timer = QTimer()
        self._timer.setInterval(max(200, self._settings.update_interval_ms))
        self._timer.timeout.connect(self._poll_once)
        self._timer.start()
        logger.debug("Monitor worker polling started at %sms", self._settings.update_interval_ms)

    @Slot()
    def stop_polling(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _poll_once(self) -> None:
        try:
            snapshot = MonitorSnapshot(
                cpu=get_cpu_snapshot(),
                memory=get_memory_snapshot(),
                gpus=get_gpu_snapshots(),
                disk_partitions=get_partitions(),
                disk_io=self._disk_tracker.sample() if self._disk_tracker else DiskIoRate(0, 0),
                network=self._net_tracker.sample() if self._net_tracker else {},
                processes=list_processes(
                    include_system=self._include_system_processes,
                    include_kernel_threads=self._include_kernel_threads,
                ),
            )
            self.snapshot_ready.emit(snapshot)
        except Exception as exc:  # noqa: BLE001 - a poll tick must never kill the timer
            logger.exception("Polling cycle failed")
            self.error_occurred.emit(str(exc))


def build_monitor_thread(settings: AppSettings) -> tuple[QThread, MonitorWorker]:
    """
    Construct the worker + its dedicated thread and wire the standard
    lifecycle signals. Caller owns starting/stopping the thread
    (typically from MainWindow.__init__ / closeEvent).
    """
    thread = QThread()
    worker = MonitorWorker(settings)
    worker.moveToThread(thread)
    thread.started.connect(worker.start_polling)
    return thread, worker
