from pathlib import Path
text = Path('app/ui/pages/pads.py').read_text(encoding='utf-8')
start = text.index('board = QWidget()')
end = text.index('main.addWidget(self.effects_holder, 0)')
print(text[start:end])
