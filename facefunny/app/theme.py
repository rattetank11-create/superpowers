"""Colours, fonts and the Qt stylesheet of the dark esports look."""

from PySide6.QtGui import QColor, QFont, QFontDatabase

BG = "#07080b"
BG_PANEL = "#0e1117"
BG_PANEL_2 = "#141922"
BORDER = "#1f2633"
TEXT = "#e9edf5"
TEXT_DIM = "#7d8799"
CT_BLUE = "#3d8bff"
CT_BLUE_SOFT = "#1d3f78"
T_RED = "#ff3d4f"
T_RED_SOFT = "#6e1b24"
ACCENT = "#ffffff"
OK_GREEN = "#36e39a"
WARN = "#ffc24a"

C_CT = QColor(CT_BLUE)
C_T = QColor(T_RED)

# Fonts that exist on most systems, in order of preference.
_FAMILIES = ["Bahnschrift", "Rajdhani", "Inter", "Segoe UI", "Roboto", "Helvetica Neue", "Arial"]


def font_families() -> list:
    available = set(QFontDatabase.families())
    picked = [f for f in _FAMILIES if f in available]
    return picked or ["Sans Serif"]


def make_font(size: float, weight: QFont.Weight = QFont.Weight.Normal, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(font_families())
    f.setPointSizeF(size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def stylesheet() -> str:
    fam = ", ".join(f'"{f}"' for f in font_families())
    return f"""
    QWidget {{
        background: transparent;
        color: {TEXT};
        font-family: {fam};
        font-size: 10pt;
    }}
    QMainWindow, #Root {{ background: {BG}; }}

    QLineEdit#ServerInput {{
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 14px 18px;
        font-size: 14pt;
        color: {TEXT};
        selection-background-color: {CT_BLUE};
    }}
    QLineEdit#ServerInput:focus {{ border: 1px solid {CT_BLUE}; background: {BG_PANEL_2}; }}
    QLineEdit#ServerInput[error="true"] {{ border: 1px solid {T_RED}; }}

    QPushButton#ConnectButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {CT_BLUE}, stop:1 #6f5bff);
        border: none;
        border-radius: 12px;
        padding: 14px 18px;
        font-size: 13pt;
        font-weight: 700;
        letter-spacing: 4px;
        color: white;
    }}
    QPushButton#ConnectButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5c9dff, stop:1 #8a7aff);
    }}
    QPushButton#ConnectButton:pressed {{ background: #2f6fd6; }}
    QPushButton#ConnectButton:disabled {{ background: {BORDER}; color: {TEXT_DIM}; }}

    QFrame#Panel {{
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}
    QLabel#Logo {{ font-size: 17pt; font-weight: 800; letter-spacing: 5px; color: {ACCENT}; }}
    QLabel#Chip {{
        background: {BG_PANEL_2};
        border: 1px solid {BORDER};
        border-radius: 9px;
        padding: 5px 11px;
        font-size: 9pt;
        font-weight: 600;
        letter-spacing: 1px;
        color: {TEXT};
    }}
    QLabel#Dim {{ color: {TEXT_DIM}; font-size: 9pt; letter-spacing: 1px; }}

    QPushButton#ToolButton {{
        background: {BG_PANEL_2};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 8px 16px;
        font-size: 9pt;
        font-weight: 700;
        letter-spacing: 2px;
        color: {TEXT};
    }}
    QPushButton#ToolButton:hover {{ border: 1px solid {CT_BLUE}; color: white; background: #18202c; }}
    QPushButton#ToolButton:pressed {{ background: #0c1018; }}
    QPushButton#ToolButton[danger="true"]:hover {{ border: 1px solid {T_RED}; }}

    QToolTip {{
        background: {BG_PANEL_2};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 5px 8px;
        font-weight: 600;
    }}
    """
