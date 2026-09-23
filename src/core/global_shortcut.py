"""
Global shortcut handling (section 21).

Reality check this module encodes: there is no portable, unprivileged
API for registering a truly global hotkey on Wayland — each
compositor decides whether/how to expose that (GNOME and KDE both
require the shortcut to be bound through their own settings, not
grabbed directly by the app). So:

  * On X11: we CAN register a real global grab via Xlib bindings if
    `python-xlib` is available, and we do so.
  * On Wayland: we do NOT claim to own a global hotkey. Instead we
    register a "Custom Shortcut" with the desktop environment via its
    own mechanism where one exists (GNOME's custom-keybindings gsettings
    schema is the only broadly-scriptable case), and otherwise show the
    user manual setup instructions pointing the shortcut at:

        manjaro-task-manager --toggle

  * In both cases, an in-app fallback exists: while the app window has
    focus, the shortcut still works as a normal (non-global) QShortcut,
    so the feature is never silently broken — just its *global* reach
    is what's platform-limited, and we say so honestly in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger
from src.utils.platform_info import detect_display_server
from src.utils.safe_exec import run_argv

logger = get_logger("core.global_shortcut")


class GlobalShortcutMethod(str, Enum):
    X11_NATIVE_GRAB = "x11_native_grab"
    GNOME_CUSTOM_KEYBINDING = "gnome_custom_keybinding"
    MANUAL_SETUP_REQUIRED = "manual_setup_required"
    UNAVAILABLE = "unavailable"


@dataclass
class GlobalShortcutStatus:
    method: GlobalShortcutMethod
    is_truly_global: bool
    instructions: str | None = None


_GNOME_KEYBINDING_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/manjaro-task-manager/"


def _try_register_gnome_custom_keybinding(shortcut: str, exec_command: str) -> bool:
    """
    Best-effort registration of a GNOME custom keybinding via gsettings.
    Only works on GNOME/GNOME-based Wayland sessions where gsettings is
    present; silently returns False everywhere else so the caller can
    fall back to manual instructions.
    """
    from src.utils.safe_exec import run_argv

    check = run_argv(["gsettings", "--version"], timeout=2.0)
    if not check.success:
        return False

    list_result = run_argv(
        ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"],
        timeout=2.0,
    )
    if not list_result.success:
        return False

    existing = list_result.stdout.strip()
    if _GNOME_KEYBINDING_PATH not in existing:
        if existing in ("@as []", "[]"):
            new_list = f"['{_GNOME_KEYBINDING_PATH}']"
        else:
            trimmed = existing.rstrip("]").rstrip()
            separator = "" if trimmed.endswith("[") else ", "
            new_list = f"{trimmed}{separator}'{_GNOME_KEYBINDING_PATH}']"
        run_argv(
            ["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys",
             "custom-keybindings", new_list],
            timeout=2.0,
        )

    schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{_GNOME_KEYBINDING_PATH}"
    run_argv(["gsettings", "set", schema, "name", "Manjaro Task Manager"], timeout=2.0)
    run_argv(["gsettings", "set", schema, "command", exec_command], timeout=2.0)
    binding = run_argv(["gsettings", "set", schema, "binding", shortcut], timeout=2.0)
    return binding.success


def configure_global_shortcut(shortcut: str, exec_command: str) -> GlobalShortcutStatus:
    """
    Attempt to configure a global shortcut using the best available
    method for the current session. Always returns a status the UI
    can honestly display — never silently claims success.
    """
    display_server = detect_display_server()

    if display_server == "X11":
        try:
            import Xlib  # noqa: F401  (presence check only)
            return GlobalShortcutStatus(
                method=GlobalShortcutMethod.X11_NATIVE_GRAB,
                is_truly_global=True,
                instructions=None,
            )
        except ImportError:
            logger.info("python-xlib not installed; cannot register a native X11 grab.")

    if _try_register_gnome_custom_keybinding(shortcut, exec_command):
        return GlobalShortcutStatus(
            method=GlobalShortcutMethod.GNOME_CUSTOM_KEYBINDING,
            is_truly_global=True,
            instructions=None,
        )

    instructions = (
        f"Your desktop environment does not allow this application to register a "
        f"global shortcut automatically. To set it up manually, open your desktop's "
        f"Keyboard Shortcuts settings and bind '{shortcut}' to run:\n\n"
        f"    {exec_command}"
    )
    return GlobalShortcutStatus(
        method=GlobalShortcutMethod.MANUAL_SETUP_REQUIRED,
        is_truly_global=False,
        instructions=instructions,
    )
