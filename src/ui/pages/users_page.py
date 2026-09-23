"""Users page (section 17): active sessions with optional Logout."""

from __future__ import annotations

import datetime
import getpass

from PySide6.QtGui import QStandardItem, QStandardItemModel
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

from src.system.users_monitor import list_user_sessions
from src.utils.safe_exec import run_argv

_COLUMNS = ("Username", "Terminal", "Login Time", "Processes", "CPU %", "RAM %")


class UsersPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(12)

        header_row = QHBoxLayout()
        heading = QLabel("Users")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        header_row.addWidget(heading)
        header_row.addStretch(1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.reload_sessions)
        header_row.addWidget(refresh_btn)
        root_layout.addLayout(header_row)

        self._model = QStandardItemModel(0, len(_COLUMNS), self)
        self._model.setHorizontalHeaderLabels(list(_COLUMNS))

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        root_layout.addWidget(self._table, stretch=1)

        self._logout_btn = QPushButton("Logout")
        self._logout_btn.setObjectName("dangerButton")
        self._logout_btn.setEnabled(False)
        self._logout_btn.clicked.connect(self._on_logout)
        root_layout.addWidget(self._logout_btn)

        self.reload_sessions()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reload_sessions()

    def reload_sessions(self) -> None:
        sessions = list_user_sessions()
        self._model.setRowCount(0)
        for session in sessions:
            login_str = "--"
            if session.login_time:
                try:
                    login_str = datetime.datetime.fromtimestamp(session.login_time).strftime("%Y-%m-%d %H:%M")
                except (OverflowError, OSError, ValueError):
                    pass
            row = [
                QStandardItem(session.username),
                QStandardItem(session.terminal),
                QStandardItem(login_str),
                QStandardItem(str(session.process_count)),
                QStandardItem(f"{session.cpu_percent:.1f}"),
                QStandardItem(f"{session.ram_percent:.1f}"),
            ]
            for item in row:
                item.setEditable(False)
            self._model.appendRow(row)

    def _on_selection_changed(self, *_args) -> None:
        indexes = self._table.selectionModel().selectedRows()
        self._logout_btn.setEnabled(bool(indexes))

    def _on_logout(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        username = self._model.item(indexes[0].row(), 0).text()

        if username == getpass.getuser():
            note = "This will log out YOUR current session."
        else:
            note = "This requires elevated permissions for other users."

        if QMessageBox.question(
            self, "Confirm Logout",
            f"Log out user '{username}'?\n\n{note}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        result = run_argv(["loginctl", "terminate-user", username], timeout=10.0)
        if not result.success:
            QMessageBox.warning(self, "Logout", f"Could not log out {username}: {result.stderr.strip()}")
        self.reload_sessions()
