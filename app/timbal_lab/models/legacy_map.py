"""Simple baseline map approximating the current legacy behavior."""
from __future__ import annotations

from typing import Iterable


def run_legacy_map(features: Iterable[dict[str, object]], patch_profile: dict[str, object] | None = None) -> list[dict[str, object]]:
    predictions: list[dict[str, object]] = []
    for item in features:
        intensity = _clamp01(float(item.get("intensity_input_norm", 0.0)))
        slope = _clamp01(float(item.get("slope_norm", 0.0)))
        pre = _clamp01(float(item.get("pre_hit_energy_norm", 0.0)))

        velocity_main = int(round(18 + (109 * intensity)))
        brightness = _clamp01((0.78 * intensity) + (0.18 * slope))
        transient_gain = _clamp01(0.35 + (0.55 * slope))
        decay_ms = 280.0 + (460.0 * intensity) + (90.0 * pre)
        mute_damping = _clamp01(0.08 + (0.35 * float(item.get("tail_ratio", 0.0))))

        predictions.append(
            {
                "model_name": "legacy_map",
                "hit_id": int(item["hit_id"]),
                "velocity_main": velocity_main,
                "brightness_0_1": round(brightness, 6),
                "transient_gain": round(transient_gain, 6),
                "decay_ms": round(decay_ms, 6),
                "mute_damping_0_1": round(mute_damping, 6),
                "energy_state": None,
                "contact_state": None,
                "repeat_state": None,
            }
        )
    return predictions


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
