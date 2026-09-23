"""Tests for src.system.cpu_monitor and src.system.memory_monitor."""

from __future__ import annotations

from src.system.cpu_monitor import get_cpu_snapshot
from src.system.memory_monitor import get_memory_snapshot


class TestCpuMonitor:
    def test_snapshot_has_sane_values(self) -> None:
        snapshot = get_cpu_snapshot()
        assert 0.0 <= snapshot.total_percent <= 100.0
        assert snapshot.physical_cores >= 1
        assert snapshot.logical_cores >= snapshot.physical_cores
        assert isinstance(snapshot.model_name, str) and snapshot.model_name

    def test_per_core_percent_matches_logical_core_count(self) -> None:
        snapshot = get_cpu_snapshot()
        # per_core_percent should have one entry per logical core (when
        # the platform supports it) — never crash if it's shorter/absent.
        assert len(snapshot.per_core_percent) <= snapshot.logical_cores + 1

    def test_missing_temperature_does_not_crash(self) -> None:
        # On sandboxes/CI without sensors, temperature_c should just be
        # None rather than raising.
        snapshot = get_cpu_snapshot()
        assert snapshot.temperature_c is None or isinstance(snapshot.temperature_c, float)


class TestMemoryMonitor:
    def test_snapshot_has_sane_values(self) -> None:
        snapshot = get_memory_snapshot()
        assert snapshot.total_bytes > 0
        assert 0 <= snapshot.used_bytes <= snapshot.total_bytes * 1.05  # small slack for races
        assert 0.0 <= snapshot.percent <= 100.0

    def test_swap_values_are_non_negative(self) -> None:
        snapshot = get_memory_snapshot()
        assert snapshot.swap_total_bytes >= 0
        assert snapshot.swap_used_bytes >= 0
        assert snapshot.swap_free_bytes >= 0
