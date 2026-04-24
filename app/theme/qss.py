
TOKENS = {
  "bg": "#1f2937", "panel": "#0f172a", "accent": "#3b82f6",
  "text": "#e5e7eb", "muted": "#94a3b8", "danger": "#ef4444",
  "radius": "10px"
}

def build_qss():
    t = TOKENS
    return f"""
QWidget {{
    font-family: "Segoe UI", "Inter", Arial, sans-serif;
}}
QMainWindow {{
    background: {t['bg']};
    color: {t['text']};
}}
QMenuBar {{
    background: #111827;
    color: {t['text']};
    border-bottom: 1px solid #334155;
    padding: 4px 8px;
}}
QMenuBar::item {{
    background: transparent;
    border-radius: 6px;
    padding: 7px 12px;
}}
QMenuBar::item:selected {{
    background: #1f2937;
}}
QMenu {{
    background: #111827;
    color: {t['text']};
    border: 1px solid #334155;
    padding: 6px;
}}
QMenu::item {{
    border-radius: 6px;
    padding: 7px 24px 7px 12px;
}}
QMenu::item:selected {{
    background: #1f2937;
}}
QStatusBar {{ background:{t['panel']}; color:{t['muted']}; }}
QToolButton {{ color:{t['text']}; }}
QPushButton {{
    background: {t['accent']};
    color: white;
    border: 1px solid #60a5fa;
    border-radius: 8px;
    padding: 7px 12px;
}}
QPushButton:hover {{ background: #1d4ed8; }}
QPushButton:pressed {{ background: #1f2937; }}
QSlider::groove:horizontal {{
    height: 6px;
    background: #334155;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: #3b82f6;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 16px;
    border-radius: 8px;
    background: #e5e7eb;
    border: 1px solid #94a3b8;
    margin: -5px 0;
}}
QSlider::groove:vertical {{
    width: 6px;
    background: #334155;
    border-radius: 3px;
}}
QSlider::sub-page:vertical {{
    background: #3b82f6;
    border-radius: 3px;
}}
QSlider::handle:vertical {{
    height: 16px;
    border-radius: 8px;
    background: #e5e7eb;
    border: 1px solid #94a3b8;
    margin: 0 -5px;
}}
QGroupBox {{
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    background: #111827;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color:{t['muted']};
}}
QToolTip {{
    background: #111827;
    color: {t['text']};
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 7px;
}}
"""
