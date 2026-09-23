"""Process Properties dialog (section 11)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from src.process.process_properties import ProcessProperties


def _kv_row(form: QFormLayout, label: str, value: str) -> None:
    value_label = QLabel(value or "--")
    value_label.setWordWrap(True)
    value_label.setTextInteractionFlags(
        value_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
    )
    form.addRow(label, value_label)


class PropertiesDialog(QDialog):
    def __init__(self, props: ProcessProperties, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Properties — {props.name} (PID {props.pid})")
        self.resize(560, 480)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        general_tab = QWidget()
        form = QFormLayout(general_tab)
        _kv_row(form, "Name", props.name)
        _kv_row(form, "PID", str(props.pid))
        _kv_row(form, "PPID", str(props.ppid))
        _kv_row(form, "User", props.username)
        _kv_row(form, "Executable Path", props.exe or "N/A")
        _kv_row(form, "Command Line", " ".join(props.cmdline) or "N/A")
        _kv_row(form, "Working Directory", props.cwd or "N/A (permission denied)")
        _kv_row(form, "CPU", f"{props.cpu_percent:.1f}%")
        _kv_row(form, "Memory (RSS)", f"{props.memory_rss_bytes / (1024*1024):.1f} MB")
        _kv_row(form, "Memory (VMS)", f"{props.memory_vms_bytes / (1024*1024):.1f} MB")
        _kv_row(form, "Threads", str(props.num_threads))
        _kv_row(form, "Priority (nice)", str(props.nice))
        _kv_row(form, "Status", props.status.replace("-", " ").title())
        import datetime
        start = "--"
        if props.create_time:
            try:
                start = datetime.datetime.fromtimestamp(props.create_time).strftime("%Y-%m-%d %H:%M:%S")
            except (OverflowError, OSError, ValueError):
                pass
        _kv_row(form, "Start Time", start)
        tabs.addTab(general_tab, "General")

        env_tab = QWidget()
        env_layout = QVBoxLayout(env_tab)
        env_text = QTextEdit()
        env_text.setReadOnly(True)
        if props.environment_available and props.environment:
            env_text.setPlainText(
                "\n".join(f"{k}={v}" for k, v in sorted(props.environment.items()))
            )
        else:
            env_text.setPlainText("Environment not available (permission denied).")
        env_layout.addWidget(env_text)
        tabs.addTab(env_tab, "Environment")

        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        files_text = QTextEdit()
        files_text.setReadOnly(True)
        if props.open_files_available:
            files_text.setPlainText("\n".join(props.open_files) or "No open files reported.")
        else:
            files_text.setPlainText("Open files not available (permission denied).")
        files_layout.addWidget(files_text)
        tabs.addTab(files_tab, "Open Files")
