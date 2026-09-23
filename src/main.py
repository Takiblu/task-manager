#!/usr/bin/env python3
"""
Manjaro Task Manager — entry point.

Usage:
    manjaro-task-manager             Launch the application normally.
    manjaro-task-manager --toggle    Used by the global-shortcut / autostart
                                      integration to show/hide an already
                                      running instance (see README for the
                                      single-instance IPC mechanism).
    manjaro-task-manager --verbose   Enable debug-level console logging.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.utils.logger import configure_logging, get_logger

_SINGLE_INSTANCE_KEY = "manjaro-task-manager-singleton"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="manjaro-task-manager")
    parser.add_argument(
        "--toggle", action="store_true",
        help="Show/hide the running instance (used by the global shortcut).",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose console logging.",
    )
    parser.add_argument(
        "--minimized", action="store_true",
        help="Start minimized to the system tray.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    logger = configure_logging(verbose=args.verbose)
    logger.info("Starting Manjaro Task Manager")

    # Single-instance guard: if another instance is already running,
    # this process just exits (a future enhancement can wire --toggle
    # through a local socket to actually message the running instance;
    # documented as a known limitation in the README for now).
    shared_memory = QSharedMemory(_SINGLE_INSTANCE_KEY)
    if shared_memory.attach():
        logger.info("Another instance is already running; exiting.")
        return 0
    if not shared_memory.create(1):
        logger.warning("Could not create single-instance guard; continuing anyway.")

    app = QApplication(sys.argv)
    app.setApplicationName("Manjaro Task Manager")
    app.setOrganizationName("ManjaroTaskManager")
    app.setQuitOnLastWindowClosed(False)  # keep running when minimized to tray

    from src.settings.app_settings import load_settings

    settings = load_settings()
    if args.minimized:
        settings.start_minimized = True

    window = MainWindow(settings)  # noqa: F841 - must stay referenced for the app's lifetime

    exit_code = app.exec()
    shared_memory.detach()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
