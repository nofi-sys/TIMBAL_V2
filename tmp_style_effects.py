from pathlib import Path
import re

path = Path("app/ui/pages/effects.py")
text = path.read_text(encoding="utf-8-sig")
if "self.setObjectName(\"EffectsPage\")" not in text:
    text = text.replace(
        "        self.audio = engine\n        self.min_velocity = 8\n        self._build_ui()\n",
        "        self.audio = engine\n        self.min_velocity = 8\n        self.setObjectName(\"EffectsPage\")\n        self._build_ui()\n        self.setStyleSheet(\n            \"QWidget#EffectsPage{color:#e5e7eb;}\n"
        "QWidget#EffectsPage QLabel{color:#e5e7eb;}\n"
        "QWidget#EffectsPage QGroupBox{color:#e5e7eb;}\n"
        "QWidget#EffectsPage QCheckBox{color:#e5e7eb;}\n"
        "QWidget#EffectsPage QPushButton{color:#e5e7eb;}\")\n",
        1,
    )
path.write_text(text, encoding='utf-8')
