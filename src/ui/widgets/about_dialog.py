"""About dialog (section 32)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

APP_VERSION = "1.0.0"
APP_LICENSE = "GPL-3.0-or-later"
APP_GITHUB_URL = "https://github.com/Takiblu"
APP_AUTHOR = "Taki"


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Manjaro Task Manager")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)

        title = QLabel("Manjaro Task Manager")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        layout.addWidget(QLabel(f"Version: {APP_VERSION}"))
        layout.addWidget(QLabel(f"License: {APP_LICENSE}"))
        layout.addWidget(QLabel(f"Author: {APP_AUTHOR}"))

        link = QLabel(f'<a href="{APP_GITHUB_URL}">{APP_GITHUB_URL}</a>')
        link.setOpenExternalLinks(True)
        layout.addWidget(link)

        layout.addWidget(QLabel("Built with PySide6 (Qt6) and psutil."))

        import platform as _platform
        layout.addWidget(QLabel(f"Python {_platform.python_version()} — Qt for Python"))
