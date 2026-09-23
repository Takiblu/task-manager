"""
Linux desktop notifications (section 23). Prefers the Qt/D-Bus route
via QDBusInterface directly against org.freedesktop.Notifications so
we don't depend on the `notify-send` binary being installed, but
falls back to it if D-Bus is unavailable (e.g. running outside a
full session bus).
"""

from __future__ import annotations

import shutil

from src.utils.logger import get_logger
from src.utils.safe_exec import run_argv

logger = get_logger("core.notifications")

_APP_NAME = "Task Manager"


def _notify_via_dbus(title: str, body: str) -> bool:
    try:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface
    except ImportError:
        return False

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False

    interface = QDBusInterface(
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        bus,
    )
    if not interface.isValid():
        return False

    reply = interface.call(
        "Notify",
        _APP_NAME,        # app_name
        0,                 # replaces_id
        "",                # app_icon
        title,             # summary
        body,              # body
        [],                # actions
        {},                # hints
        5000,              # timeout ms
    )
    return reply.type() != reply.type().ErrorMessage if hasattr(reply, "type") else True


def notify(title: str, body: str) -> None:
    """Show a desktop notification. Never raises — failures are logged only."""
    try:
        if _notify_via_dbus(title, body):
            return
    except Exception as exc:  # noqa: BLE001
        logger.debug("D-Bus notification failed: %s", exc)

    if shutil.which("notify-send"):
        result = run_argv(["notify-send", "--app-name", _APP_NAME, title, body], timeout=3.0)
        if not result.success:
            logger.debug("notify-send failed: %s", result.stderr.strip())
    else:
        logger.debug("No notification backend available; skipping: %s / %s", title, body)
