"""
Disk monitoring: per-partition usage plus system-wide read/write
throughput computed as a delta between two psutil.disk_io_counters()
samples (bytes/sec).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import psutil

from src.utils.logger import get_logger

logger = get_logger("system.disk_monitor")


@dataclass
class DiskPartition:
    device: str
    mount_point: str
    filesystem: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


@dataclass
class DiskIoRate:
    read_bytes_per_sec: float
    write_bytes_per_sec: float


class DiskIoTracker:
    """
    Stateful tracker that computes read/write throughput between
    successive calls to `sample()`. One instance should live for the
    lifetime of the polling worker so the delta stays meaningful.
    """

    def __init__(self) -> None:
        self._last_read_bytes = 0
        self._last_write_bytes = 0
        self._last_timestamp: float | None = None
        self._prime()

    def _prime(self) -> None:
        try:
            counters = psutil.disk_io_counters()
            if counters:
                self._last_read_bytes = counters.read_bytes
                self._last_write_bytes = counters.write_bytes
        except OSError as exc:
            logger.debug("disk_io_counters unavailable at startup: %s", exc)
        self._last_timestamp = time.monotonic()

    def sample(self) -> DiskIoRate:
        now = time.monotonic()
        try:
            counters = psutil.disk_io_counters()
        except OSError:
            counters = None

        if counters is None or self._last_timestamp is None:
            self._last_timestamp = now
            return DiskIoRate(0.0, 0.0)

        elapsed = max(now - self._last_timestamp, 1e-6)
        read_rate = max(0.0, (counters.read_bytes - self._last_read_bytes) / elapsed)
        write_rate = max(0.0, (counters.write_bytes - self._last_write_bytes) / elapsed)

        self._last_read_bytes = counters.read_bytes
        self._last_write_bytes = counters.write_bytes
        self._last_timestamp = now

        return DiskIoRate(read_bytes_per_sec=read_rate, write_bytes_per_sec=write_rate)


def get_partitions() -> list[DiskPartition]:
    """
    List real, mounted filesystems (skips pseudo filesystems like
    proc/sysfs/tmpfs-for-runtime by relying on psutil's default
    `all=False`, which already excludes most virtual mounts).
    """
    partitions: list[DiskPartition] = []
    try:
        entries = psutil.disk_partitions(all=False)
    except OSError as exc:
        logger.warning("Failed to list disk partitions: %s", exc)
        return partitions

    for entry in entries:
        try:
            usage = psutil.disk_usage(entry.mountpoint)
        except (PermissionError, FileNotFoundError, OSError) as exc:
            logger.debug("Skipping partition %s: %s", entry.mountpoint, exc)
            continue

        partitions.append(
            DiskPartition(
                device=entry.device,
                mount_point=entry.mountpoint,
                filesystem=entry.fstype,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent=usage.percent,
            )
        )
    return partitions
