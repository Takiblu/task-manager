"""
Theme system: generates Qt stylesheets (QSS) for Dark/Light modes
with a Manjaro-inspired palette (deep teal/green accent, slate
backgrounds) and rounded, card-based widgets. Never uses Manjaro's
actual logo/wordmark assets — this is an original palette only.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QPalette

from src.settings.app_settings import AppSettings


@dataclass(frozen=True)
class ThemeColors:
    background: str
    surface: str
    surface_alt: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_hover: str
    success: str
    warning: str
    danger: str


DARK_COLORS = ThemeColors(
    background="#1b1f22",
    surface="#22272b",
    surface_alt="#2a3034",
    border="#33393d",
    text_primary="#eef1f2",
    text_secondary="#9aa4a9",
    accent="#35b37e",
    accent_hover="#2f9e6f",
    success="#35b37e",
    warning="#e0a63e",
    danger="#e0563e",
)

LIGHT_COLORS = ThemeColors(
    background="#f4f6f5",
    surface="#ffffff",
    surface_alt="#eef1f0",
    border="#dfe3e1",
    text_primary="#1b1f22",
    text_secondary="#5c6a66",
    accent="#2f9e6f",
    accent_hover="#278a60",
    success="#2f9e6f",
    warning="#c4881f",
    danger="#c4432c",
)


def resolve_effective_theme(settings: AppSettings) -> str:
    """Resolve 'system' to an actual dark/light choice via Qt's palette."""
    if settings.theme in ("dark", "light"):
        return settings.theme

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        palette: QPalette = app.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        # Simple luminance heuristic to decide dark vs light.
        luminance = 0.299 * window_color.red() + 0.587 * window_color.green() + 0.114 * window_color.blue()
        return "dark" if luminance < 128 else "light"
    return "dark"


def get_colors(settings: AppSettings) -> ThemeColors:
    effective = resolve_effective_theme(settings)
    colors = DARK_COLORS if effective == "dark" else LIGHT_COLORS
    if settings.accent_color:
        colors = ThemeColors(**{**colors.__dict__, "accent": settings.accent_color})
    return colors


def build_stylesheet(settings: AppSettings) -> str:
    c = get_colors(settings)
    radius = 10

    return f"""
    * {{
        font-family: "Noto Sans", "Cantarell", sans-serif;
        font-size: 13px;
        color: {c.text_primary};
    }}

    QMainWindow, QWidget#centralWidget {{
        background-color: {c.background};
    }}

    QWidget#sidebar {{
        background-color: {c.surface};
        border-right: 1px solid {c.border};
    }}

    QPushButton#navButton {{
        text-align: left;
        padding: 10px 16px;
        border: none;
        border-radius: {radius}px;
        background-color: transparent;
        color: {c.text_secondary};
        font-weight: 500;
    }}

    QPushButton#navButton:hover {{
        background-color: {c.surface_alt};
        color: {c.text_primary};
    }}

    QPushButton#navButton:checked {{
        background-color: {c.accent};
        color: #ffffff;
    }}

    QFrame#card {{
        background-color: {c.surface};
        border: 1px solid {c.border};
        border-radius: {radius}px;
    }}

    QLabel#cardTitle {{
        color: {c.text_secondary};
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
    }}

    QLabel#cardValue {{
        color: {c.text_primary};
        font-size: 22px;
        font-weight: 700;
    }}

    QLabel#cardSubtext {{
        color: {c.text_secondary};
        font-size: 11px;
    }}

    QTableView {{
        background-color: {c.surface};
        alternate-background-color: {c.surface_alt};
        gridline-color: {c.border};
        border: 1px solid {c.border};
        border-radius: {radius}px;
        selection-background-color: {c.accent};
        selection-color: #ffffff;
    }}

    QHeaderView::section {{
        background-color: {c.surface_alt};
        color: {c.text_secondary};
        padding: 6px;
        border: none;
        border-bottom: 1px solid {c.border};
        font-weight: 600;
    }}

    QLineEdit, QComboBox, QSpinBox {{
        background-color: {c.surface_alt};
        border: 1px solid {c.border};
        border-radius: {radius - 2}px;
        padding: 6px 10px;
    }}

    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {c.accent};
    }}

    QPushButton#primaryButton {{
        background-color: {c.accent};
        color: #ffffff;
        border: none;
        border-radius: {radius - 2}px;
        padding: 8px 18px;
        font-weight: 600;
    }}

    QPushButton#primaryButton:hover {{
        background-color: {c.accent_hover};
    }}

    QPushButton#dangerButton {{
        background-color: {c.danger};
        color: #ffffff;
        border: none;
        border-radius: {radius - 2}px;
        padding: 8px 18px;
        font-weight: 600;
    }}

    QPushButton#secondaryButton {{
        background-color: transparent;
        border: 1px solid {c.border};
        border-radius: {radius - 2}px;
        padding: 8px 18px;
        color: {c.text_primary};
    }}

    QPushButton#secondaryButton:hover {{
        background-color: {c.surface_alt};
    }}

    QProgressBar {{
        background-color: {c.surface_alt};
        border: none;
        border-radius: 6px;
        height: 8px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {c.accent};
        border-radius: 6px;
    }}

    QToolTip {{
        background-color: {c.surface_alt};
        color: {c.text_primary};
        border: 1px solid {c.border};
        padding: 4px 8px;
        border-radius: 4px;
    }}

    QMenu {{
        background-color: {c.surface};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 6px 20px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {c.accent};
        color: #ffffff;
    }}
    """
