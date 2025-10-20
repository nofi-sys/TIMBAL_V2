from pathlib import Path

path = Path("app/ui/pages/pads.py")
text = path.read_text(encoding="utf-8")
replacements = {
    "self.setMinimumSize(48, 260)": "self.setMinimumSize(48, 260)",  # keep
    "bar.setFixedHeight(18)": "bar.setFixedHeight(18)",
    "board.setMinimumSize(560, 390)": "board.setMinimumSize(540, 380)",
    "board_layout.setContentsMargins(32, 18, 32, 24)": "board_layout.setContentsMargins(28, 16, 28, 22)",
    "board_layout.setSpacing(12)": "board_layout.setSpacing(10)",
    "container.setMinimumWidth(1200)": "container.setMinimumWidth(1260)",
    "container.setMaximumWidth(1500)": "container.setMaximumWidth(1500)",
    "btn.setMinimumSize(170, 96)": "btn.setMinimumSize(150, 92)",
    "prev_row.setSpacing(16)": "prev_row.setSpacing(14)",
    "next_row.setSpacing(16)": "next_row.setSpacing(14)"
}
for old, new in replacements.items():
    text = text.replace(old, new, 1)

# ensure contents margins
if 'grid.setContentsMargins' not in text:
    text = text.replace('grid = QGridLayout()\n        grid.setHorizontalSpacing(20)\n        grid.setVerticalSpacing(12)',
                        'grid = QGridLayout()\n        grid.setContentsMargins(18, 0, 18, 0)\n        grid.setHorizontalSpacing(18)\n        grid.setVerticalSpacing(12)', 1)
else:
    text = text.replace('grid = QGridLayout()\n        grid.setHorizontalSpacing(18)',
                        'grid = QGridLayout()\n        grid.setContentsMargins(18, 0, 18, 0)\n        grid.setHorizontalSpacing(18)', 1)

# adjust prev/next margins if not present
if 'prev_row.setContentsMargins' not in text:
    text = text.replace('prev_row = QHBoxLayout()\n        prev_row.setSpacing(14)',
                        'prev_row = QHBoxLayout()\n        prev_row.setContentsMargins(0, 6, 0, 4)\n        prev_row.setSpacing(14)', 1)
if 'next_row.setContentsMargins' not in text:
    text = text.replace('next_row = QHBoxLayout()\n        next_row.setSpacing(14)',
                        'next_row = QHBoxLayout()\n        next_row.setContentsMargins(0, 4, 0, 0)\n        next_row.setSpacing(14)', 1)

# fix toggle text
text = text.replace('self.effects_toggle.setText("? Efectos")', "self.effects_toggle.setText('\\u25C0 Efectos')", 1)
text = text.replace('self.effects_toggle.setText("? Efectos")', "self.effects_toggle.setText('\\u25B6 Efectos')", 1)

path.write_text(text, encoding='utf-8')
