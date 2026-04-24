
TOKENS = {
  "bg": "#07111b", "panel": "#0f172a", "accent": "#19d8d2",
  "text": "#e5e7eb", "muted": "#94a3b8", "danger": "#ef4444",
  "radius": "10px"
}

def build_qss():
    t = TOKENS
    return f"""
QWidget {{
    font-family: "Segoe UI", Arial, sans-serif;
}}
QMainWindow {{
    background: #07111b;
    color: {t['text']};
}}
QWidget#AppShell {{
    background: #07111b;
    border: 1px solid #1e3448;
    border-radius: 16px;
}}
QWidget#AppChrome {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #050b12, stop:0.82 #07111b, stop:1 #0b1622);
    border-bottom: 1px solid #26384d;
}}
QLabel#AppMark {{
    color: #19d8d2;
    font-size: 25px;
    font-weight: 700;
}}
QLabel#AppTitle {{
    color: #f2f7fb;
    font-size: 20px;
    font-weight: 700;
}}
QLabel#AppTitleMuted {{
    color: #d2dce8;
    font-size: 20px;
    font-weight: 400;
}}
QPushButton#WindowButton, QPushButton#WindowCloseButton {{
    background: transparent;
    color: #d6e0ea;
    border: 0;
    border-radius: 6px;
    font-size: 18px;
    padding: 4px 10px;
}}
QPushButton#WindowButton:hover {{
    background: #142234;
    color: #19d8d2;
}}
QPushButton#WindowCloseButton:hover {{
    background: #7f1d1d;
    color: #ffffff;
}}
QWidget#AppTabs {{
    background: #0a131f;
    border-bottom: 1px solid #26384d;
}}
QPushButton#ChromeTab {{
    background: transparent;
    color: #cbd5e1;
    border: 0;
    border-radius: 0;
    padding: 13px 34px;
    font-size: 15px;
}}
QPushButton#ChromeTab:hover {{
    background: #101d2b;
    color: #ffffff;
}}
QPushButton#ChromeTab[active="true"] {{
    color: #ffffff;
    border-bottom: 3px solid #19d8d2;
}}
QMenu {{
    background: #0a131f;
    color: #e5e7eb;
    border: 1px solid #2b455d;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 28px 8px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: #102638;
    color: #19d8d2;
}}
QStatusBar {{ background:{t['panel']}; color:{t['muted']}; }}
QToolButton {{ color:{t['text']}; }}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #163247, stop:0.52 #0b1a28, stop:1 #07111b);
    color: #d9f7fb;
    border: 1px solid #2d526a;
    border-radius: 8px;
    padding: 7px 12px;
}}
QPushButton:hover {{
    border-color: #19d8d2;
    color: #ffffff;
}}
QPushButton:pressed {{
    background: #06101a;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: #2f465c;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: #19d8d2;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 13px;
    height: 13px;
    background: #d8edf4;
    border: 2px solid #2c89a1;
    border-radius: 7px;
    margin: -6px 0;
}}
QSlider::groove:vertical {{
    width: 5px;
    background: #2f465c;
    border-radius: 2px;
}}
QSlider::sub-page:vertical {{
    background: #19d8d2;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    width: 13px;
    height: 13px;
    background: #d8edf4;
    border: 2px solid #2c89a1;
    border-radius: 7px;
    margin: 0 -6px;
}}
QGroupBox {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #101d2a, stop:1 #07111b);
    border: 1px solid #2c4357;
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 10px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 7px;
    color: #d6e0ea;
    font-size: 13px;
    font-weight: 700;
}}
QCheckBox {{
    color: #dbe8f1;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 38px;
    height: 20px;
    border-radius: 10px;
    border: 1px solid #2c5268;
    background: #102033;
}}
QCheckBox::indicator:checked {{
    background: #0d766f;
    border-color: #19d8d2;
}}
QToolTip {{
    background: #07111b;
    color: #e5e7eb;
    border: 1px solid #2d526a;
    border-radius: 6px;
    padding: 5px 7px;
}}
"""
