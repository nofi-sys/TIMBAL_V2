"""Reverb preset definitions in legacy units (0-100)."""
from __future__ import annotations

from typing import Dict, List

_PRESETS: Dict[str, Dict[str, object]] = {
    'seco': {'active': False, 'level': 0, 'room': None, 'damp': None},
    'media': {'active': True, 'level': 25, 'room': 45, 'damp': 25},
    'sala': {'active': True, 'level': 40, 'room': 70, 'damp': 20},
}


def get_reverb_preset(name: str) -> Dict[str, object]:
    """Return a copy of the preset definition for the given name."""
    key = (name or '').lower()
    return dict(_PRESETS.get(key, _PRESETS['media']))


def available_reverb_presets() -> List[str]:
    """Return the list of available preset identifiers."""
    return list(_PRESETS.keys())
