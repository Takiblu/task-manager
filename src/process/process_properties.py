"""
Detailed single-process inspection for the "Properties" dialog:
executable path, full command line, working directory, environment,
and open files — each individually guarded since any of these can
raise AccessDenied for processes we don't own.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import psutil

from src.utils.logger import get_logger
from src.utils.safe_exec import InvalidPidError, validate_pid

logger = get_logger("process.process_properties")


@dataclass
class ProcessProperties:
    pid: int
    ppid: int
    name: str
    username: str
    exe: str | None
    cmdline: list[str]
    cwd: str | None
    cpu_percent: float
    memory_rss_bytes: int
    memory_vms_bytes: int
    num_threads: int
    nice: int
    status: str
    create_time: float
    environment: dict[str, str] | None = None
    open_files: list[str] = field(default_factory=list)
    environment_available: bool = False
    open_files_available: bool = False


def get_process_properties(pid: object) -> ProcessProperties | None:
    try:
        valid_pid = validate_pid(pid)
    except InvalidPidError as exc:
        logger.info("Cannot read properties, invalid PID: %s", exc)
        return None

    try:
        proc = psutil.Process(valid_pid)
        with proc.oneshot():
            name = proc.name()
            username = _safe(proc.username, "?")
            ppid = _safe(proc.ppid, 0)
            cpu_percent = _safe(proc.cpu_percent, 0.0)
            mem_info = _safe(proc.memory_info, None)
            num_threads = _safe(proc.num_threads, 0)
            nice = _safe(proc.nice, 0)
            status = _safe(proc.status, "unknown")
            create_time = _safe(proc.create_time, 0.0)
            exe = _safe(proc.exe, None)
            cmdline = _safe(proc.cmdline, [])
            cwd = _safe(proc.cwd, None)

        environment: dict[str, str] | None = None
        environment_available = False
        try:
            environment = proc.environ()
            environment_available = True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            environment_available = False

        open_files: list[str] = []
        open_files_available = False
        try:
            open_files = [f.path for f in proc.open_files()]
            open_files_available = True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            open_files_available = False

        return ProcessProperties(
            pid=valid_pid,
            ppid=ppid,
            name=name,
            username=username,
            exe=exe,
            cmdline=cmdline or [],
            cwd=cwd,
            cpu_percent=cpu_percent,
            memory_rss_bytes=mem_info.rss if mem_info else 0,
            memory_vms_bytes=mem_info.vms if mem_info else 0,
            num_threads=num_threads,
            nice=nice,
            status=str(status),
            create_time=create_time,
            environment=environment,
            open_files=open_files,
            environment_available=environment_available,
            open_files_available=open_files_available,
        )
    except psutil.NoSuchProcess:
        logger.info("Process %s vanished while reading properties", valid_pid)
        return None
    except psutil.AccessDenied:
        logger.info("Access denied reading properties of PID %s", valid_pid)
        return None


def _safe(getter, default):
    try:
        return getter()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return default
