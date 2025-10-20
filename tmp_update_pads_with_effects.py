from pathlib import Path

path = Path('app/ui/pages/pads.py')
text = path.read_text(encoding='utf-8')

if "from app.ui.pages.effects import EffectsPage" not in text:
    text = text.replace("from app.ui.components.note_selector import NoteSelectorDialog\n", "from app.ui.components.note_selector import NoteSelectorDialog\nfrom app.ui.components.collapsible import CollapsiblePanel\nfrom app.ui.pages.effects import EffectsPage\n")

text = text.replace("class PadsPage(QWidget):\n    def __init__(self, engine) -> None:\n        super().__init__()\n        self.engine = engine\n", "class PadsPage(QWidget):\n    def __init__(self, engine, config: dict | None = None) -> None:\n        super().__init__()\n        self.engine = engine\n        self.config = config if config is not None else {}\n        self._config_key = 'effects_panel_collapsed'\n")

text = text.replace("        main = QHBoxLayout(self)\n        main.setContentsMargins(24, 16, 24, 16)\n        main.setSpacing(28)\n\n        board = QWidget()\n", "        main = QHBoxLayout(self)\n        main.setContentsMargins(24, 16, 24, 16)\n        main.setSpacing(28)\n\n        effects_collapsed = bool(self.config.get(self._config_key, False))\n        self.effects_widget = EffectsPage(engine)\n        self.effects_panel = CollapsiblePanel('Efectos', self.effects_widget, collapsed=effects_collapsed)\n        self.effects_panel.setMinimumWidth(260)\n        self.effects_panel.setMaximumWidth(320)\n        self.effects_panel.on_toggled(self._on_effects_toggled)\n\n        board = QWidget()\n")

text = text.replace("        main.addWidget(board, 1)\n        main.addWidget(nav_widget, 0, Qt.AlignVCenter)\n", "        main.addWidget(self.effects_panel, 0)\n        main.addWidget(board, 1)\n        main.addWidget(nav_widget, 0, Qt.AlignVCenter)\n")

text = text.replace("            QWidget#PadSetNav {\n                background: #111827;\n                border: 1px solid #1f2937;\n                border-radius: 22px;\n            }\n            QWidget#PadSetNav QPushButton {\n", "            QWidget#PadSetNav {\n                background: #111827;\n                border: 1px solid #1f2937;\n                border-radius: 22px;\n            }\n            QWidget#PadSetNav QPushButton {\n")

if "QFrame#CollapsiblePanel" not in text:
    insert = "            QFrame#CollapsiblePanel {\n                background-color: #111827;\n                border: 1px solid #1f2937;\n                border-radius: 18px;\n                margin-right: 8px;\n            }\n            QToolButton#CollapsibleHeader {\n                background-color: transparent;\n                color: #e5e7eb;\n                border: none;\n                font-size: 16px;\n                font-weight: 700;\n                padding: 8px 12px;\n            }\n            QToolButton#CollapsibleHeader:checked {\n                color: #60a5fa;\n            }\n"
    text = text.replace("            QWidget#PadSetNav QPushButton:hover {\n                background-color: #3b82f6;\n            }\n            QWidget#PadSetNav QLabel {\n", insert + "            QWidget#PadSetNav QPushButton:hover {\n                background-color: #3b82f6;\n            }\n            QWidget#PadSetNav QLabel {\n")

if "self.effects_panel" not in text:
    raise SystemExit('effects panel not inserted')

if "def _on_effects_toggled" not in text:
    text += "\n    def _on_effects_toggled(self, collapsed: bool) -> None:\n        self.config[self._config_key] = collapsed\n        try:\n            from app.state.settings import save_config\n            save_config(self.config)\n        except Exception:\n            pass\n\n"

path.write_text(text, encoding='utf-8')
