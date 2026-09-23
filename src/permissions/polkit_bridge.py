"""
Privilege escalation via polkit's `pkexec`, used ONLY for actions
that genuinely require root (enabling/disabling a systemd service
owned by another user context, editing a system-wide autostart
entry, etc.). The app itself never runs as root and never calls
`sudo` — see project security requirements (section 9, 26).

Every elevated call still goes through utils.safe_exec.run_argv(),
so it is still an argv list, never a shell string.
"""

from __future__ import annotations

import shutil

from src.utils.logger import get_logger
from src.utils.safe_exec import CommandResult, run_argv

logger = get_logger("permissions.polkit_bridge")


def is_polkit_available() -> bool:
    return shutil.which("pkexec") is not None


def run_privileged(argv: list[str], timeout: float = 15.0) -> CommandResult:
    """
    Run `argv` elevated via pkexec, prompting the user through their
    desktop's polkit authentication agent. If pkexec is not installed,
    returns a synthetic failure rather than silently trying something
    else (like sudo), keeping the privilege path singular and auditable.
    """
    if not is_polkit_available():
        logger.warning("pkexec not found; cannot escalate privileges for: %s", argv)
        return CommandResult(
            success=False, returncode=127, stdout="",
            stderr="pkexec is not installed; cannot request elevated permissions.",
        )

    full_argv = ["pkexec", *argv]
    return run_argv(full_argv, timeout=timeout)
