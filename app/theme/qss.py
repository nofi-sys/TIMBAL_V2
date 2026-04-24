
TOKENS = {
  "bg": "#1f2937", "panel": "#0f172a", "accent": "#3b82f6",
  "text": "#e5e7eb", "muted": "#94a3b8", "danger": "#ef4444",
  "radius": "10px"
}

def build_qss():
    t = TOKENS
    return f"""
QMainWindow {{ background: {t['bg']}; color:{t['text']}; }}
QStatusBar {{ background:{t['panel']}; color:{t['muted']}; }}
QToolButton {{ color:{t['text']}; }}
QPushButton {{ background:{t['accent']}; color:white; border-radius:8px; padding:6px 10px; }}
QSlider::groove:horizontal {{ height:6px; background:#334155; border-radius:3px; }}
QSlider::handle:horizontal {{ width:16px; border-radius:8px; background:white; margin:-5px 0; }}
QGroupBox {{ border:1px solid #334155; border-radius:8px; margin-top:12px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color:{t['muted']}; }}
"""
