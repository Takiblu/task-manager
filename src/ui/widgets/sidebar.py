"""Left-hand navigation sidebar with the required page list."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget

SIDEBAR_PAGES = (
    ("overview", "Overview"),
    ("processes", "Processes"),
    ("applications", "Applications"),
    ("performance", "Performance"),
    ("services", "Services"),
    ("startup", "Startup Apps"),
    ("users", "Users"),
    ("system", "System"),
    ("settings", "Settings"),
)


class Sidebar(QWidget):
    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for key, label in SIDEBAR_PAGES:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked, k=key: self._on_clicked(k))
            self._group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        self.select_page("overview")

    def _on_clicked(self, key: str) -> None:
        self.page_selected.emit(key)

    def select_page(self, key: str) -> None:
        button = self._buttons.get(key)
        if button is not None:
            button.setChecked(True)
            self.page_selected.emit(key)
