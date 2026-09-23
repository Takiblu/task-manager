"""
Processes page (sections 5-11, 28-30). Wires the table model to
End Task / Force Kill / End Process Tree / Suspend / Resume /
Properties / Search / Sort, using in-place model updates so the
selection and scroll position survive every poll tick.
"""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.core.monitor_worker import MonitorSnapshot
from src.process import process_actions
from src.process.process_properties import get_process_properties
from src.settings.app_settings import AppSettings
from src.ui.pages.process_table_model import ProcessTableModel
from src.ui.widgets.confirm_dialog import (
    confirm_end_process_tree,
    confirm_end_task,
    confirm_force_kill,
)
from src.ui.widgets.properties_dialog import PropertiesDialog
from src.utils.logger import get_logger

logger = get_logger("ui.processes_page")


class ProcessesPage(QWidget):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(12)

        header_row = QHBoxLayout()
        heading = QLabel("Processes")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        header_row.addWidget(heading)
        header_row.addStretch(1)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search by name, PID, user, command…")
        self._search_box.setFixedWidth(280)
        self._search_box.textChanged.connect(self._on_search_changed)
        header_row.addWidget(self._search_box)
        root_layout.addLayout(header_row)

        action_row = QHBoxLayout()
        self._end_task_button = QPushButton("End Task")
        self._end_task_button.setObjectName("dangerButton")
        self._end_task_button.setEnabled(False)
        self._end_task_button.clicked.connect(self._on_end_task_clicked)

        self._force_kill_button = QPushButton("Force Kill")
        self._force_kill_button.setObjectName("secondaryButton")
        self._force_kill_button.setEnabled(False)
        self._force_kill_button.clicked.connect(self._on_force_kill_clicked)

        action_row.addWidget(self._end_task_button)
        action_row.addWidget(self._force_kill_button)
        action_row.addStretch(1)
        root_layout.addLayout(action_row)

        self._model = ProcessTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # search across all columns

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        root_layout.addWidget(self._table, stretch=1)

    # -- data updates -----------------------------------------------------

    def update_snapshot(self, snapshot: MonitorSnapshot) -> None:
        self._model.update_processes(snapshot.processes)
        self._refresh_action_buttons()

    def _on_search_changed(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    # -- selection / action state ------------------------------------------

    def _selected_process(self):
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        source_index = self._proxy.mapToSource(indexes[0])
        return self._model.process_at_row(source_index.row())

    def _on_selection_changed(self, *_args) -> None:
        self._refresh_action_buttons()

    def _refresh_action_buttons(self) -> None:
        process = self._selected_process()
        enabled = process is not None
        self._end_task_button.setEnabled(enabled)
        self._force_kill_button.setEnabled(enabled)

    # -- actions ------------------------------------------------------------

    def _on_end_task_clicked(self) -> None:
        process = self._selected_process()
        if process is None:
            return
        self._end_task(process.pid, process.name)

    def _on_force_kill_clicked(self) -> None:
        process = self._selected_process()
        if process is None:
            return
        self._force_kill(process.pid, process.name)

    def _end_task(self, pid: int, name: str) -> None:
        if self._settings.confirm_end_task and not confirm_end_task(self, name, pid):
            return

        result = process_actions.end_task(pid)
        self._notify_action_result("End Task", name, result)

        if result.outcome.value == "success":
            # Give the process a moment, then offer Force Kill if it's
            # still alive (section 6: SIGTERM -> wait -> offer force).
            QTimer.singleShot(3000, lambda: self._offer_force_kill_if_still_running(pid, name))

    def _offer_force_kill_if_still_running(self, pid: int, name: str) -> None:
        if not process_actions.is_running(pid):
            return
        box = QMessageBox(self)
        box.setWindowTitle("Application Not Responding")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"{name} (PID {pid}) did not close in time.")
        box.setInformativeText("Would you like to force kill it?")
        force_btn = box.addButton("Force Kill", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Wait", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == force_btn:
            self._force_kill(pid, name, already_confirmed=True)

    def _force_kill(self, pid: int, name: str, already_confirmed: bool = False) -> None:
        if not already_confirmed and self._settings.confirm_force_kill and not confirm_force_kill(self, name, pid):
            return
        result = process_actions.force_kill(pid)
        self._notify_action_result("Force Kill", name, result)

    def _end_process_tree(self, pid: int, name: str) -> None:
        descendants = process_actions.get_process_tree_pids(pid)[1:]
        if not confirm_end_process_tree(self, name, pid, len(descendants)):
            return
        results = process_actions.end_process_tree(pid, force=False)
        failed = [r for r in results if r.outcome.value not in ("success", "already_gone")]
        if failed:
            QMessageBox.warning(
                self, "Task Manager",
                f"Some processes in the tree could not be ended:\n"
                + "\n".join(f"PID {r.pid}: {r.message}" for r in failed),
            )

    def _notify_action_result(self, action_label: str, name: str, result) -> None:
        from src.core.notifications import notify

        if result.outcome.value == "success":
            logger.info("%s succeeded for %s", action_label, name)
            if self._settings.notifications_enabled and self._settings.notify_process_terminated:
                notify("Task Manager", f"{name} was terminated successfully.")
        elif result.outcome.value == "permission_denied":
            if self._settings.notifications_enabled and self._settings.notify_errors:
                notify("Task Manager", f"Unable to {action_label.lower()} {name}: permission denied.")
            QMessageBox.warning(self, action_label, f"Permission denied: {result.message}")
        elif result.outcome.value == "already_gone":
            pass  # nothing to report; process was already gone
        else:
            if self._settings.notifications_enabled and self._settings.notify_errors:
                notify("Task Manager", f"Unable to {action_label.lower()} {name}.")

    # -- context menu ---------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        self._table.selectRow(index.row())
        process = self._selected_process()
        if process is None:
            return

        menu = QMenu(self)
        menu.addAction("End Task", lambda: self._end_task(process.pid, process.name))
        menu.addAction("Force Kill", lambda: self._force_kill(process.pid, process.name))
        menu.addAction(
            "End Process Tree", lambda: self._end_process_tree(process.pid, process.name)
        )
        menu.addSeparator()
        menu.addAction("Suspend", lambda: self._suspend(process.pid))
        menu.addAction("Resume", lambda: self._resume(process.pid))
        menu.addSeparator()
        menu.addAction("Properties", lambda: self._show_properties(process.pid))
        if process.exe:
            menu.addAction("Open File Location", lambda: self._open_file_location(process.exe))
        menu.addAction("Copy PID", lambda: self._copy_to_clipboard(str(process.pid)))
        menu.addAction("Copy Process Name", lambda: self._copy_to_clipboard(process.name))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _suspend(self, pid: int) -> None:
        result = process_actions.suspend(pid)
        if result.outcome.value == "permission_denied":
            QMessageBox.warning(self, "Suspend", result.message)

    def _resume(self, pid: int) -> None:
        result = process_actions.resume(pid)
        if result.outcome.value == "permission_denied":
            QMessageBox.warning(self, "Resume", result.message)

    def _show_properties(self, pid: int) -> None:
        props = get_process_properties(pid)
        if props is None:
            QMessageBox.information(self, "Properties", "This process is no longer available.")
            return
        dialog = PropertiesDialog(props, self)
        dialog.exec()

    def _open_file_location(self, exe_path: str) -> None:
        import os
        from pathlib import Path

        from src.utils.safe_exec import run_argv

        folder = str(Path(exe_path).parent)
        if os.environ.get("XDG_CURRENT_DESKTOP") is not None:
            run_argv(["xdg-open", folder], timeout=3.0)

    def _copy_to_clipboard(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
