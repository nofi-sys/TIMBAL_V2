
from pathlib import Path
from .settings import save_json, load_json
PRESETS_DIR = Path.home() / ".timbal_app" / "presets"
def save_preset(name: str, data: dict):
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    save_json(PRESETS_DIR / f"{name}.json", data)
def load_preset(name: str) -> dict:
    return load_json(PRESETS_DIR / f"{name}.json")
