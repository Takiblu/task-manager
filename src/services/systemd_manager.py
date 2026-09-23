"""
systemd Service Manager (section 15). Uses `systemctl` via argv-list
subprocess calls — never shell strings. Read operations (list-units,
show) run as the current user; unit files not owned by the user or
requiring root (system-scope start/stop/enable/disable when not
already permitted by polkit rules) are retried elevated through
permissions/polkit_bridge.py on demand, never automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.permissions.polkit_bridge import run_privileged
from src.utils.logger import get_logger
from src.utils.safe_exec import run_argv

logger = get_logger("services.systemd_manager")

_VALID_UNIT_SUFFIX = ".service"


class ServiceActionOutcome(str, Enum):
    SUCCESS = "success"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    FAILED = "failed"


@dataclass
class ServiceInfo:
    name: str
    description: str
    load_state: str
    active_state: str
    sub_state: str
    unit_file_state: str  # enabled/disabled/static/...

    @property
    def is_active(self) -> bool:
        return self.active_state == "active"

    @property
    def is_failed(self) -> bool:
        return self.active_state == "failed" or self.sub_state == "failed"

    @property
    def is_enabled(self) -> bool:
        return self.unit_file_state == "enabled"


@dataclass
class ServiceActionResult:
    outcome: ServiceActionOutcome
    message: str


def _validate_unit_name(name: str) -> str:
    """
    Reject anything that isn't a plausible systemd unit name before it
    ever reaches an argv list, closing off unit-name-based injection
    even though argv lists already prevent shell injection.
    """
    if not name or "/" in name or ".." in name or "\x00" in name:
        raise ValueError(f"Invalid unit name: {name!r}")
    if not name.endswith(_VALID_UNIT_SUFFIX):
        name = f"{name}{_VALID_UNIT_SUFFIX}"
    return name


def list_services(user_scope: bool = False) -> list[ServiceInfo]:
    """
    List all known service units with their load/active/sub state and
    enabled/disabled status, in a single `systemctl list-units` +
    `list-unit-files` pass merged by unit name.
    """
    scope_flag = ["--user"] if user_scope else []

    units_result = run_argv(
        ["systemctl", *scope_flag, "list-units", "--type=service", "--all", "--no-legend", "--no-pager"],
        timeout=10.0,
    )
    files_result = run_argv(
        ["systemctl", *scope_flag, "list-unit-files", "--type=service", "--no-legend", "--no-pager"],
        timeout=10.0,
    )

    enabled_state_by_name: dict[str, str] = {}
    if files_result.success:
        for line in files_result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                enabled_state_by_name[parts[0]] = parts[1]

    services: list[ServiceInfo] = []
    if not units_result.success:
        logger.warning("Failed to list systemd units: %s", units_result.stderr.strip())
        return services

    for line in units_result.stdout.strip().splitlines():
        # Columns: UNIT LOAD ACTIVE SUB DESCRIPTION...
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        unit, load_state, active_state, sub_state, description = parts
        if not unit.endswith(_VALID_UNIT_SUFFIX):
            continue
        services.append(
            ServiceInfo(
                name=unit,
                description=description.strip(),
                load_state=load_state,
                active_state=active_state,
                sub_state=sub_state,
                unit_file_state=enabled_state_by_name.get(unit, "unknown"),
            )
        )

    return services


def get_service_detail(name: str, user_scope: bool = False) -> str:
    """Return the raw `systemctl show` output for a unit (for a details panel)."""
    unit = _validate_unit_name(name)
    scope_flag = ["--user"] if user_scope else []
    result = run_argv(["systemctl", *scope_flag, "show", unit, "--no-pager"], timeout=5.0)
    return result.stdout if result.success else result.stderr


def _run_systemctl_action(
    action: str, name: str, user_scope: bool, allow_privileged_retry: bool
) -> ServiceActionResult:
    unit = _validate_unit_name(name)
    scope_flag = ["--user"] if user_scope else []
    argv = ["systemctl", *scope_flag, action, unit]

    result = run_argv(argv, timeout=15.0)
    if result.success:
        return ServiceActionResult(ServiceActionOutcome.SUCCESS, f"{action} succeeded for {unit}")

    permission_related = "Interactive authentication required" in result.stderr or "Access denied" in result.stderr

    if permission_related and allow_privileged_retry and not user_scope:
        logger.info("Retrying '%s %s' with elevated privileges via polkit", action, unit)
        elevated = run_privileged(["systemctl", action, unit], timeout=20.0)
        if elevated.success:
            return ServiceActionResult(ServiceActionOutcome.SUCCESS, f"{action} succeeded for {unit} (elevated)")
        return ServiceActionResult(ServiceActionOutcome.PERMISSION_DENIED, elevated.stderr.strip())

    if permission_related:
        return ServiceActionResult(ServiceActionOutcome.PERMISSION_DENIED, result.stderr.strip())

    if "not found" in result.stderr.lower() or "could not be found" in result.stderr.lower():
        return ServiceActionResult(ServiceActionOutcome.NOT_FOUND, result.stderr.strip())

    return ServiceActionResult(ServiceActionOutcome.FAILED, result.stderr.strip())


def start_service(name: str, user_scope: bool = False) -> ServiceActionResult:
    return _run_systemctl_action("start", name, user_scope, allow_privileged_retry=True)


def stop_service(name: str, user_scope: bool = False) -> ServiceActionResult:
    return _run_systemctl_action("stop", name, user_scope, allow_privileged_retry=True)


def restart_service(name: str, user_scope: bool = False) -> ServiceActionResult:
    return _run_systemctl_action("restart", name, user_scope, allow_privileged_retry=True)


def reload_service(name: str, user_scope: bool = False) -> ServiceActionResult:
    return _run_systemctl_action("reload", name, user_scope, allow_privileged_retry=True)


def enable_service(name: str, user_scope: bool = False) -> ServiceActionResult:
    return _run_systemctl_action("enable", name, user_scope, allow_privileged_retry=True)


def disable_service(name: str, user_scope: bool = False) -> ServiceActionResult:
    return _run_systemctl_action("disable", name, user_scope, allow_privileged_retry=True)
