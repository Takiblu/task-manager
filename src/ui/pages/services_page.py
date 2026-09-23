"""Services page (section 15): systemd unit browser with lifecycle actions."""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services import systemd_manager
from src.utils.logger import get_logger

logger = get_logger("ui.services_page")

_COLUMNS = ("Service", "Description", "Active", "Sub-state", "Enabled")


class ServiceListWorker(QThread):
    """Fetches the (potentially slow) systemctl listing off the UI thread."""

    finished_loading = Signal(list)

    def run(self) -> None:
        try:
            services = systemd_manager.list_services(user_scope=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load services")
            services = []
        self.finished_loading.emit(services)


class ServicesPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services_by_name = {}
        self._loader_thread: ServiceListWorker | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(12)

        header_row = QHBoxLayout()
        heading = QLabel("Services")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        header_row.addWidget(heading)
        header_row.addStretch(1)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search services…")
        self._search_box.setFixedWidth(260)
        self._search_box.textChanged.connect(self._on_search_changed)
        header_row.addWidget(self._search_box)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.reload_services)
        header_row.addWidget(refresh_btn)
        root_layout.addLayout(header_row)

        action_row = QHBoxLayout()
        self._start_btn = self._make_action_button("Start", self._on_start)
        self._stop_btn = self._make_action_button("Stop", self._on_stop)
        self._restart_btn = self._make_action_button("Restart", self._on_restart)
        self._reload_btn = self._make_action_button("Reload", self._on_reload)
        self._enable_btn = self._make_action_button("Enable", self._on_enable)
        self._disable_btn = self._make_action_button("Disable", self._on_disable)
        for btn in (self._start_btn, self._stop_btn, self._restart_btn,
                    self._reload_btn, self._enable_btn, self._disable_btn):
            action_row.addWidget(btn)
        action_row.addStretch(1)
        root_layout.addLayout(action_row)

        self._model = QStandardItemModel(0, len(_COLUMNS), self)
        self._model.setHorizontalHeaderLabels(list(_COLUMNS))
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        root_layout.addWidget(self._table, stretch=2)

        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setPlaceholderText("Select a service to see details…")
        self._detail_text.setMaximumHeight(160)
        root_layout.addWidget(self._detail_text)

        self._set_actions_enabled(False)

    def _make_action_button(self, label: str, handler) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("secondaryButton")
        btn.clicked.connect(handler)
        return btn

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._model.rowCount() == 0:
            self.reload_services()

    def reload_services(self) -> None:
        if self._loader_thread is not None and self._loader_thread.isRunning():
            return
        self._loader_thread = ServiceListWorker(self)
        self._loader_thread.finished_loading.connect(self._on_services_loaded)
        self._loader_thread.start()

    def _on_services_loaded(self, services: list) -> None:
        self._services_by_name = {s.name: s for s in services}
        self._model.setRowCount(0)
        for service in services:
            row = [
                QStandardItem(service.name),
                QStandardItem(service.description),
                QStandardItem("Active" if service.is_active else service.active_state.title()),
                QStandardItem(service.sub_state),
                QStandardItem("Enabled" if service.is_enabled else "Disabled"),
            ]
            for item in row:
                item.setEditable(False)
            self._model.appendRow(row)

    def _on_search_changed(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    def _selected_service_name(self) -> str | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        source_index = self._proxy.mapToSource(indexes[0])
        item = self._model.item(source_index.row(), 0)
        return item.text() if item else None

    def _on_selection_changed(self, *_args) -> None:
        name = self._selected_service_name()
        self._set_actions_enabled(name is not None)
        if name:
            detail = systemd_manager.get_service_detail(name)
            self._detail_text.setPlainText(detail[:4000])

    def _set_actions_enabled(self, enabled: bool) -> None:
        for btn in (self._start_btn, self._stop_btn, self._restart_btn,
                    self._reload_btn, self._enable_btn, self._disable_btn):
            btn.setEnabled(enabled)

    def _confirm(self, action: str, name: str) -> bool:
        return QMessageBox.question(
            self, f"{action} Service",
            f"{action} {name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _run_action(self, action_fn, action_label: str) -> None:
        name = self._selected_service_name()
        if not name:
            return
        if action_label in ("Stop", "Disable", "Restart") and not self._confirm(action_label, name):
            return
        result = action_fn(name)
        if result.outcome.value != "success":
            QMessageBox.warning(self, action_label, f"{action_label} failed: {result.message}")
        self.reload_services()

    def _on_start(self) -> None:
        self._run_action(systemd_manager.start_service, "Start")

    def _on_stop(self) -> None:
        self._run_action(systemd_manager.stop_service, "Stop")

    def _on_restart(self) -> None:
        self._run_action(systemd_manager.restart_service, "Restart")

    def _on_reload(self) -> None:
        self._run_action(systemd_manager.reload_service, "Reload")

    def _on_enable(self) -> None:
        self._run_action(systemd_manager.enable_service, "Enable")

    def _on_disable(self) -> None:
        self._run_action(systemd_manager.disable_service, "Disable")
