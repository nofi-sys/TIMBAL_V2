from pathlib import Path

path = Path('app/ui/pages/pads.py')
text = path.read_text(encoding='utf-8')
replacements = {
    'self.setMinimumSize(48, 220)': 'self.setMinimumSize(48, 260)',
    'bar.setFixedHeight(16)': 'bar.setFixedHeight(18)',
    'board.setMinimumSize(460, 420)': 'board.setMinimumSize(560, 390)',
    'board_layout.setContentsMargins(28, 24, 28, 24)': 'board_layout.setContentsMargins(32, 18, 32, 24)',
    'board_layout.setSpacing(14)': 'board_layout.setSpacing(12)',
    'vu_grid.setHorizontalSpacing(18)': 'vu_grid.setHorizontalSpacing(18)',
    'grid.setHorizontalSpacing(16)': 'grid.setHorizontalSpacing(20)',
    'grid.setVerticalSpacing(14)': 'grid.setVerticalSpacing(12)',
    'btn.setMinimumSize(170, 96)': 'btn.setMinimumSize(160, 96)',
    'container.setMinimumWidth(1100)': 'container.setMinimumWidth(1200)',
    'container.setMaximumWidth(1400)': 'container.setMaximumWidth(1500)'
}
for old, new in replacements.items():
    text = text.replace(old, new, 1)

# Insert contents margins for grid and prev/next rows
if 'grid.setContentsMargins' not in text:
    text = text.replace('grid = QGridLayout()\n        grid.setHorizontalSpacing(20)\n        grid.setVerticalSpacing(12)',
                        'grid = QGridLayout()\n        grid.setContentsMargins(16, 0, 16, 0)\n        grid.setHorizontalSpacing(20)\n        grid.setVerticalSpacing(12)',
                        1)
if 'prev_row.setContentsMargins' not in text:
    text = text.replace('prev_row = QHBoxLayout()\n        prev_row.setSpacing(16)',
                        'prev_row = QHBoxLayout()\n        prev_row.setContentsMargins(0, 8, 0, 6)\n        prev_row.setSpacing(14)',
                        1)
if 'next_row.setContentsMargins' not in text:
    text = text.replace('next_row = QHBoxLayout()\n        next_row.setSpacing(16)',
                        'next_row = QHBoxLayout()\n        next_row.setContentsMargins(0, 6, 0, 0)\n        next_row.setSpacing(14)',
                        1)

path.write_text(text, encoding='utf-8')
