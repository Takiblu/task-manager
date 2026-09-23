"""
Application-wide logging configuration.

Logs are written to ~/.local/state/manjaro-task-manager/app.log
(rotated) and mirrored to stderr at WARNING+ when running interactively.
This module is imported first by main.py so that every other module
can safely do `logger = logging.getLogger(__name__)`.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

APP_STATE_DIR_NAME = "manjaro-task-manager"
LOG_FILE_NAME = "app.log"
MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3

_configured = False


def get_state_dir() -> Path:
    """
    Return the XDG state directory for this application, creating it
    if necessary. Falls back to a temp-like location under $HOME if
    XDG_STATE_HOME is not set, per the XDG Base Directory spec.
    """
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        base = Path(xdg_state_home)
    else:
        base = Path.home() / ".local" / "state"

    state_dir = base / APP_STATE_DIR_NAME
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Last-resort fallback: use a directory under /tmp so the app
        # never crashes purely because logging couldn't be set up.
        state_dir = Path("/tmp") / APP_STATE_DIR_NAME
        state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def configure_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure the root logger once. Safe to call multiple times;
    subsequent calls are no-ops. Returns the root application logger.
    """
    global _configured
    root_logger = logging.getLogger("manjaro_task_manager")

    if _configured:
        return root_logger

    root_logger.setLevel(logging.DEBUG)

    log_dir = get_state_dir()
    log_path = log_dir / LOG_FILE_NAME

    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except OSError as exc:
        # If we can't write logs to disk, still continue running;
        # console output below will carry diagnostic information.
        print(f"[manjaro-task-manager] could not open log file: {exc}", file=sys.stderr)

    console_formatter = logging.Formatter(
        fmt="%(levelname)-8s %(name)s: %(message)s"
    )
    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    _configured = True
    root_logger.debug("Logging initialized. Log file: %s", log_path)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Convenience helper: get a child logger under the app namespace."""
    configure_logging()
    return logging.getLogger(f"manjaro_task_manager.{name}")
