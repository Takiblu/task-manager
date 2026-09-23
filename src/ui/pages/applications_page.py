"""
Applications page (section 12): a filtered view of Processes limited
to processes that look like GUI applications (heuristic: has a
non-empty cmdline, is not a kernel thread, and belongs to the current
graphical session's user). Reuses ProcessTableModel/actions rather
than re-implementing End Task / Force Kill.
"""

from __future__ import annotations

import getpass

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.core.monitor_worker import MonitorSnapshot
from src.process import process_actions
from src.settings.app_settings import AppSettings
from src.ui.pages.process_table_model import ProcessTableModel
from src.ui.widgets.confirm_dialog import confirm_end_task, confirm_force_kill

# A small heuristic denylist of names that are almost never
# user-facing GUI applications even though they may have a window.
_NON_APP_NAME_HINTS = ("kdeconnect", "xdg-desktop-portal", "polkit", "dbus", "pipewire", "wireplumber")


def _looks_like_application(process) -> bool:
    if process.is_kernel_thread or process.is_system_process:
        return False
    if not process.cmdline:
        return False
    name_lower = process.name.lower()
    if any(hint in name_lower for hint in _NON_APP_NAME_HINTS):
        return False
    return process.username == getpass.getuser()


class ApplicationsPage(QWidget):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(12)

        header_row = QHBoxLayout()
        heading = QLabel("Applications")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        header_row.addWidget(heading)
        header_row.addStretch(1)
        root_layout.addLayout(header_row)

        action_row = QHBoxLayout()
        self._end_task_btn = QPushButton("End Task")
        self._end_task_btn.setObjectName("dangerButton")
        self._end_task_btn.setEnabled(False)
        self._end_task_btn.clicked.connect(self._on_end_task)

        self._force_kill_btn = QPushButton("Force Kill")
        self._force_kill_btn.setObjectName("secondaryButton")
        self._force_kill_btn.setEnabled(False)
        self._force_kill_btn.clicked.connect(self._on_force_kill)

        action_row.addWidget(self._end_task_btn)
        action_row.addWidget(self._force_kill_btn)
        action_row.addStretch(1)
        root_layout.addLayout(action_row)

        self._model = ProcessTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.selectionModel().selectionChanged.connect(self._refresh_buttons)
        root_layout.addWidget(self._table, stretch=1)

    def update_snapshot(self, snapshot: MonitorSnapshot) -> None:
        apps = [p for p in snapshot.processes if _looks_like_application(p)]
        self._model.update_processes(apps)
        self._refresh_buttons()

    def _selected_process(self):
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        source_index = self._proxy.mapToSource(indexes[0])
        return self._model.process_at_row(source_index.row())

    def _refresh_buttons(self, *_args) -> None:
        process = self._selected_process()
        enabled = process is not None
        self._end_task_btn.setEnabled(enabled)
        self._force_kill_btn.setEnabled(enabled)

    def _on_end_task(self) -> None:
        process = self._selected_process()
        if not process:
            return
        if self._settings.confirm_end_task and not confirm_end_task(self, process.name, process.pid):
            return
        result = process_actions.end_task(process.pid)
        if result.outcome.value == "permission_denied":
            QMessageBox.warning(self, "End Task", result.message)

    def _on_force_kill(self) -> None:
        process = self._selected_process()
        if not process:
            return
        if self._settings.confirm_force_kill and not confirm_force_kill(self, process.name, process.pid):
            return
        result = process_actions.force_kill(process.pid)
        if result.outcome.value == "permission_denied":
            QMessageBox.warning(self, "Force Kill", result.message)
