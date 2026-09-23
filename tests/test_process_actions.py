"""
Tests for src.process.process_actions.

Uses real short-lived child processes (spawned via subprocess) rather
than mocking psutil everywhere, so these tests exercise the actual
signal-sending code paths end to end.
"""

from __future__ import annotations

import subprocess
import time

import psutil
import pytest

from src.process import process_actions
from src.process.process_actions import ActionOutcome


@pytest.fixture
def sleeper_process():
    """Spawn a short-lived `sleep` child process and clean it up after the test."""
    proc = subprocess.Popen(["sleep", "30"])
    time.sleep(0.1)  # let it actually start
    yield proc
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=2)


class TestEndTask:
    def test_end_task_terminates_process(self, sleeper_process) -> None:
        result = process_actions.end_task(sleeper_process.pid)
        assert result.outcome == ActionOutcome.SUCCESS
        assert process_actions.wait_for_exit(sleeper_process.pid, timeout_seconds=3.0) is True

    def test_end_task_on_invalid_pid(self) -> None:
        result = process_actions.end_task("not-a-pid")
        assert result.outcome == ActionOutcome.INVALID_PID

    def test_end_task_on_nonexistent_pid(self) -> None:
        result = process_actions.end_task(2**22)
        assert result.outcome == ActionOutcome.INVALID_PID

    def test_end_task_on_already_exited_process(self, sleeper_process) -> None:
        pid = sleeper_process.pid
        sleeper_process.kill()
        sleeper_process.wait(timeout=2)
        # give the OS a moment to actually reap/mark it gone
        time.sleep(0.2)
        result = process_actions.end_task(pid)
        assert result.outcome in (ActionOutcome.INVALID_PID, ActionOutcome.ALREADY_GONE)


class TestForceKill:
    def test_force_kill_terminates_process(self, sleeper_process) -> None:
        result = process_actions.force_kill(sleeper_process.pid)
        assert result.outcome == ActionOutcome.SUCCESS
        sleeper_process.wait(timeout=3)
        assert not psutil.pid_exists(sleeper_process.pid)


class TestSuspendResume:
    def test_suspend_then_resume(self, sleeper_process) -> None:
        suspend_result = process_actions.suspend(sleeper_process.pid)
        assert suspend_result.outcome == ActionOutcome.SUCCESS

        proc = psutil.Process(sleeper_process.pid)
        # Give the kernel a moment to reflect the stopped state.
        time.sleep(0.1)
        assert proc.status() == psutil.STATUS_STOPPED

        resume_result = process_actions.resume(sleeper_process.pid)
        assert resume_result.outcome == ActionOutcome.SUCCESS


class TestProcessTree:
    def test_get_process_tree_pids_includes_root(self, sleeper_process) -> None:
        pids = process_actions.get_process_tree_pids(sleeper_process.pid)
        assert sleeper_process.pid in pids

    def test_get_process_tree_pids_for_invalid_pid_returns_empty(self) -> None:
        assert process_actions.get_process_tree_pids(2**22) == []

    def test_end_process_tree_terminates_root(self, sleeper_process) -> None:
        results = process_actions.end_process_tree(sleeper_process.pid, force=True)
        assert len(results) >= 1
        assert all(r.outcome in (ActionOutcome.SUCCESS, ActionOutcome.ALREADY_GONE) for r in results)
        sleeper_process.wait(timeout=3)


class TestIsRunning:
    def test_is_running_true_for_live_process(self, sleeper_process) -> None:
        assert process_actions.is_running(sleeper_process.pid) is True

    def test_is_running_false_for_invalid_input(self) -> None:
        assert process_actions.is_running("nonsense") is False
        assert process_actions.is_running(None) is False
