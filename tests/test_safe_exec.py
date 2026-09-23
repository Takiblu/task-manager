"""Tests for src.utils.safe_exec — the PID validation / injection-safety choke point."""

from __future__ import annotations

import os

import pytest

from src.utils.safe_exec import InvalidPidError, run_argv, validate_pid


class TestValidatePid:
    def test_accepts_current_process_pid(self) -> None:
        current_pid = os.getpid()
        assert validate_pid(current_pid) == current_pid

    def test_accepts_numeric_string(self) -> None:
        current_pid = os.getpid()
        assert validate_pid(str(current_pid)) == current_pid

    def test_rejects_non_numeric_string(self) -> None:
        with pytest.raises(InvalidPidError):
            validate_pid("not-a-pid; rm -rf /")

    def test_rejects_negative_pid(self) -> None:
        with pytest.raises(InvalidPidError):
            validate_pid(-5)

    def test_rejects_zero_pid(self) -> None:
        with pytest.raises(InvalidPidError):
            validate_pid(0)

    def test_rejects_nonexistent_pid(self) -> None:
        # PID 2**22 is astronomically unlikely to exist on any real system.
        with pytest.raises(InvalidPidError):
            validate_pid(2**22)

    def test_rejects_none(self) -> None:
        with pytest.raises(InvalidPidError):
            validate_pid(None)

    def test_rejects_float_pid_object(self) -> None:
        # Accepting "1234.0" style floats silently could let a caller
        # pass unsanitized JSON numbers straight through; keep this strict.
        with pytest.raises(InvalidPidError):
            validate_pid(object())


class TestRunArgv:
    def test_runs_simple_command(self) -> None:
        result = run_argv(["true"])
        assert result.success is True
        assert result.returncode == 0

    def test_reports_nonzero_exit(self) -> None:
        result = run_argv(["false"])
        assert result.success is False
        assert result.returncode != 0

    def test_missing_binary_does_not_raise(self) -> None:
        result = run_argv(["this-binary-does-not-exist-xyz"])
        assert result.success is False
        assert result.returncode == 127

    def test_refuses_shell_string(self) -> None:
        with pytest.raises(TypeError):
            run_argv("echo hello; rm -rf /")  # type: ignore[arg-type]

    def test_captures_stdout(self) -> None:
        result = run_argv(["echo", "hello world"])
        assert "hello world" in result.stdout
