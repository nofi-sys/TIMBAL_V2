from pathlib import Path
text = Path('old/TIMBAL 2.0.py').read_text(encoding='utf-8')
start = text.index('    def _init_hw_map(')
end = text.index('    def _timer_vu(')
print(text[start:end])
