"""Visual constants from spec section 4. Role names, used everywhere instead of raw values."""

BG = "#16181D"
PANEL = "#1F2229"
PANEL_RAISED = "#262A33"
TEXT = "#E8EAED"
TEXT_MUTED = "#9AA0A6"
ACCENT = "#22D3EE"
ACCENT_HOVER = "#4FDDF2"
ACCENT_PRESSED = "#0FB5CF"
WARNING = "#F59E0B"
ERROR = "#F87171"
FLASH = "#FFFFFF"
BORDER_LINE = "#2E333D"

FONT_FAMILY = "Segoe UI"
FONT_PT_BODY = 10
FONT_PT_SMALL = 9

RADIUS_WINDOW = 8
RADIUS_BUTTON = 6

# Frame border geometry (physical pixels)
BORDER_GAP = 2
BORDER_THICKNESS = 3
BAR_GAP_LOGICAL = 12

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "{FONT_FAMILY}";
    font-size: {FONT_PT_BODY}pt;
}}
QFrame#panel, QGroupBox {{
    background: {PANEL};
    border: 1px solid {BORDER_LINE};
    border-radius: {RADIUS_WINDOW}px;
}}
QGroupBox {{
    margin-top: 10px;
    padding: 10px 8px 6px 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {TEXT_MUTED};
}}
QLabel {{ background: transparent; }}
QLabel#muted {{ color: {TEXT_MUTED}; }}
QLabel#warning {{ color: {WARNING}; }}
QLabel#error {{ color: {ERROR}; }}
QLineEdit, QSpinBox, QComboBox {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER_LINE};
    border-radius: {RADIUS_BUTTON}px;
    padding: 4px 6px;
    selection-background-color: {ACCENT};
    selection-color: {BG};
}}
QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit[invalid="true"] {{ border: 1px solid {ERROR}; }}
QLineEdit:read-only {{ color: {TEXT_MUTED}; }}
QPushButton {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER_LINE};
    border-radius: {RADIUS_BUTTON}px;
    padding: 6px 12px;
}}
QPushButton:hover {{ border-color: {TEXT_MUTED}; }}
QPushButton:pressed {{ background: {PANEL}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; }}
QPushButton#primary {{
    background: {ACCENT};
    color: {BG};
    font-weight: bold;
    border: none;
    padding: 9px 16px;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background: {PANEL_RAISED}; color: {TEXT_MUTED}; }}
QPushButton#bar {{
    background: transparent;
    border: none;
    border-radius: {RADIUS_BUTTON}px;
    padding: 2px;
    font-size: 13pt;
    min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
}}
QPushButton#bar:hover {{ background: {PANEL_RAISED}; }}
QPushButton#bar:disabled {{ color: {BORDER_LINE}; }}
QCheckBox, QRadioButton {{ background: transparent; spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    background: {PANEL_RAISED};
    border: 1px solid {TEXT_MUTED};
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}
QRadioButton::indicator:checked {{
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0.45 {BG}, stop:0.55 {ACCENT});
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border: 1px solid {ACCENT}; }}
QSlider::groove:horizontal {{ height: 4px; background: {PANEL_RAISED}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; margin: -6px 0; background: {ACCENT}; border-radius: 7px; }}
QProgressBar {{ background: {PANEL_RAISED}; border: none; border-radius: 4px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QMenu {{ background: {PANEL}; border: 1px solid {BORDER_LINE}; border-radius: {RADIUS_BUTTON}px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {PANEL_RAISED}; }}
QMenu::separator {{ height: 1px; background: {BORDER_LINE}; margin: 4px 6px; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER_LINE}; padding: 4px; }}
QMessageBox {{ background: {PANEL}; }}
QDialog {{ background: {BG}; }}
"""
