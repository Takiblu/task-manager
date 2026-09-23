"""System Information page (section 18)."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from src.system.system_info import format_duration, get_full_system_snapshot


def _format_bytes(num_bytes: float) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < step:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} PB"


class _SectionCard(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        layout.addWidget(title_label)
        self.form = QFormLayout()
        layout.addLayout(self.form)

    def add_row(self, label: str, value: str) -> None:
        self.form.addRow(label, QLabel(value))


class SystemPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 24, 24, 24)
        outer_layout.setSpacing(12)

        heading = QLabel("System Information")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        outer_layout.addWidget(heading)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.setFixedWidth(120)
        refresh_btn.clicked.connect(self.refresh)
        outer_layout.addWidget(refresh_btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll, stretch=1)

        self._content = QWidget()
        scroll.setWidget(self._content)
        self._grid = QGridLayout(self._content)
        self._grid.setSpacing(16)

        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        # Clear existing cards.
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        snapshot = get_full_system_snapshot()

        os_card = _SectionCard("Operating System")
        os_card.add_row("Distribution", snapshot.identity.distribution)
        os_card.add_row("Version", snapshot.identity.distribution_version)
        os_card.add_row("Kernel", snapshot.identity.kernel)
        os_card.add_row("Architecture", snapshot.identity.architecture)
        os_card.add_row("Hostname", snapshot.identity.hostname)
        os_card.add_row("Uptime", format_duration(snapshot.uptime_seconds))
        self._grid.addWidget(os_card, 0, 0)

        cpu = snapshot.cpu
        cpu_card = _SectionCard("CPU")
        cpu_card.add_row("Model", cpu.model_name)
        cpu_card.add_row("Physical Cores", str(cpu.physical_cores))
        cpu_card.add_row("Logical Threads", str(cpu.logical_cores))
        freq = f"{cpu.current_freq_mhz / 1000:.2f} GHz" if cpu.current_freq_mhz else "N/A"
        cpu_card.add_row("Frequency", freq)
        self._grid.addWidget(cpu_card, 0, 1)

        gpu_card = _SectionCard("GPU")
        if snapshot.gpus:
            for i, gpu in enumerate(snapshot.gpus):
                gpu_card.add_row(f"GPU {i}", f"{gpu.name} ({gpu.vendor})")
        else:
            gpu_card.add_row("GPU", "No supported GPU detected")
        self._grid.addWidget(gpu_card, 1, 0)

        mem = snapshot.memory
        mem_card = _SectionCard("Memory")
        mem_card.add_row("Total", _format_bytes(mem.total_bytes))
        mem_card.add_row("Used", _format_bytes(mem.used_bytes))
        mem_card.add_row("Available", _format_bytes(mem.available_bytes))
        mem_card.add_row("Swap Total", _format_bytes(mem.swap_total_bytes))
        mem_card.add_row("Swap Used", _format_bytes(mem.swap_used_bytes))
        self._grid.addWidget(mem_card, 1, 1)

        storage_card = _SectionCard("Storage")
        for partition in snapshot.partitions:
            storage_card.add_row(
                partition.mount_point,
                f"{_format_bytes(partition.used_bytes)} / {_format_bytes(partition.total_bytes)} "
                f"({partition.percent:.0f}%) — {partition.filesystem}",
            )
        self._grid.addWidget(storage_card, 2, 0)

        desktop_card = _SectionCard("Desktop")
        desktop_card.add_row("Desktop Environment", snapshot.identity.desktop_environment)
        desktop_card.add_row("Window Manager", snapshot.identity.window_manager)
        desktop_card.add_row("Display Server", snapshot.identity.display_server)
        self._grid.addWidget(desktop_card, 2, 1)
