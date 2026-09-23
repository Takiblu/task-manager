"""
Network monitoring: per-interface throughput (delta-based, like disk
I/O) plus link status and IP addresses via psutil.net_if_addrs()/
net_if_stats().
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass

import psutil

from src.utils.logger import get_logger

logger = get_logger("system.network_monitor")


@dataclass
class NetworkInterfaceSnapshot:
    name: str
    ip_address: str | None
    is_up: bool
    download_bytes_per_sec: float
    upload_bytes_per_sec: float
    total_received_bytes: int
    total_sent_bytes: int


class NetworkIoTracker:
    """Stateful per-interface throughput tracker (see DiskIoTracker)."""

    def __init__(self) -> None:
        self._last_counters: dict[str, tuple[int, int]] = {}
        self._last_timestamp: float | None = None
        self._prime()

    def _prime(self) -> None:
        try:
            per_nic = psutil.net_io_counters(pernic=True)
            for name, counters in per_nic.items():
                self._last_counters[name] = (counters.bytes_recv, counters.bytes_sent)
        except OSError as exc:
            logger.debug("net_io_counters unavailable at startup: %s", exc)
        self._last_timestamp = time.monotonic()

    def sample(self) -> dict[str, NetworkInterfaceSnapshot]:
        now = time.monotonic()
        elapsed = max(now - (self._last_timestamp or now), 1e-6)

        try:
            per_nic_io = psutil.net_io_counters(pernic=True)
        except OSError:
            per_nic_io = {}

        try:
            per_nic_addrs = psutil.net_if_addrs()
        except OSError:
            per_nic_addrs = {}

        try:
            per_nic_stats = psutil.net_if_stats()
        except OSError:
            per_nic_stats = {}

        results: dict[str, NetworkInterfaceSnapshot] = {}

        for name, counters in per_nic_io.items():
            prev_recv, prev_sent = self._last_counters.get(name, (counters.bytes_recv, counters.bytes_sent))
            download_rate = max(0.0, (counters.bytes_recv - prev_recv) / elapsed)
            upload_rate = max(0.0, (counters.bytes_sent - prev_sent) / elapsed)

            ip_address = None
            for addr in per_nic_addrs.get(name, []):
                if addr.family == socket.AF_INET:
                    ip_address = addr.address
                    break

            is_up = False
            stats = per_nic_stats.get(name)
            if stats is not None:
                is_up = stats.isup

            results[name] = NetworkInterfaceSnapshot(
                name=name,
                ip_address=ip_address,
                is_up=is_up,
                download_bytes_per_sec=download_rate,
                upload_bytes_per_sec=upload_rate,
                total_received_bytes=counters.bytes_recv,
                total_sent_bytes=counters.bytes_sent,
            )
            self._last_counters[name] = (counters.bytes_recv, counters.bytes_sent)

        self._last_timestamp = now
        return results
