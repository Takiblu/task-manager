"""Startup Apps page (section 16)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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

from src.core.startup_manager import list_startup_entries, remove_entry, set_entry_enabled

_COLUMNS = ("Application", "Command", "Enabled", "Source")


class StartupPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(12)

        header_row = QHBoxLayout()
        heading = QLabel("Startup Apps")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        header_row.addWidget(heading)
        header_row.addStretch(1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.reload_entries)
        header_row.addWidget(refresh_btn)
        root_layout.addLayout(header_row)

        action_row = QHBoxLayout()
        self._enable_btn = QPushButton("Enable")
        self._enable_btn.setObjectName("secondaryButton")
        self._enable_btn.clicked.connect(lambda: self._toggle_selected(True))
        self._disable_btn = QPushButton("Disable")
        self._disable_btn.setObjectName("secondaryButton")
        self._disable_btn.clicked.connect(lambda: self._toggle_selected(False))
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setObjectName("dangerButton")
        self._remove_btn.clicked.connect(self._remove_selected)
        for btn in (self._enable_btn, self._disable_btn, self._remove_btn):
            btn.setEnabled(False)
            action_row.addWidget(btn)
        action_row.addStretch(1)
        root_layout.addLayout(action_row)

        self._model = QStandardItemModel(0, len(_COLUMNS), self)
        self._model.setHorizontalHeaderLabels(list(_COLUMNS))

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        root_layout.addWidget(self._table, stretch=1)

        self.reload_entries()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reload_entries()

    def reload_entries(self) -> None:
        entries = list_startup_entries()
        self._model.setRowCount(0)
        for entry in entries:
            filename = Path(entry.source_path).name
            row = [
                QStandardItem(entry.name),
                QStandardItem(entry.command),
                QStandardItem("Yes" if entry.enabled else "No"),
                QStandardItem("User" if entry.is_user_editable else "System"),
            ]
            row[0].setData(filename, Qt.ItemDataRole.UserRole)
            row[0].setData(entry.is_user_editable, Qt.ItemDataRole.UserRole + 1)
            for item in row:
                item.setEditable(False)
            self._model.appendRow(row)

    def _selected_row_data(self):
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None, False
        item = self._model.item(indexes[0].row(), 0)
        filename = item.data(Qt.ItemDataRole.UserRole)
        editable = item.data(Qt.ItemDataRole.UserRole + 1)
        return filename, editable

    def _on_selection_changed(self, *_args) -> None:
        filename, editable = self._selected_row_data()
        enabled = filename is not None and editable
        self._enable_btn.setEnabled(enabled)
        self._disable_btn.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled)

    def _toggle_selected(self, enable: bool) -> None:
        filename, editable = self._selected_row_data()
        if not filename or not editable:
            return
        if not set_entry_enabled(filename, enable):
            QMessageBox.warning(self, "Startup Apps", "Failed to update this entry.")
        self.reload_entries()

    def _remove_selected(self) -> None:
        filename, editable = self._selected_row_data()
        if not filename or not editable:
            return
        if QMessageBox.question(
            self, "Remove Startup Entry", f"Remove '{filename}' from startup?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        if not remove_entry(filename):
            QMessageBox.warning(self, "Startup Apps", "Failed to remove this entry.")
        self.reload_entries()
