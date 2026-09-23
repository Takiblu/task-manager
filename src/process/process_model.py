"""
Process listing: builds ProcessInfo records from psutil, tolerating
processes that vanish mid-read (NoSuchProcess) or that we can't fully
inspect (AccessDenied) without ever crashing the poll cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import psutil

from src.utils.logger import get_logger

logger = get_logger("process.process_model")


class ProcessStatus(str, Enum):
    RUNNING = "running"
    SLEEPING = "sleeping"
    DISK_SLEEP = "disk-sleep"
    STOPPED = "stopped"
    TRACING_STOP = "tracing-stop"
    ZOMBIE = "zombie"
    DEAD = "dead"
    WAKE_KILL = "wake-kill"
    WAKING = "waking"
    IDLE = "idle"
    LOCKED = "locked"
    WAITING = "waiting"
    UNKNOWN = "unknown"

    @classmethod
    def from_psutil(cls, raw: str) -> "ProcessStatus":
        try:
            return cls(raw)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    name: str
    username: str
    cpu_percent: float
    memory_percent: float
    memory_rss_bytes: int
    num_threads: int
    nice: int
    status: ProcessStatus
    create_time: float
    cmdline: list[str] = field(default_factory=list)
    exe: str = ""
    is_system_process: bool = False
    is_kernel_thread: bool = False

    @property
    def display_command(self) -> str:
        return " ".join(self.cmdline) if self.cmdline else self.name


_PROCESS_FIELDS = (
    "pid", "ppid", "name", "username", "cpu_percent", "memory_percent",
    "memory_info", "num_threads", "nice", "status", "create_time",
    "cmdline", "exe",
)

# Heuristic: kernel threads on Linux have exe == "" and are usually
# wrapped in square brackets by ps/top; psutil exposes name() as the
# bracketed form too (e.g. "[kworker/0:1]").
def _looks_like_kernel_thread(name: str, exe: str) -> bool:
    return not exe and name.startswith("[") and name.endswith("]")


# Processes below UID 1000 (system/service accounts) are treated as
# "system processes" for the show_system_processes filter. This is a
# heuristic, not a security boundary.
_SYSTEM_UID_THRESHOLD = 1000


def list_processes(
    include_system: bool = True,
    include_kernel_threads: bool = False,
) -> list[ProcessInfo]:
    """
    Return a snapshot of all currently visible processes. Each process
    read is wrapped individually so one vanished/inaccessible process
    never aborts the whole listing.
    """
    results: list[ProcessInfo] = []

    for proc in psutil.process_iter(attrs=_PROCESS_FIELDS):
        try:
            info = proc.info
            name = info.get("name") or ""
            exe = info.get("exe") or ""
            is_kernel_thread = _looks_like_kernel_thread(name, exe)

            if is_kernel_thread and not include_kernel_threads:
                continue

            try:
                uid = proc.uids().real
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                uid = _SYSTEM_UID_THRESHOLD  # assume non-system if unreadable

            is_system = uid < _SYSTEM_UID_THRESHOLD
            if is_system and not include_system:
                continue

            mem_info = info.get("memory_info")
            rss = mem_info.rss if mem_info else 0

            results.append(
                ProcessInfo(
                    pid=info["pid"],
                    ppid=info.get("ppid") or 0,
                    name=name or f"pid-{info['pid']}",
                    username=info.get("username") or "?",
                    cpu_percent=info.get("cpu_percent") or 0.0,
                    memory_percent=info.get("memory_percent") or 0.0,
                    memory_rss_bytes=rss,
                    num_threads=info.get("num_threads") or 0,
                    nice=info.get("nice") or 0,
                    status=ProcessStatus.from_psutil(info.get("status") or "unknown"),
                    create_time=info.get("create_time") or 0.0,
                    cmdline=info.get("cmdline") or [],
                    exe=exe,
                    is_system_process=is_system,
                    is_kernel_thread=is_kernel_thread,
                )
            )
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            # Process exited between iter() and info read — skip silently.
            continue
        except psutil.AccessDenied:
            # We can still list it with what limited info we have.
            try:
                results.append(
                    ProcessInfo(
                        pid=proc.pid,
                        ppid=0,
                        name=proc.name() if _safe_name(proc) else f"pid-{proc.pid}",
                        username="?",
                        cpu_percent=0.0,
                        memory_percent=0.0,
                        memory_rss_bytes=0,
                        num_threads=0,
                        nice=0,
                        status=ProcessStatus.UNKNOWN,
                        create_time=0.0,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Skipping inaccessible process %s: %s", proc.pid, exc)
                continue

    return results


def _safe_name(proc: psutil.Process) -> bool:
    try:
        proc.name()
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
