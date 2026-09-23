"""
Aggregates identity + hardware info for the Overview and System pages
in one call. This module does NOT do continuous polling itself — see
core/monitor_worker.py for the background polling loop; this module
is for on-demand / low-frequency snapshots (e.g. the System page,
which doesn't need sub-second refresh).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import psutil

from src.system.cpu_monitor import CpuSnapshot, get_cpu_snapshot
from src.system.disk_monitor import DiskPartition, get_partitions
from src.system.gpu_monitor import GpuSnapshot, get_gpu_snapshots
from src.system.memory_monitor import MemorySnapshot, get_memory_snapshot
from src.utils.platform_info import SystemIdentity, get_system_identity


@dataclass
class FullSystemSnapshot:
    identity: SystemIdentity
    cpu: CpuSnapshot
    memory: MemorySnapshot
    gpus: list[GpuSnapshot]
    partitions: list[DiskPartition]
    uptime_seconds: float


def get_uptime_seconds() -> float:
    try:
        return max(0.0, time.time() - psutil.boot_time())
    except OSError:
        return 0.0


def format_duration(total_seconds: float) -> str:
    """Format seconds into a human string like '2d 04:35:12'."""
    total_seconds = int(max(0, total_seconds))
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_full_system_snapshot() -> FullSystemSnapshot:
    """Collect a one-shot snapshot of everything the System page shows."""
    return FullSystemSnapshot(
        identity=get_system_identity(),
        cpu=get_cpu_snapshot(),
        memory=get_memory_snapshot(),
        gpus=get_gpu_snapshots(),
        partitions=get_partitions(),
        uptime_seconds=get_uptime_seconds(),
    )
