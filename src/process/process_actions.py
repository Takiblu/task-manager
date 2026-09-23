"""
Process lifecycle actions: End Task (SIGTERM with a graceful-wait
fallback to Force Kill), direct Force Kill (SIGKILL), Suspend/Resume,
and priority (nice) changes.

Every function here takes a raw `pid` (int or str) and validates it
through utils.safe_exec.validate_pid() before touching it — this is
the enforced choke point against PID confusion / TOCTOU races
described in the project's security requirements.

None of this module runs as root. If a PID belongs to another user
and permissions are insufficient, psutil.AccessDenied propagates up
as ActionPermissionError so the UI can offer a polkit-elevated retry
(see permissions/polkit_bridge.py) instead of silently failing.
"""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from enum import Enum

import psutil

from src.utils.logger import get_logger
from src.utils.safe_exec import InvalidPidError, validate_pid

logger = get_logger("process.process_actions")

GRACEFUL_TERM_WAIT_SECONDS = 3.0


class ActionOutcome(str, Enum):
    SUCCESS = "success"
    ALREADY_GONE = "already_gone"
    PERMISSION_DENIED = "permission_denied"
    TIMED_OUT_NEEDS_FORCE = "timed_out_needs_force"
    INVALID_PID = "invalid_pid"
    FAILED = "failed"


@dataclass
class ActionResult:
    outcome: ActionOutcome
    pid: int | None
    message: str


class ActionPermissionError(PermissionError):
    """Raised when the current user lacks rights to act on a PID."""


def _resolve(pid: object) -> tuple[int | None, ActionResult | None]:
    """Validate a PID, returning either (pid, None) or (None, error_result)."""
    try:
        return validate_pid(pid), None
    except InvalidPidError as exc:
        logger.info("Rejected invalid PID %r: %s", pid, exc)
        return None, ActionResult(ActionOutcome.INVALID_PID, None, str(exc))


def end_task(pid: object) -> ActionResult:
    """
    Politely ask a process to exit via SIGTERM. Does NOT wait/escalate
    itself — callers (UI layer) are expected to poll `is_running(pid)`
    for up to GRACEFUL_TERM_WAIT_SECONDS and offer Force Kill if it's
    still alive, matching the required End Task -> wait -> offer
    Force Kill flow.
    """
    valid_pid, error = _resolve(pid)
    if error:
        return error

    try:
        proc = psutil.Process(valid_pid)
        proc.terminate()  # SIGTERM
        logger.info("Sent SIGTERM to PID %s (%s)", valid_pid, _safe_name(proc))
        return ActionResult(ActionOutcome.SUCCESS, valid_pid, "SIGTERM sent")
    except psutil.NoSuchProcess:
        return ActionResult(ActionOutcome.ALREADY_GONE, valid_pid, "Process already exited")
    except psutil.AccessDenied:
        return ActionResult(
            ActionOutcome.PERMISSION_DENIED, valid_pid,
            "Insufficient permission to terminate this process",
        )


def wait_for_exit(pid: object, timeout_seconds: float = GRACEFUL_TERM_WAIT_SECONDS) -> bool:
    """
    Block (briefly) waiting for a process to exit after SIGTERM.
    Returns True if it exited within the timeout, False if it's still
    alive (caller should then offer Force Kill).
    """
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return True  # invalid pid == nothing to wait for

    try:
        proc = psutil.Process(pid_int)
        proc.wait(timeout=timeout_seconds)
        return True
    except psutil.NoSuchProcess:
        return True
    except psutil.TimeoutExpired:
        return False


def force_kill(pid: object) -> ActionResult:
    """Force-terminate a process via SIGKILL. Cannot be undone."""
    valid_pid, error = _resolve(pid)
    if error:
        return error

    try:
        proc = psutil.Process(valid_pid)
        name = _safe_name(proc)
        proc.kill()  # SIGKILL
        logger.warning("Sent SIGKILL to PID %s (%s)", valid_pid, name)
        return ActionResult(ActionOutcome.SUCCESS, valid_pid, "SIGKILL sent")
    except psutil.NoSuchProcess:
        return ActionResult(ActionOutcome.ALREADY_GONE, valid_pid, "Process already exited")
    except psutil.AccessDenied:
        return ActionResult(
            ActionOutcome.PERMISSION_DENIED, valid_pid,
            "Insufficient permission to force-kill this process",
        )


def get_process_tree_pids(root_pid: object) -> list[int]:
    """
    Return [root_pid, *all descendant pids] in a safe, read-only walk.
    Used both to render the tree UI and as the target list for
    "End Process Tree".
    """
    valid_pid, error = _resolve(root_pid)
    if error:
        return []

    try:
        root = psutil.Process(valid_pid)
        descendants = root.children(recursive=True)
        return [valid_pid] + [child.pid for child in descendants]
    except psutil.NoSuchProcess:
        return []


def end_process_tree(root_pid: object, force: bool = False) -> list[ActionResult]:
    """
    End (or force-kill) a process and all of its descendants.
    Children are signalled first, then the root, so a parent doesn't
    respawn anything while its tree is still being torn down.
    """
    pids = get_process_tree_pids(root_pid)
    if not pids:
        return [ActionResult(ActionOutcome.ALREADY_GONE, None, "Process tree not found")]

    root = pids[0]
    children = pids[1:]
    ordered_targets = children + [root]

    action = force_kill if force else end_task
    return [action(pid) for pid in ordered_targets]


def suspend(pid: object) -> ActionResult:
    """Pause a process (SIGSTOP)."""
    valid_pid, error = _resolve(pid)
    if error:
        return error
    try:
        psutil.Process(valid_pid).suspend()
        return ActionResult(ActionOutcome.SUCCESS, valid_pid, "Process suspended")
    except psutil.NoSuchProcess:
        return ActionResult(ActionOutcome.ALREADY_GONE, valid_pid, "Process already exited")
    except psutil.AccessDenied:
        return ActionResult(ActionOutcome.PERMISSION_DENIED, valid_pid, "Cannot suspend process")


def resume(pid: object) -> ActionResult:
    """Resume a suspended process (SIGCONT)."""
    valid_pid, error = _resolve(pid)
    if error:
        return error
    try:
        psutil.Process(valid_pid).resume()
        return ActionResult(ActionOutcome.SUCCESS, valid_pid, "Process resumed")
    except psutil.NoSuchProcess:
        return ActionResult(ActionOutcome.ALREADY_GONE, valid_pid, "Process already exited")
    except psutil.AccessDenied:
        return ActionResult(ActionOutcome.PERMISSION_DENIED, valid_pid, "Cannot resume process")


def set_priority(pid: object, nice_value: int) -> ActionResult:
    """
    Set a process's nice value. Range is clamped to [-20, 19]; going
    below 0 (higher priority) generally requires elevated privileges
    and will surface as PERMISSION_DENIED for a normal user, which
    the UI can offer to retry via polkit.
    """
    valid_pid, error = _resolve(pid)
    if error:
        return error

    clamped = max(-20, min(19, int(nice_value)))
    try:
        psutil.Process(valid_pid).nice(clamped)
        return ActionResult(ActionOutcome.SUCCESS, valid_pid, f"Priority set to {clamped}")
    except psutil.NoSuchProcess:
        return ActionResult(ActionOutcome.ALREADY_GONE, valid_pid, "Process already exited")
    except psutil.AccessDenied:
        return ActionResult(
            ActionOutcome.PERMISSION_DENIED, valid_pid,
            "Insufficient permission to change priority",
        )


def is_running(pid: object) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    return psutil.pid_exists(pid_int)


def _safe_name(proc: psutil.Process) -> str:
    try:
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "?"
