"""
Security-critical helpers shared by process/, services/, and
permissions/. Centralizing this logic means every privileged or
PID-based operation in the app goes through the same validated path.

Rules enforced here (see project security requirements):
  * Never build shell strings from user input (no os.system()).
  * Every subprocess call uses an argv list, never shell=True.
  * PIDs are validated as real integers referring to a process that
    actually exists before any signal is sent (closes the read/kill
    TOCTOU race as much as userspace can).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence

import psutil

from src.utils.logger import get_logger

logger = get_logger("utils.safe_exec")


class InvalidPidError(ValueError):
    """Raised when a PID is not a valid, currently-running process."""


@dataclass(frozen=True)
class CommandResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str


def validate_pid(pid: object) -> int:
    """
    Validate that `pid` is a positive integer corresponding to a
    process that exists right now. Returns the int PID on success.

    Raises InvalidPidError otherwise. This is the single choke point
    every "act on a PID" code path must pass through before calling
    psutil.Process(pid) or sending a signal.
    """
    try:
        pid_int = int(pid)  # rejects non-numeric strings, floats-as-str, etc.
    except (TypeError, ValueError) as exc:
        raise InvalidPidError(f"PID is not an integer: {pid!r}") from exc

    if pid_int <= 0:
        raise InvalidPidError(f"PID must be positive: {pid_int}")

    if not psutil.pid_exists(pid_int):
        raise InvalidPidError(f"No such process: {pid_int}")

    return pid_int


def run_argv(
    argv: Sequence[str],
    timeout: float = 5.0,
    check: bool = False,
) -> CommandResult:
    """
    Run a command safely as an argv list (never a shell string).

    This is the ONLY place in the codebase that should call
    subprocess.run directly for privileged/system commands
    (systemctl, pkexec, loginctl, etc.) — every caller in
    services/, process/, permissions/ routes through here so
    behavior (timeouts, logging, error shape) stays consistent.
    """
    if isinstance(argv, str):
        # Defensive: this function must never be handed a raw shell
        # string. Refuse outright rather than silently shell-splitting
        # it, which could reintroduce injection risk from callers.
        raise TypeError("run_argv() requires a list of arguments, not a string")

    argv = list(argv)
    logger.debug("Executing: %s", argv)

    try:
        completed = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        logger.warning("Command not found: %s (%s)", argv[0] if argv else "?", exc)
        return CommandResult(success=False, returncode=127, stdout="", stderr=str(exc))
    except subprocess.TimeoutExpired as exc:
        logger.warning("Command timed out: %s", argv)
        return CommandResult(success=False, returncode=-1, stdout="", stderr=str(exc))
    except OSError as exc:
        logger.error("OS error running command %s: %s", argv, exc)
        return CommandResult(success=False, returncode=-1, stdout="", stderr=str(exc))

    result = CommandResult(
        success=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )

    if check and not result.success:
        logger.warning(
            "Command failed (%s): %s | stderr=%s",
            result.returncode, argv, result.stderr.strip(),
        )

    return result
