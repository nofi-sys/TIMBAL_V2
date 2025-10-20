from pathlib import Path

path = Path('app/ui/pages/pads.py')
text = path.read_text()
text = text.replace('self.effects_toggle.setText("�-? Efectos")', "self.effects_toggle.setText('<< Efectos')", 1)
text = text.replace('self.effects_toggle.setText("�-� Efectos")', "self.effects_toggle.setText('>> Efectos')", 1)
path.write_text(text)
