from pathlib import Path
import re

path = Path("app/ui/pages/pads.py")
text = path.read_text(encoding="utf-8")
text = re.sub(r"self.btn_up = QPushButton\(.*?\)", "self.btn_up = QPushButton(chr(0x25B2))", text)
text = re.sub(r"self.btn_down = QPushButton\(.*?\)", "self.btn_down = QPushButton(chr(0x25BC))", text)
path.write_text(text, encoding="utf-8")
