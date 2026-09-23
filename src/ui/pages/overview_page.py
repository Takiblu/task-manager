"""
Overview page: the landing summary with CPU/Memory/GPU/Disk/Network
cards, all updated in-place from MonitorSnapshot signals (no widget
rebuilding on tick).
"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from src.core.monitor_worker import MonitorSnapshot
from src.system.system_info import format_duration, get_uptime_seconds
from src.ui.widgets.metric_card import MetricCard


def _format_bytes(num_bytes: float) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < step:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} PB"


def _format_rate(bytes_per_sec: float) -> str:
    bits_per_sec = bytes_per_sec * 8
    step = 1000.0
    for unit in ("bps", "Kbps", "Mbps", "Gbps"):
        if abs(bits_per_sec) < step:
            return f"{bits_per_sec:.1f} {unit}"
        bits_per_sec /= step
    return f"{bits_per_sec:.1f} Tbps"


class OverviewPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        heading = QLabel("Overview")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        root_layout.addWidget(heading)

        self._uptime_label = QLabel("Uptime: --")
        self._uptime_label.setStyleSheet("color: #9aa4a9;")
        root_layout.addWidget(self._uptime_label)

        grid = QGridLayout()
        grid.setSpacing(16)
        root_layout.addLayout(grid)

        self.cpu_card = MetricCard("CPU")
        self.memory_card = MetricCard("Memory")
        self.gpu_card = MetricCard("GPU")
        self.disk_card = MetricCard("Disk")
        self.network_card = MetricCard("Network")

        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.memory_card, 0, 1)
        grid.addWidget(self.gpu_card, 0, 2)
        grid.addWidget(self.disk_card, 1, 0)
        grid.addWidget(self.network_card, 1, 1)

        root_layout.addStretch(1)

    def update_snapshot(self, snapshot: MonitorSnapshot) -> None:
        cpu = snapshot.cpu
        self.cpu_card.set_value(f"{cpu.total_percent:.0f}%")
        self.cpu_card.set_progress(cpu.total_percent)
        freq_text = f"{cpu.current_freq_mhz / 1000:.1f} GHz" if cpu.current_freq_mhz else "-- GHz"
        self.cpu_card.set_subtext(
            f"{cpu.physical_cores} Cores / {cpu.logical_cores} Threads  •  {freq_text}"
        )

        mem = snapshot.memory
        self.memory_card.set_value(f"{_format_bytes(mem.used_bytes)} / {_format_bytes(mem.total_bytes)}")
        self.memory_card.set_progress(mem.percent)
        self.memory_card.set_subtext(f"{mem.percent:.0f}% used  •  Swap {mem.swap_percent:.0f}%")

        if snapshot.gpus:
            gpu = snapshot.gpus[0]
            usage_text = f"{gpu.usage_percent:.0f}%" if gpu.usage_percent is not None else "N/A"
            self.gpu_card.set_value(usage_text)
            self.gpu_card.set_progress(gpu.usage_percent)
            vram_text = (
                f"{gpu.vram_used_mb / 1024:.1f} GB VRAM"
                if gpu.vram_used_mb is not None else gpu.name
            )
            self.gpu_card.set_subtext(vram_text)
        else:
            self.gpu_card.set_value("N/A")
            self.gpu_card.set_progress(None)
            self.gpu_card.set_subtext("No supported GPU detected")

        io = snapshot.disk_io
        self.disk_card.set_value(f"R {_format_bytes(io.read_bytes_per_sec)}/s")
        self.disk_card.set_progress(None)
        self.disk_card.set_subtext(f"W {_format_bytes(io.write_bytes_per_sec)}/s")

        total_down = sum(nic.download_bytes_per_sec for nic in snapshot.network.values())
        total_up = sum(nic.upload_bytes_per_sec for nic in snapshot.network.values())
        self.network_card.set_value(f"↓ {_format_rate(total_down)}")
        self.network_card.set_progress(None)
        self.network_card.set_subtext(f"↑ {_format_rate(total_up)}")

        self._uptime_label.setText(f"Uptime: {format_duration(get_uptime_seconds())}")
