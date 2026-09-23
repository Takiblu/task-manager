"""
Startup Apps manager (section 16): reads XDG autostart entries from
~/.config/autostart/ (and /etc/xdg/autostart/ as a read-only system
source), and can enable/disable/remove user-scope entries.

Enable/disable is implemented the standard XDG way: writing/removing
`X-GNOME-Autostart-enabled=false` (respected by most DEs) rather than
deleting the file outright, so re-enabling doesn't require redownloading
anything. Only files under the user's own ~/.config/autostart/ are
ever modified — system-wide entries under /etc/xdg/autostart/ are
shown read-only to satisfy "protect important files" (avoids silently
mutating a package-managed file that pacman/paru could then flag as
modified).
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("core.startup_manager")


@dataclass
class StartupEntry:
    name: str
    command: str
    enabled: bool
    source_path: str
    is_user_editable: bool


def _user_autostart_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    directory = base / "autostart"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _system_autostart_dirs() -> list[Path]:
    xdg_dirs = os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg")
    return [Path(d) / "autostart" for d in xdg_dirs.split(":") if d]


def _parse_desktop_entry(path: Path, editable: bool) -> StartupEntry | None:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error) as exc:
        logger.debug("Failed to parse autostart entry %s: %s", path, exc)
        return None

    if "Desktop Entry" not in parser:
        return None

    section = parser["Desktop Entry"]
    if section.get("Type", "Application") != "Application":
        return None
    if section.getboolean("Hidden", fallback=False):
        return None

    name = section.get("Name", path.stem)
    command = section.get("Exec", "")
    enabled = section.getboolean("X-GNOME-Autostart-enabled", fallback=True)

    return StartupEntry(
        name=name,
        command=command,
        enabled=enabled,
        source_path=str(path),
        is_user_editable=editable,
    )


def list_startup_entries() -> list[StartupEntry]:
    """
    Merge system + user autostart entries by filename, with user
    entries taking precedence (matching XDG spec override semantics).
    """
    entries_by_filename: dict[str, StartupEntry] = {}

    for system_dir in _system_autostart_dirs():
        if not system_dir.is_dir():
            continue
        for desktop_file in sorted(system_dir.glob("*.desktop")):
            entry = _parse_desktop_entry(desktop_file, editable=False)
            if entry:
                entries_by_filename[desktop_file.name] = entry

    user_dir = _user_autostart_dir()
    for desktop_file in sorted(user_dir.glob("*.desktop")):
        entry = _parse_desktop_entry(desktop_file, editable=True)
        if entry:
            entries_by_filename[desktop_file.name] = entry

    return list(entries_by_filename.values())


def _user_override_path(filename: str) -> Path:
    """Resolve a safe path inside the user's autostart dir for a given filename."""
    safe_name = Path(filename).name  # strips any directory traversal
    if not safe_name.endswith(".desktop"):
        raise ValueError("Invalid autostart filename")
    return _user_autostart_dir() / safe_name


def set_entry_enabled(filename: str, enabled: bool) -> bool:
    """
    Enable/disable a startup entry. If the entry currently only exists
    system-wide, a user-scope override copy is created first (so the
    original package-managed file under /etc/xdg is never touched).
    """
    try:
        target_path = _user_override_path(filename)
    except ValueError as exc:
        logger.warning("Refusing unsafe autostart filename: %s", exc)
        return False

    if not target_path.exists():
        # Copy from system dir as a starting point for the override.
        for system_dir in _system_autostart_dirs():
            candidate = system_dir / target_path.name
            if candidate.exists():
                try:
                    target_path.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
                except OSError as exc:
                    logger.error("Failed creating autostart override: %s", exc)
                    return False
                break
        else:
            logger.warning("No existing autostart entry found for %s", filename)
            return False

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(target_path, encoding="utf-8")
        if "Desktop Entry" not in parser:
            parser["Desktop Entry"] = {}
        parser["Desktop Entry"]["X-GNOME-Autostart-enabled"] = "true" if enabled else "false"
        with target_path.open("w", encoding="utf-8") as fh:
            parser.write(fh)
        return True
    except (OSError, configparser.Error) as exc:
        logger.error("Failed to update autostart entry %s: %s", target_path, exc)
        return False


def remove_entry(filename: str) -> bool:
    """Remove a user-scope autostart entry only (never touches /etc/xdg)."""
    try:
        target_path = _user_override_path(filename)
    except ValueError:
        return False

    if not target_path.exists():
        return False

    try:
        target_path.unlink()
        return True
    except OSError as exc:
        logger.error("Failed to remove autostart entry %s: %s", target_path, exc)
        return False
