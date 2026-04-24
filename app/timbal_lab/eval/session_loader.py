"""Helpers to load recorded timbal lab sessions from disk."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.host_analog.stream import AnalogHit, AnalogSample
from app.timbal_lab.logging.session_recorder import RAW_SAMPLE_STRUCT


@dataclass(frozen=True)
class SessionData:
    session_dir: Path
    manifest: dict[str, object]
    samples: list[AnalogSample]
    events: list[dict[str, object]]
    hits: list[AnalogHit]


def load_session_dir(session_dir: Path) -> SessionData:
    manifest_path = session_dir / "manifest.json"
    raw_path = session_dir / "arduino_raw.bin"
    events_path = session_dir / "events.jsonl"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = _load_samples(raw_path)
    events = _load_events(events_path)
    hits = _hits_from_events(events)
    return SessionData(
        session_dir=session_dir,
        manifest=manifest,
        samples=samples,
        events=events,
        hits=hits,
    )


def _load_samples(path: Path) -> list[AnalogSample]:
    raw = path.read_bytes()
    size = RAW_SAMPLE_STRUCT.size
    if len(raw) % size != 0:
        raise ValueError("arduino_raw.bin tiene longitud invalida")

    samples: list[AnalogSample] = []
    for offset in range(0, len(raw), size):
        channel, device_us, value, host_ns = RAW_SAMPLE_STRUCT.unpack(raw[offset : offset + size])
        samples.append(
            AnalogSample(
                channel=int(channel),
                device_us=int(device_us),
                value=int(value),
                host_time=float(host_ns) / 1_000_000_000.0,
            )
        )
    return samples


def _load_events(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _hits_from_events(events: list[dict[str, object]]) -> list[AnalogHit]:
    hits: list[AnalogHit] = []
    for record in events:
        if record.get("kind") != "HIT":
            continue
        payload = record.get("payload", {})
        if not isinstance(payload, dict):
            continue
        hits.append(
            AnalogHit(
                channel=int(payload.get("channel", 0)),
                value=int(payload.get("value", 0)),
                device_us=int(payload.get("device_us", 0)),
                host_time=float(payload.get("host_time_s", 0.0)),
                lag_ms=None if payload.get("lag_ms") is None else float(payload["lag_ms"]),
            )
        )
    return hits
