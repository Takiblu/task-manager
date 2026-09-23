"""Performance page (section 13-14): detailed per-resource live charts."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from src.core.monitor_worker import MonitorSnapshot
from src.ui.widgets.live_chart import LiveLineChart


def _format_bytes(num_bytes: float) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < step:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} PB"


class _ChartSection(QWidget):
    def __init__(self, title: str, y_min: float = 0, y_max: float = 100, color: str = "#35b37e") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header_row = QVBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: 600;")
        self.value_label = QLabel("--")
        self.value_label.setStyleSheet("color: #9aa4a9; font-size: 12px;")
        header_row.addWidget(self.title_label)
        header_row.addWidget(self.value_label)
        layout.addLayout(header_row)

        self.chart = LiveLineChart(y_min=y_min, y_max=y_max, line_color=color)
        self.chart.setMinimumHeight(90)
        layout.addWidget(self.chart)


class PerformancePage(QWidget):
    def __init__(self, chart_history_points: int = 120, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        heading = QLabel("Performance")
        heading.setStyleSheet("font-size: 20px; font-weight: 700;")
        root_layout.addWidget(heading)

        grid = QGridLayout()
        grid.setSpacing(20)
        root_layout.addLayout(grid)

        self.cpu_section = _ChartSection("CPU", 0, 100, "#35b37e")
        self.memory_section = _ChartSection("Memory", 0, 100, "#4e8fe0")
        self.gpu_section = _ChartSection("GPU", 0, 100, "#e0a63e")
        self.disk_section = _ChartSection("Disk I/O", 0, 100, "#c46be0")
        self.network_section = _ChartSection("Network", 0, 100, "#e0563e")

        grid.addWidget(self.cpu_section, 0, 0)
        grid.addWidget(self.memory_section, 0, 1)
        grid.addWidget(self.gpu_section, 1, 0)
        grid.addWidget(self.disk_section, 1, 1)
        grid.addWidget(self.network_section, 2, 0, 1, 2)

        root_layout.addStretch(1)

        self.set_history_length(chart_history_points)

        self._disk_peak = 1.0
        self._net_peak = 1.0

    def set_history_length(self, points: int) -> None:
        for section in (self.cpu_section, self.memory_section, self.gpu_section,
                         self.disk_section, self.network_section):
            section.chart.set_max_points(points)

    def update_snapshot(self, snapshot: MonitorSnapshot) -> None:
        cpu = snapshot.cpu
        self.cpu_section.chart.push_value(cpu.total_percent)
        temp_text = f"  •  {cpu.temperature_c:.0f}°C" if cpu.temperature_c else ""
        self.cpu_section.value_label.setText(
            f"{cpu.total_percent:.0f}%  •  Load {cpu.load_avg_1:.2f}{temp_text}"
        )

        mem = snapshot.memory
        self.memory_section.chart.push_value(mem.percent)
        self.memory_section.value_label.setText(
            f"{_format_bytes(mem.used_bytes)} / {_format_bytes(mem.total_bytes)}"
        )

        if snapshot.gpus:
            gpu = snapshot.gpus[0]
            usage = gpu.usage_percent or 0.0
            self.gpu_section.chart.push_value(usage)
            vram = (
                f"{gpu.vram_used_mb / 1024:.1f} / {gpu.vram_total_mb / 1024:.1f} GB"
                if gpu.vram_used_mb is not None and gpu.vram_total_mb else gpu.name
            )
            self.gpu_section.value_label.setText(f"{gpu.name}  •  {vram}")
        else:
            self.gpu_section.value_label.setText("No supported GPU detected")

        io = snapshot.disk_io
        total_io = io.read_bytes_per_sec + io.write_bytes_per_sec
        self._disk_peak = max(self._disk_peak, total_io, 1.0)
        self.disk_section.chart.set_range(0, self._disk_peak)
        self.disk_section.chart.push_value(total_io)
        self.disk_section.value_label.setText(
            f"R {_format_bytes(io.read_bytes_per_sec)}/s  •  W {_format_bytes(io.write_bytes_per_sec)}/s"
        )

        total_down = sum(n.download_bytes_per_sec for n in snapshot.network.values())
        total_up = sum(n.upload_bytes_per_sec for n in snapshot.network.values())
        total_net = total_down + total_up
        self._net_peak = max(self._net_peak, total_net, 1.0)
        self.network_section.chart.set_range(0, self._net_peak)
        self.network_section.chart.push_value(total_net)
        self.network_section.value_label.setText(
            f"↓ {_format_bytes(total_down)}/s  •  ↑ {_format_bytes(total_up)}/s"
        )
