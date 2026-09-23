"""Tests for src.process.process_model.list_processes."""

from __future__ import annotations

import os

from src.process.process_model import list_processes


class TestListProcesses:
    def test_returns_nonempty_list(self) -> None:
        processes = list_processes(include_system=True, include_kernel_threads=False)
        assert len(processes) > 0

    def test_includes_own_process(self) -> None:
        own_pid = os.getpid()
        processes = list_processes(include_system=True, include_kernel_threads=False)
        assert any(p.pid == own_pid for p in processes)

    def test_excluding_system_processes_reduces_or_equal_count(self) -> None:
        with_system = list_processes(include_system=True, include_kernel_threads=False)
        without_system = list_processes(include_system=False, include_kernel_threads=False)
        assert len(without_system) <= len(with_system)

    def test_every_process_has_required_fields(self) -> None:
        processes = list_processes()
        assert processes
        sample = processes[0]
        assert sample.pid > 0
        assert isinstance(sample.name, str)
        assert isinstance(sample.username, str)
        assert sample.cpu_percent >= 0.0
        assert sample.memory_percent >= 0.0

    def test_never_raises_even_under_repeated_calls(self) -> None:
        # Repeated rapid calls simulate the polling worker; processes will
        # come and go between calls, and this must never raise.
        for _ in range(5):
            list_processes()
