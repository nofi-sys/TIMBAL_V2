"""Legacy configuration helpers (JSON on disk)."""
from __future__ import annotations

import json
import os
from pathlib import Path


def _app_config_dir() -> Path:
    base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    directory = base / 'TimbalApp'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_config_path() -> Path:
    override = os.environ.get('TIMBAL_CONFIG_PATH')
    if override:
        try:
            path = Path(override).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            pass
    return _app_config_dir() / 'config.json'


CONFIG_PATH = _resolve_config_path()


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        print('Aviso: no pude guardar la configuración.')
