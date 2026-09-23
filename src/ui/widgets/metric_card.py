"""Reusable "card" widget used on the Overview page (CPU/RAM/GPU/Disk/Network)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout


class MetricCard(QFrame):
    """
    A small card: title, big value, optional subtext line, optional
    progress bar. Designed to be updated in-place (setText/setValue)
    on every poll tick rather than recreated, to keep updates cheap.
    """

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("cardTitle")

        self._value_label = QLabel("--")
        self._value_label.setObjectName("cardValue")

        self._subtext_label = QLabel("")
        self._subtext_label.setObjectName("cardSubtext")
        self._subtext_label.setWordWrap(True)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.hide()

        layout.addWidget(self._title_label)
        layout.addWidget(self._value_label)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._subtext_label)
        layout.addStretch(1)

    def set_value(self, text: str) -> None:
        self._value_label.setText(text)

    def set_subtext(self, text: str) -> None:
        self._subtext_label.setText(text)

    def set_progress(self, percent: float | None) -> None:
        if percent is None:
            self._progress_bar.hide()
            return
        self._progress_bar.show()
        self._progress_bar.setValue(max(0, min(100, int(percent))))
