"""Patch profile persistence for the timbal lab."""
from __future__ import annotations

import json
import time
from pathlib import Path


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "unlabeled"


class PatchProfileManager:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path("configs") / "patches"

    def ensure_profile(
        self,
        *,
        patch_id: str,
        notes: str = "",
        source_kind: str | None = None,
    ) -> Path:
        profile = self.load_profile(patch_id)
        if profile is None:
            profile = self._default_profile(patch_id)

        if notes:
            profile["notes"] = notes
        if source_kind:
            profile["last_source_kind"] = source_kind
        profile["updated_at_local"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return self.save_profile(patch_id, profile)

    def load_profile(self, patch_id: str) -> dict[str, object] | None:
        path = self.profile_path(patch_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def profile_path(self, patch_id: str) -> Path:
        return self.root_dir / f"{_slugify(patch_id)}.json"

    def save_profile(self, patch_id: str, profile: dict[str, object]) -> Path:
        path = self.profile_path(patch_id)
        return self.write_profile(path, profile)

    def write_profile(self, path: Path, profile: dict[str, object]) -> Path:
        profile = dict(profile)
        profile.setdefault("updated_at_local", time.strftime("%Y-%m-%d %H:%M:%S"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, ensure_ascii=True, indent=2), encoding="utf-8")
        return path

    def _default_profile(self, patch_id: str) -> dict[str, object]:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "patch_id": patch_id,
            "created_at_local": timestamp,
            "updated_at_local": timestamp,
            "notes": "",
            "base_note_midi": 60,
            "thresholds": {
                "hit_threshold": None,
                "delta_threshold": None,
                "refractory_ms": None,
            },
            "temporal": {
                "tau_energy_ms": None,
                "tau_decay_free_ms": None,
                "tau_decay_hold_ms": None,
            },
            "model_curves": {
                "velocity_curve": [],
                "brightness_curve": [],
                "mute_curve": [],
            },
        }
