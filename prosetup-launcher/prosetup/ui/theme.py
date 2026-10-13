"""Тёмная киберспортивная тема с оранжевыми акцентами FACEIT."""

BG = "#0b0c0e"
PANEL = "#121317"
CARD = "#15171b"
CARD_HOVER = "#191b20"
BORDER = "#24272d"
TEXT = "#eceef1"
MUTED = "#8b9099"
DIM = "#5f646d"
ACCENT = "#ff5500"
ACCENT_HOVER = "#ff6d24"
ACCENT_PRESSED = "#d94800"
GREEN = "#3ddc84"
AMBER = "#ffb020"
RED = "#ff5f61"

HEADING_FONT = '"Bahnschrift SemiBold", "Bahnschrift", "Segoe UI Semibold", "Segoe UI", sans-serif'

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QWidget#root, QDialog {{ background: {BG}; }}
QWidget#cardsHost, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea {{ border: none; }}

QLabel#logo {{ font-family: {HEADING_FONT}; font-size: 20pt; font-weight: 700; }}
QLabel#tagline {{ color: {MUTED}; font-size: 8.5pt; font-weight: 600; }}
QLabel#sectionTitle {{ color: {MUTED}; font-family: {HEADING_FONT}; font-size: 9.5pt; font-weight: 700; }}
QLabel#hint {{ color: {DIM}; font-size: 8.5pt; }}
QLabel#heroStatus {{ color: {MUTED}; font-size: 9.5pt; }}
QLabel#selection {{ color: {ACCENT}; font-size: 9.5pt; font-weight: 600; }}

QFrame#hero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #22150d, stop:0.45 #141518, stop:1 #101114);
    border: 1px solid {BORDER};
    border-radius: 16px;
}}

QPushButton#launchButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff6a1a, stop:1 #ff4600);
    color: white;
    font-family: {HEADING_FONT};
    font-size: 17pt;
    font-weight: 700;
    border: none;
    border-radius: 12px;
    padding: 14px 28px;
}}
QPushButton#launchButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff7f3a, stop:1 #ff5a14);
}}
QPushButton#launchButton:pressed {{
    background: {ACCENT_PRESSED};
    padding-top: 16px; padding-bottom: 12px;
}}
QPushButton#launchButton:disabled {{ background: #3a2518; color: #b58f78; }}

QPushButton#secondary {{
    background: #1a1c21;
    border: 1px solid #2b2e35;
    border-radius: 9px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton#secondary:hover {{ border-color: {ACCENT}; color: white; background: #1f2127; }}
QPushButton#secondary:pressed {{ background: #131418; padding-top: 8px; padding-bottom: 6px; }}
QPushButton#secondary:disabled {{ color: {DIM}; border-color: #1f2126; }}

QPushButton#accentOutline {{
    background: rgba(255, 85, 0, 0.10);
    border: 1px solid {ACCENT};
    border-radius: 9px;
    padding: 7px 14px;
    color: #ffb48a;
    font-weight: 700;
}}
QPushButton#accentOutline:hover {{ background: {ACCENT}; color: white; }}
QPushButton#accentOutline:pressed {{ background: {ACCENT_PRESSED}; padding-top: 8px; padding-bottom: 6px; }}
QPushButton#accentOutline:disabled {{ background: transparent; border-color: #3a2a20; color: #6b5547; }}

QPushButton#cardLaunch {{
    background: transparent;
    border: 1px solid {ACCENT};
    border-radius: 8px;
    padding: 5px 14px;
    color: #ff8a4c;
    font-weight: 700;
}}
QPushButton#cardLaunch:hover {{ background: {ACCENT}; color: white; }}
QPushButton#cardLaunch:pressed {{ background: {ACCENT_PRESSED}; padding-top: 6px; padding-bottom: 4px; }}
QPushButton#cardLaunch:disabled {{ border-color: #33261e; color: #5c4a3f; }}

QPushButton#cardTool {{
    background: #1c1e23;
    border: 1px solid #2a2d33;
    border-radius: 8px;
    padding: 5px 10px;
    color: {MUTED};
}}
QPushButton#cardTool:hover {{ color: white; border-color: #4a4e57; }}
QPushButton#cardTool:pressed {{ background: #141518; }}

QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#card:hover {{ background: {CARD_HOVER}; border-color: #3b2b21; }}
QLabel#cardTitle {{ font-family: {HEADING_FONT}; font-size: 12.5pt; font-weight: 700; color: #f6f6f7; }}
QLabel#cardTitle[off="true"] {{ color: {DIM}; }}
QLabel#cardSubtitle {{ color: {MUTED}; font-size: 9pt; }}
QLabel#cardPath {{ color: {DIM}; font-family: "Cascadia Mono", "Consolas", monospace; font-size: 8.5pt; }}
QLabel#monogram {{
    color: white;
    font-family: {HEADING_FONT};
    font-size: 12pt;
    font-weight: 700;
    border-radius: 10px;
}}

QLabel#badge {{ border-radius: 10px; padding: 3px 10px; font-size: 8.5pt; font-weight: 700; }}
QLabel#badge[state="running"]  {{ background: rgba(61, 220, 132, 0.13); color: {GREEN}; }}
QLabel#badge[state="starting"] {{ background: rgba(255, 176, 32, 0.15); color: {AMBER}; }}
QLabel#badge[state="idle"]     {{ background: rgba(255, 255, 255, 0.06); color: #a6aab2; }}
QLabel#badge[state="notfound"] {{ background: rgba(255, 95, 97, 0.14); color: {RED}; }}

QProgressBar#progress {{ background: #1d1f24; border: none; border-radius: 2px; }}
QProgressBar#progress::chunk {{ background: {ACCENT}; border-radius: 2px; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2a2d33; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ height: 0; background: none; }}

QToolTip {{ background: #1b1d22; color: {TEXT}; border: 1px solid {ACCENT}; padding: 5px; }}

QMenu {{ background: #16171b; border: 1px solid #2a2d33; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::separator {{ height: 1px; background: #2a2d33; margin: 4px 8px; }}

QFrame#toast {{
    background: #1a1c21;
    border: 1px solid #2c2f36;
    border-left: 4px solid {ACCENT};
    border-radius: 10px;
}}
QFrame#toast[kind="success"] {{ border-left-color: {GREEN}; }}
QFrame#toast[kind="error"]   {{ border-left-color: {RED}; }}
QFrame#toast[kind="warning"] {{ border-left-color: {AMBER}; }}
QLabel#toastTitle {{ font-weight: 700; font-size: 10pt; }}
QLabel#toastText {{ color: #b9bdc4; font-size: 9pt; }}

/* --- диалог настроек --- */
QFrame#panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLineEdit, QDoubleSpinBox {{
    background: #0f1013;
    border: 1px solid #2a2d33;
    border-radius: 7px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QDoubleSpinBox {{ padding-right: 20px; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 18px; border: none; background: transparent;
}}
QDoubleSpinBox::up-button {{ subcontrol-position: top right; }}
QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; }}
QDoubleSpinBox::up-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid {MUTED};
}}
QDoubleSpinBox::down-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {MUTED};
}}
QDoubleSpinBox::up-arrow:hover {{ border-bottom-color: {ACCENT}; }}
QDoubleSpinBox::down-arrow:hover {{ border-top-color: {ACCENT}; }}
QComboBox {{
    background: #0f1013; border: 1px solid #2a2d33; border-radius: 7px; padding: 6px 10px; min-width: 220px;
}}
QComboBox:hover, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: #16171b; border: 1px solid #2a2d33; selection-background-color: {ACCENT}; outline: none;
}}
QLabel#ok {{ color: {GREEN}; font-size: 8.5pt; }}
QLabel#bad {{ color: {RED}; font-size: 8.5pt; }}
QLabel#info {{ color: {MUTED}; font-size: 8.5pt; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a3e46; background: #0f1013; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QMessageBox {{ background: {PANEL}; }}
QMessageBox QPushButton, QDialogButtonBox QPushButton {{
    background: #1a1c21; border: 1px solid #2b2e35; border-radius: 8px; padding: 6px 16px; min-width: 80px;
}}
QMessageBox QPushButton:hover, QDialogButtonBox QPushButton:hover {{ border-color: {ACCENT}; }}
"""
