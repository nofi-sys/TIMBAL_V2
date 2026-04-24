"""Session recording helpers for the timbal lab."""
from __future__ import annotations

import json
import struct
import time
from pathlib import Path

from app.host_analog.stream import AnalogHit, AnalogSample

RAW_SAMPLE_STRUCT = struct.Struct("<BIHQ")


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "unlabeled"


class SessionRecorder:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path("data") / "sessions"
        self.session_dir: Path | None = None
        self._raw_handle = None
        self._events_handle = None
        self._manifest: dict[str, object] | None = None
        self.sample_count = 0
        self.hit_count = 0

    @property
    def is_active(self) -> bool:
        return self.session_dir is not None

    def start(
        self,
        *,
        patch_id: str,
        notes: str,
        source_kind: str,
        source_detail: str | None = None,
    ) -> Path:
        if self.is_active:
            raise RuntimeError("Ya hay una sesion activa.")

        self.root_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        base_name = f"{timestamp}_{_slugify(patch_id)}"
        session_dir = self.root_dir / base_name
        suffix = 1
        while session_dir.exists():
            session_dir = self.root_dir / f"{base_name}_{suffix:02d}"
            suffix += 1
        session_dir.mkdir(parents=True, exist_ok=False)

        self.session_dir = session_dir
        self.sample_count = 0
        self.hit_count = 0
        self._raw_handle = (session_dir / "arduino_raw.bin").open("wb")
        self._events_handle = (session_dir / "events.jsonl").open("w", encoding="utf-8")
        self._manifest = {
            "patch_id": patch_id,
            "notes": notes,
            "source_kind": source_kind,
            "source_detail": source_detail,
            "started_at_local": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sample_count": 0,
            "hit_count": 0,
        }
        self._write_manifest()
        self.log_event(
            "SESSION_START",
            {
                "patch_id": patch_id,
                "notes": notes,
                "source_kind": source_kind,
                "source_detail": source_detail,
            },
        )
        return session_dir

    def log_samples(self, samples: list[AnalogSample]) -> None:
        if not self.is_active or not samples or self._raw_handle is None:
            return
        for sample in samples:
            host_ns = int(round(sample.host_time * 1_000_000_000.0))
            self._raw_handle.write(
                RAW_SAMPLE_STRUCT.pack(
                    int(sample.channel),
                    int(sample.device_us),
                    int(sample.value),
                    host_ns,
                )
            )
            self.sample_count += 1
        self._update_manifest_counts()

    def log_hit(self, hit: AnalogHit) -> None:
        if not self.is_active:
            return
        self.hit_count += 1
        self.log_event(
            "HIT",
            {
                "channel": int(hit.channel),
                "value": int(hit.value),
                "device_us": int(hit.device_us),
                "host_time_s": float(hit.host_time),
                "lag_ms": None if hit.lag_ms is None else float(hit.lag_ms),
            },
        )
        self._update_manifest_counts()

    def log_event(self, kind: str, payload: dict[str, object]) -> None:
        if not self.is_active or self._events_handle is None:
            return
        record = {
            "kind": kind,
            "t_local": time.strftime("%Y-%m-%d %H:%M:%S"),
            "payload": payload,
        }
        self._events_handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        self._events_handle.flush()

    def update_manifest_fields(self, **fields: object) -> None:
        if self._manifest is None:
            return
        self._manifest.update(fields)
        self._write_manifest()

    def close(self) -> Path | None:
        if not self.is_active:
            return None
        session_dir = self.session_dir
        self.log_event("SESSION_END", {"sample_count": self.sample_count, "hit_count": self.hit_count})
        if self._manifest is not None:
            self._manifest["finished_at_local"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._manifest["sample_count"] = self.sample_count
            self._manifest["hit_count"] = self.hit_count
            self._write_manifest()

        if self._raw_handle is not None:
            self._raw_handle.close()
        if self._events_handle is not None:
            self._events_handle.close()

        self.session_dir = None
        self._raw_handle = None
        self._events_handle = None
        self._manifest = None
        return session_dir

    def _update_manifest_counts(self) -> None:
        if self._manifest is None:
            return
        self._manifest["sample_count"] = self.sample_count
        self._manifest["hit_count"] = self.hit_count
        self._write_manifest()

    def _write_manifest(self) -> None:
        if self.session_dir is None or self._manifest is None:
            return
        manifest_path = self.session_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(self._manifest, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
