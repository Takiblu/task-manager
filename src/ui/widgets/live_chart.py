"""
Lightweight rolling line-chart widget, hand-drawn with QPainter.

Deliberately avoids QtCharts (not always packaged the same way across
distros) and avoids re-laying-out any Qt widget tree on every tick —
`push_value()` just appends to a bounded deque and calls `update()`,
which triggers a single paintEvent. This keeps per-tick cost to a
single lightweight repaint instead of a widget-heavy chart library,
addressing the "charts must not cause high CPU usage" requirement.
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class LiveLineChart(QWidget):
    def __init__(
        self,
        max_points: int = 120,
        y_min: float = 0.0,
        y_max: float = 100.0,
        line_color: str = "#35b37e",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._max_points = max_points
        self._values: deque[float] = deque(maxlen=max_points)
        self._y_min = y_min
        self._y_max = y_max
        self._line_color = QColor(line_color)
        self.setMinimumHeight(80)

    def set_range(self, y_min: float, y_max: float) -> None:
        self._y_min = y_min
        self._y_max = y_max

    def set_max_points(self, max_points: int) -> None:
        self._max_points = max(10, max_points)
        new_deque: deque[float] = deque(self._values, maxlen=self._max_points)
        self._values = new_deque

    def push_value(self, value: float) -> None:
        clamped = max(self._y_min, min(self._y_max, value))
        self._values.append(clamped)
        self.update()

    def clear(self) -> None:
        self._values.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, Qt.GlobalColor.transparent)

        if len(self._values) < 2:
            painter.end()
            return

        span = max(self._y_max - self._y_min, 1e-6)
        width = rect.width()
        height = rect.height()
        count = len(self._values)
        step_x = width / max(count - 1, 1)

        points: list[QPointF] = []
        for i, value in enumerate(self._values):
            x = i * step_x
            normalized = (value - self._y_min) / span
            y = height - (normalized * height)
            points.append(QPointF(x, y))

        line_path = QPainterPath()
        line_path.moveTo(points[0])
        for point in points[1:]:
            line_path.lineTo(point)

        fill_path = QPainterPath(line_path)
        fill_path.lineTo(points[-1].x(), height)
        fill_path.lineTo(points[0].x(), height)
        fill_path.closeSubpath()

        gradient = QLinearGradient(0, 0, 0, height)
        fill_color_top = QColor(self._line_color)
        fill_color_top.setAlpha(90)
        fill_color_bottom = QColor(self._line_color)
        fill_color_bottom.setAlpha(0)
        gradient.setColorAt(0.0, fill_color_top)
        gradient.setColorAt(1.0, fill_color_bottom)

        painter.fillPath(fill_path, gradient)

        pen = QPen(self._line_color)
        pen.setWidthF(2.0)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(line_path)

        painter.end()
