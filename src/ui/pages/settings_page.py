"""Settings page (section 19): appearance, performance, process, startup, notifications."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.settings.app_settings import (
    MAX_UPDATE_INTERVAL_MS,
    MIN_UPDATE_INTERVAL_MS,
    AppSettings,
    save_settings,
)
from src.utils.logger import get_logger
from src.utils.safe_exec import run_argv

logger = get_logger("ui.settings_page")

_AUTOSTART_UNIT = "manjaro-task-manager.service"


def _apply_start_with_system(enabled: bool) -> None:
    """
    Enable/disable the packaged systemd --user unit. Runs entirely in
    user scope (no polkit/root needed) since --user units are managed
    per-login-session by design.
    """
    action = "enable" if enabled else "disable"
    result = run_argv(["systemctl", "--user", action, "--now", _AUTOSTART_UNIT], timeout=10.0)
    if not result.success:
        logger.warning("Failed to %s autostart unit: %s", action, result.stderr.strip())


class SettingsPage(QWidget):
    settings_changed = Signal(object)  # emits the updated AppSettings

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 24, 24, 24)
        outer_layout.setSpacing(12)

        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        outer_layout.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll, stretch=1)

        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)

        content_layout.addWidget(self._build_appearance_group())
        content_layout.addWidget(self._build_performance_group())
        content_layout.addWidget(self._build_process_group())
        content_layout.addWidget(self._build_startup_group())
        content_layout.addWidget(self._build_notifications_group())
        content_layout.addStretch(1)

    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("Appearance")
        form = QFormLayout(group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Dark", "Light"])
        self.theme_combo.setCurrentText(self._settings.theme.capitalize())
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        form.addRow("Theme", self.theme_combo)

        return group

    def _build_performance_group(self) -> QGroupBox:
        group = QGroupBox("Performance")
        form = QFormLayout(group)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(MIN_UPDATE_INTERVAL_MS, MAX_UPDATE_INTERVAL_MS)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setValue(self._settings.update_interval_ms)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        form.addRow("Update Interval", self.interval_spin)

        self.animations_check = QCheckBox("Enable animations")
        self.animations_check.setChecked(self._settings.animations_enabled)
        self.animations_check.toggled.connect(self._on_animations_toggled)
        form.addRow(self.animations_check)

        self.history_spin = QSpinBox()
        self.history_spin.setRange(30, 600)
        self.history_spin.setValue(self._settings.chart_history_points)
        self.history_spin.valueChanged.connect(self._on_history_changed)
        form.addRow("Chart History (points)", self.history_spin)

        return group

    def _build_process_group(self) -> QGroupBox:
        group = QGroupBox("Process")
        form = QFormLayout(group)

        self.confirm_end_check = QCheckBox("Confirm End Task")
        self.confirm_end_check.setChecked(self._settings.confirm_end_task)
        self.confirm_end_check.toggled.connect(lambda v: self._update_and_save("confirm_end_task", v))
        form.addRow(self.confirm_end_check)

        self.confirm_force_check = QCheckBox("Confirm Force Kill")
        self.confirm_force_check.setChecked(self._settings.confirm_force_kill)
        self.confirm_force_check.toggled.connect(lambda v: self._update_and_save("confirm_force_kill", v))
        form.addRow(self.confirm_force_check)

        self.show_system_check = QCheckBox("Show System Processes")
        self.show_system_check.setChecked(self._settings.show_system_processes)
        self.show_system_check.toggled.connect(self._on_show_system_toggled)
        form.addRow(self.show_system_check)

        self.show_kernel_check = QCheckBox("Show Kernel Threads")
        self.show_kernel_check.setChecked(self._settings.show_kernel_threads)
        self.show_kernel_check.toggled.connect(self._on_show_kernel_toggled)
        form.addRow(self.show_kernel_check)

        return group

    def _build_startup_group(self) -> QGroupBox:
        group = QGroupBox("Startup")
        form = QFormLayout(group)

        self.start_with_system_check = QCheckBox("Start Task Manager on login")
        self.start_with_system_check.setChecked(self._settings.start_with_system)
        self.start_with_system_check.toggled.connect(self._on_start_with_system_toggled)
        form.addRow(self.start_with_system_check)

        self.start_minimized_check = QCheckBox("Start minimized")
        self.start_minimized_check.setChecked(self._settings.start_minimized)
        self.start_minimized_check.toggled.connect(lambda v: self._update_and_save("start_minimized", v))
        form.addRow(self.start_minimized_check)

        self.start_in_tray_check = QCheckBox("Start in system tray")
        self.start_in_tray_check.setChecked(self._settings.start_in_tray)
        self.start_in_tray_check.toggled.connect(lambda v: self._update_and_save("start_in_tray", v))
        form.addRow(self.start_in_tray_check)

        return group

    def _build_notifications_group(self) -> QGroupBox:
        group = QGroupBox("Notifications")
        form = QFormLayout(group)

        self.notifications_check = QCheckBox("Enable notifications")
        self.notifications_check.setChecked(self._settings.notifications_enabled)
        self.notifications_check.toggled.connect(lambda v: self._update_and_save("notifications_enabled", v))
        form.addRow(self.notifications_check)

        self.notify_terminated_check = QCheckBox("Process terminated")
        self.notify_terminated_check.setChecked(self._settings.notify_process_terminated)
        self.notify_terminated_check.toggled.connect(
            lambda v: self._update_and_save("notify_process_terminated", v)
        )
        form.addRow(self.notify_terminated_check)

        self.notify_service_check = QCheckBox("Service changed")
        self.notify_service_check.setChecked(self._settings.notify_service_changed)
        self.notify_service_check.toggled.connect(lambda v: self._update_and_save("notify_service_changed", v))
        form.addRow(self.notify_service_check)

        self.notify_errors_check = QCheckBox("Errors")
        self.notify_errors_check.setChecked(self._settings.notify_errors)
        self.notify_errors_check.toggled.connect(lambda v: self._update_and_save("notify_errors", v))
        form.addRow(self.notify_errors_check)

        return group

    # -- change handlers -------------------------------------------------

    def _update_and_save(self, field_name: str, value) -> None:
        setattr(self._settings, field_name, value)
        self._settings.clamp()
        save_settings(self._settings)
        self.settings_changed.emit(self._settings)

    def _on_theme_changed(self, text: str) -> None:
        self._update_and_save("theme", text.lower())

    def _on_interval_changed(self, value: int) -> None:
        self._update_and_save("update_interval_ms", value)

    def _on_animations_toggled(self, value: bool) -> None:
        self._update_and_save("animations_enabled", value)

    def _on_history_changed(self, value: int) -> None:
        self._update_and_save("chart_history_points", value)

    def _on_show_system_toggled(self, value: bool) -> None:
        self._update_and_save("show_system_processes", value)

    def _on_show_kernel_toggled(self, value: bool) -> None:
        self._update_and_save("show_kernel_threads", value)

    def _on_start_with_system_toggled(self, value: bool) -> None:
        _apply_start_with_system(value)
        self._update_and_save("start_with_system", value)
