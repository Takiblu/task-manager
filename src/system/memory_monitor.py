"""Memory (RAM + swap) monitoring."""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass
class MemorySnapshot:
    total_bytes: int
    used_bytes: int
    available_bytes: int
    cached_bytes: int
    buffers_bytes: int
    percent: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_free_bytes: int
    swap_percent: float


def get_memory_snapshot() -> MemorySnapshot:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return MemorySnapshot(
        total_bytes=vm.total,
        used_bytes=vm.used,
        available_bytes=vm.available,
        # Not all platforms expose `cached`/`buffers` (only Linux does
        # via psutil); default to 0 rather than raising AttributeError.
        cached_bytes=getattr(vm, "cached", 0),
        buffers_bytes=getattr(vm, "buffers", 0),
        percent=vm.percent,
        swap_total_bytes=swap.total,
        swap_used_bytes=swap.used,
        swap_free_bytes=swap.free,
        swap_percent=swap.percent,
    )
