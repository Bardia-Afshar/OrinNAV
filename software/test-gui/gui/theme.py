

import pyqtgraph as pg
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QLabel

BG = "#0d1117"
SURFACE = "#141a22"
CARD = "#1a212b"
CARD_HOVER = "#212a36"
INPUT = "#0f141b"
BORDER = "#2a3441"
TEXT = "#e6edf3"
MUTED = "#8b98a8"
SUBTLE = "#5c6878"

ACCENT = "#3b82f6"
ACCENT_HOVER = "#5b97f8"
ACCENT_PRESSED = "#2f6bd0"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
DANGER = "#ef4444"

UI_FONT = "Ubuntu"
MONO_FONT = "DejaVu Sans Mono"

AXIS_COLORS = {"X": "#f87171", "Y": "#4ade80", "Z": "#60a5fa"}

SNR_COLORS = {
    "strong": QColor(SUCCESS),
    "ok": QColor("#a3e635"),
    "weak": QColor(WARNING),
    "poor": QColor(DANGER),
}

MAP_BACKGROUND = QColor(SURFACE)
MAP_TILE_PLACEHOLDER = QColor(CARD)

STYLESHEET = f"""
* {{
    font-family: "{UI_FONT}";
    font-size: 10pt;
    color: {TEXT};
}}

QMainWindow, QWidget#page {{
    background: {BG};
}}

QWidget#header {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QLabel#appTitle {{
    font-size: 15pt;
    font-weight: bold;
}}
QLabel#appSubtitle {{
    color: {MUTED};
}}

QTabWidget::pane {{
    border: none;
    background: {BG};
}}
QTabWidget::tab-bar {{
    left: 16px;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    font-weight: bold;
    padding: 10px 22px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}

QGroupBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 26px;
    padding: 12px 10px 10px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px;
    top: 4px;
    color: {MUTED};
    font-size: 9pt;
    font-weight: bold;
}}
QGroupBox QLabel {{
    color: {MUTED};
    background: transparent;
}}
QLabel#value {{
    color: {TEXT};
    font-family: "{MONO_FONT}";
}}
QLabel#bigValue {{
    color: {TEXT};
    font-family: "{MONO_FONT}";
    font-size: 18pt;
}}
QLabel#axisTag {{
    font-weight: bold;
    font-size: 11pt;
}}

QLabel#status {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-left: 4px solid {MUTED};
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: bold;
}}
QLabel#status[state="ok"] {{
    border-left-color: {SUCCESS};
    color: {SUCCESS};
}}
QLabel#status[state="pending"] {{
    border-left-color: {WARNING};
    color: {WARNING};
}}
QLabel#status[state="error"] {{
    border-left-color: {DANGER};
    color: {DANGER};
}}

QLineEdit, QSpinBox {{
    background: {INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {SUBTLE};
    background: {SURFACE};
}}

QPushButton {{
    background: {CARD_HOVER};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}}
QPushButton:hover {{
    border-color: {MUTED};
}}
QPushButton:disabled {{
    color: {SUBTLE};
    background: {SURFACE};
    border-color: {BORDER};
}}
QPushButton#primary {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: white;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#primary:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton#primary:disabled {{
    background: {SURFACE};
    border-color: {BORDER};
    color: {SUBTLE};
}}
QPushButton#danger {{
    color: {DANGER};
    border-color: {DANGER};
    background: transparent;
}}
QPushButton#danger:hover {{
    background: rgba(239, 68, 68, 0.12);
}}
QPushButton#danger:disabled {{
    color: {SUBTLE};
    border-color: {BORDER};
}}

QCheckBox {{
    color: {TEXT};
    spacing: 8px;
    background: transparent;
}}

QTableWidget {{
    background: {CARD};
    alternate-background-color: {SURFACE};
    border: none;
    gridline-color: transparent;
    font-family: "{MONO_FONT}";
    font-size: 9pt;
}}
QHeaderView::section {{
    background: {CARD};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 2px;
    font-weight: bold;
    font-size: 8pt;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {SUBTLE};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QToolTip {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
"""


def apply(app):
 
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(INPUT))
    palette.setColor(QPalette.AlternateBase, QColor(SURFACE))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(CARD))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ToolTipBase, QColor(CARD))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.PlaceholderText, QColor(SUBTLE))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(SUBTLE))
    app.setPalette(palette)
    app.setFont(QFont(UI_FONT, 10))
    app.setStyleSheet(STYLESHEET)

    pg.setConfigOption("background", CARD)
    pg.setConfigOption("foreground", MUTED)
    pg.setConfigOption("antialias", False)


def set_status(label, text, state):
   
    label.setText(text)
    if label.property("state") == state:
        return
    label.setProperty("state", state)
   
    label.style().unpolish(label)
    label.style().polish(label)


def status_label(text, state="idle"):
    label = QLabel()
    label.setObjectName("status")
    label.setWordWrap(True)
    set_status(label, text, state)
    return label


def value_label(text="--", big=False):
    label = QLabel(text)
    label.setObjectName("bigValue" if big else "value")
    return label
