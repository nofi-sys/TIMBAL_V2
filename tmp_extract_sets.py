from pathlib import Path
text = Path('old/TIMBAL 2.0.py').read_text(encoding='utf-8')
start = text.index('        notas_def = [')
end = text.index('        for fila in range(5):')
print(text[start:end])
