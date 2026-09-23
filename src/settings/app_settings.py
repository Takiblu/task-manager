"""
Application settings: persisted as JSON under
$XDG_CONFIG_HOME/manjaro-task-manager/settings.json (falls back to
~/.config/...). A single AppSettings instance is created at startup
and shared (via dependency passing, not globals) across the UI and
core modules that need it (update interval, confirmation dialogs,
theme, etc.)
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger

logger = get_logger("settings.app_settings")

CONFIG_DIR_NAME = "manjaro-task-manager"
CONFIG_FILE_NAME = "settings.json"

VALID_THEMES = ("dark", "light", "system")
MIN_UPDATE_INTERVAL_MS = 500
MAX_UPDATE_INTERVAL_MS = 5000
DEFAULT_UPDATE_INTERVAL_MS = 1000


@dataclass
class AppSettings:
    # Appearance
    theme: str = "system"
    accent_color: str = "#4CAF7D"  # Manjaro-esque green

    # Performance
    update_interval_ms: int = DEFAULT_UPDATE_INTERVAL_MS
    animations_enabled: bool = True
    chart_history_points: int = 120

    # Process behavior
    confirm_end_task: bool = True
    confirm_force_kill: bool = True
    show_system_processes: bool = True
    show_kernel_threads: bool = False

    # Startup
    start_with_system: bool = False
    start_minimized: bool = False
    start_in_tray: bool = False

    # Notifications
    notifications_enabled: bool = True
    notify_process_terminated: bool = True
    notify_service_changed: bool = True
    notify_errors: bool = True

    # Shortcuts (editable from Settings; values are Qt key-sequence strings)
    shortcut_open: str = "Ctrl+Shift+T"
    shortcut_search: str = "Ctrl+F"
    shortcut_refresh: str = "F5"
    shortcut_end_task: str = "Del"
    shortcut_force_kill: str = "Shift+Del"
    shortcut_settings: str = "Ctrl+,"
    shortcut_quit: str = "Ctrl+Q"

    def clamp(self) -> None:
        """Clamp/validate fields after loading untrusted JSON from disk."""
        if self.theme not in VALID_THEMES:
            self.theme = "system"
        self.update_interval_ms = max(
            MIN_UPDATE_INTERVAL_MS, min(MAX_UPDATE_INTERVAL_MS, int(self.update_interval_ms))
        )
        self.chart_history_points = max(30, min(600, int(self.chart_history_points)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        known_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        instance = cls(**filtered)
        instance.clamp()
        return instance


def get_config_path() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    config_dir = base / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / CONFIG_FILE_NAME


def load_settings() -> AppSettings:
    path = get_config_path()
    if not path.exists():
        logger.info("No settings file found, using defaults.")
        return AppSettings()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("settings.json root is not an object")
        settings = AppSettings.from_dict(raw)
        logger.debug("Loaded settings from %s", path)
        return settings
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to load settings (%s); falling back to defaults.", exc)
        return AppSettings()


def save_settings(settings: AppSettings) -> bool:
    path = get_config_path()
    tmp_path = path.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(
            json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp_path.replace(path)  # atomic on same filesystem
        logger.debug("Saved settings to %s", path)
        return True
    except OSError as exc:
        logger.error("Failed to save settings: %s", exc)
        return False
