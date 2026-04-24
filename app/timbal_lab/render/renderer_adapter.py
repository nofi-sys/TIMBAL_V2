"""Minimal renderer adapter for playing analyzed sessions."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from mido import Message

from app.timbal_lab.profiles.patch_profile import PatchProfileManager


class RendererAdapter:
    def __init__(self, engine) -> None:
        self.engine = engine
        self._play_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def is_available(self) -> bool:
        return self.engine is not None

    def stop(self) -> None:
        self._stop_event.set()
        if self._play_thread is not None and self._play_thread.is_alive():
            self._play_thread.join(timeout=0.5)
        self._play_thread = None

    def play_session_analysis(self, session_dir: Path, model_name: str) -> bool:
        if self.engine is None:
            return False
        analysis_dir = session_dir / "analysis"
        predictions_path = analysis_dir / f"predictions_{model_name}.jsonl"
        features_path = analysis_dir / "hits_features.jsonl"
        if not predictions_path.exists() or not features_path.exists():
            return False

        feature_rows = _read_jsonl(features_path)
        prediction_rows = _read_jsonl(predictions_path)
        by_hit_id = {int(item["hit_id"]): item for item in feature_rows if "hit_id" in item}
        sequence = []
        for row in prediction_rows:
            hit_id = int(row.get("hit_id", -1))
            feature = by_hit_id.get(hit_id)
            if feature is None:
                continue
            sequence.append({**row, "device_us": int(feature["device_us"])})
        sequence.sort(key=lambda item: int(item["device_us"]))
        if not sequence:
            return False

        base_note = _load_base_note(session_dir)
        self.stop()
        self._stop_event.clear()
        self._play_thread = threading.Thread(
            target=self._play_sequence,
            args=(sequence, base_note),
            name=f"timbal-lab-render-{model_name}",
            daemon=True,
        )
        self._play_thread.start()
        return True

    def _play_sequence(self, sequence: list[dict[str, object]], base_note: int) -> None:
        prev_device_us: int | None = None
        for row in sequence:
            if self._stop_event.is_set():
                return
            current_device_us = int(row["device_us"])
            if prev_device_us is not None:
                dt_s = max(0.0, (current_device_us - prev_device_us) / 1_000_000.0)
                if self._stop_event.wait(min(dt_s, 1.5)):
                    return
            prev_device_us = current_device_us

            velocity = int(max(1, min(127, int(row.get("velocity_main", 96)))))
            note = int(max(0, min(127, base_note)))
            decay_ms = float(row.get("decay_ms", 240.0))
            self.engine.disparar(Message("note_on", note=note, velocity=velocity, channel=0))
            off_delay = max(0.06, min(1.2, decay_ms / 1000.0))
            timer = threading.Timer(off_delay, self._note_off_safe, args=(note,))
            timer.daemon = True
            timer.start()

    def _note_off_safe(self, note: int) -> None:
        if self._stop_event.is_set() or self.engine is None:
            return
        try:
            self.engine.disparar(Message("note_off", note=note, velocity=0, channel=0))
        except Exception:
            pass


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _load_base_note(session_dir: Path) -> int:
    manifest_path = session_dir / "manifest.json"
    profile_path = None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        explicit = manifest.get("patch_profile_path")
        if isinstance(explicit, str) and explicit.strip():
            profile_path = Path(explicit)
    except Exception:
        profile_path = None

    if profile_path is None or not profile_path.exists():
        manager = PatchProfileManager()
        try:
            patch_id = str(json.loads(manifest_path.read_text(encoding="utf-8")).get("patch_id") or "unlabeled")
            profile_path = manager.profile_path(patch_id)
        except Exception:
            return 60

    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return 60
    try:
        return int(profile.get("base_note_midi", 60))
    except Exception:
        return 60
