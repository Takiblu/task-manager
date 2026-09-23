"""
MainWindow: assembles the sidebar, the stacked pages, the menu bar,
the system tray, global/local shortcuts, and owns the monitor worker
thread's lifecycle.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QWidget,
)

from src.core.global_shortcut import configure_global_shortcut
from src.core.monitor_worker import build_monitor_thread
from src.settings.app_settings import AppSettings, save_settings
from src.ui.pages.applications_page import ApplicationsPage
from src.ui.pages.overview_page import OverviewPage
from src.ui.pages.performance_page import PerformancePage
from src.ui.pages.processes_page import ProcessesPage
from src.ui.pages.services_page import ServicesPage
from src.ui.pages.settings_page import SettingsPage
from src.ui.pages.startup_page import StartupPage
from src.ui.pages.system_page import SystemPage
from src.ui.pages.users_page import UsersPage
from src.ui.theme.theme_manager import build_stylesheet
from src.ui.widgets.about_dialog import AboutDialog
from src.ui.widgets.sidebar import Sidebar
from src.utils.logger import get_logger

logger = get_logger("ui.main_window")

APP_TRAY_ICON_EMOJI_FALLBACK = "🖥️"
_ICON_NAME = "manjaro-task-manager"
_SOURCE_ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "icons" / f"{_ICON_NAME}.svg"


def _application_icon() -> QIcon:
    """Load the bundled SVG in development and the themed icon when installed."""
    icon = QIcon(str(_SOURCE_ICON_PATH))
    if not icon.isNull():
        return icon
    return QIcon.fromTheme(_ICON_NAME)


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._settings = settings
        self._force_quit = False

        self.setWindowTitle("Manjaro Task Manager")
        self.setWindowIcon(_application_icon())
        self.resize(1180, 760)
        self.setStyleSheet(build_stylesheet(settings))

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, stretch=1)

        self.overview_page = OverviewPage()
        self.processes_page = ProcessesPage(settings)
        self.applications_page = ApplicationsPage(settings)
        self.performance_page = PerformancePage(settings.chart_history_points)
        self.services_page = ServicesPage()
        self.startup_page = StartupPage()
        self.users_page = UsersPage()
        self.system_page = SystemPage()
        self.settings_page = SettingsPage(settings)

        self._page_index_by_key = {}
        for key, widget in (
            ("overview", self.overview_page),
            ("processes", self.processes_page),
            ("applications", self.applications_page),
            ("performance", self.performance_page),
            ("services", self.services_page),
            ("startup", self.startup_page),
            ("users", self.users_page),
            ("system", self.system_page),
            ("settings", self.settings_page),
        ):
            self._page_index_by_key[key] = self.pages.addWidget(widget)

        self.sidebar.page_selected.connect(self._on_page_selected)
        self.settings_page.settings_changed.connect(self._on_settings_changed)

        self._build_menu_bar()
        self._build_tray_icon()
        self._build_shortcuts()
        self._start_monitor_thread()

        if settings.start_minimized:
            self.hide()
        else:
            self.show()

    # -- page switching --------------------------------------------------

    def _on_page_selected(self, key: str) -> None:
        index = self._page_index_by_key.get(key)
        if index is not None:
            self.pages.setCurrentIndex(index)

    # -- monitor worker thread --------------------------------------------

    def _start_monitor_thread(self) -> None:
        self._monitor_thread, self._monitor_worker = build_monitor_thread(self._settings)
        self._monitor_worker.snapshot_ready.connect(self._on_snapshot)
        self._monitor_worker.error_occurred.connect(self._on_monitor_error)
        self._monitor_thread.start()

    def _on_snapshot(self, snapshot) -> None:
        self.overview_page.update_snapshot(snapshot)
        self.processes_page.update_snapshot(snapshot)
        self.applications_page.update_snapshot(snapshot)
        self.performance_page.update_snapshot(snapshot)

    def _on_monitor_error(self, message: str) -> None:
        logger.warning("Monitor worker reported an error: %s", message)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = settings
        self.setStyleSheet(build_stylesheet(settings))
        self._monitor_worker.update_interval(settings.update_interval_ms)
        self._monitor_worker.update_filters(settings.show_system_processes, settings.show_kernel_threads)
        self.performance_page.set_history_length(settings.chart_history_points)

    # -- menu bar ----------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction("Refresh", lambda: None)  # live polling already refreshes continuously
        file_menu.addAction("Minimize to Tray", self.hide)
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_application)

        view_menu = menu_bar.addMenu("&View")
        for key, label in (
            ("overview", "Overview"), ("processes", "Processes"), ("performance", "Performance"),
            ("services", "Services"), ("startup", "Startup"), ("users", "Users"), ("system", "System"),
        ):
            view_menu.addAction(label, lambda k=key: self.sidebar.select_page(k))

        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction("Process Inspector", lambda: self.sidebar.select_page("processes"))
        tools_menu.addAction("Service Manager", lambda: self.sidebar.select_page("services"))

        settings_menu = menu_bar.addMenu("&Settings")
        settings_menu.addAction("Preferences", lambda: self.sidebar.select_page("settings"))

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction("About", self._show_about)

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    # -- system tray ---------------------------------------------------------

    def _build_tray_icon(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.windowIcon()
        if icon.isNull():
            icon = QIcon.fromTheme("utilities-system-monitor")
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("Manjaro Task Manager")

        tray_menu = QMenu()
        tray_menu.addAction("Open Task Manager", self._restore_from_tray)
        tray_menu.addSeparator()
        for key, label in (
            ("overview", "Overview"), ("processes", "Processes"),
            ("performance", "Performance"), ("settings", "Settings"),
        ):
            tray_menu.addAction(label, lambda k=key: self._open_page_from_tray(k))
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", self._quit_application)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        if self._settings.start_in_tray or QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _open_page_from_tray(self, key: str) -> None:
        self._restore_from_tray()
        self.sidebar.select_page(key)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._restore_from_tray()

    # -- shortcuts -------------------------------------------------------

    def _build_shortcuts(self) -> None:
        s = self._settings

        def bind(sequence: str, handler) -> None:
            action = QAction(self)
            action.setShortcut(QKeySequence(sequence))
            action.triggered.connect(handler)
            self.addAction(action)

        bind(s.shortcut_search, lambda: self.sidebar.select_page("processes"))
        bind(s.shortcut_refresh, lambda: None)  # data already refreshes continuously
        bind(s.shortcut_settings, lambda: self.sidebar.select_page("settings"))
        bind(s.shortcut_quit, self._quit_application)

        # In-app fallback: while focused, Ctrl+Shift+T also just shows
        # the window (harmless if it's already visible/global-bound).
        bind(s.shortcut_open, self._restore_from_tray)

        status = configure_global_shortcut(s.shortcut_open, "manjaro-task-manager --toggle")
        if not status.is_truly_global:
            logger.info(
                "Global shortcut '%s' could not be registered system-wide (%s). "
                "In-app shortcut still active while the window has focus.",
                s.shortcut_open, status.method.value,
            )

    # -- shutdown -------------------------------------------------------

    def _quit_application(self) -> None:
        self._force_quit = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._force_quit and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            return

        # stop_polling() owns a QTimer that lives on the worker thread;
        # calling it as a plain Python method from the UI thread would
        # violate Qt's thread-affinity rules (QTimer must be
        # started/stopped from the thread that owns it). Route the call
        # through Qt's own cross-thread invocation instead, blocking
        # until the worker thread has actually processed it.
        QMetaObject.invokeMethod(
            self._monitor_worker, "stop_polling", Qt.ConnectionType.BlockingQueuedConnection
        )
        self._monitor_thread.quit()
        self._monitor_thread.wait(2000)
        save_settings(self._settings)
        event.accept()
