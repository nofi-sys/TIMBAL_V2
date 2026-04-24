"""Reduced state model focused on continuity and temporal memory."""
from __future__ import annotations

import math
from typing import Iterable


def run_state_map_v1(
    features: Iterable[dict[str, object]],
    patch_profile: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    profile = patch_profile or {}
    temporal = profile.get("temporal", {}) if isinstance(profile, dict) else {}
    tau_energy_ms = _positive_or(float(temporal.get("tau_energy_ms") or 180.0), 180.0)
    tau_decay_free_ms = _positive_or(float(temporal.get("tau_decay_free_ms") or 620.0), 620.0)
    tau_decay_hold_ms = _positive_or(float(temporal.get("tau_decay_hold_ms") or 180.0), 180.0)

    predictions: list[dict[str, object]] = []
    energy_state = 0.0
    repeat_state = 0.0

    for item in features:
        intensity = _clamp01(float(item.get("intensity_input_norm", 0.0)))
        slope = _clamp01(float(item.get("slope_norm", 0.0)))
        pre_energy = _clamp01(float(item.get("pre_hit_energy_norm", 0.0)))
        tail_ratio = max(0.0, float(item.get("tail_ratio", 0.0)))
        ioi_prev_ms = item.get("ioi_prev_ms")
        dt_ms = 300.0 if ioi_prev_ms in (None, "") else max(1.0, float(ioi_prev_ms))

        energy_pre = energy_state * math.exp(-dt_ms / tau_energy_ms)
        repeat_target = _repeat_target(dt_ms)
        repeat_state = (0.65 * repeat_state) + (0.35 * repeat_target)
        contact_state = _clamp01((0.55 * tail_ratio) + (0.35 * pre_energy) + (0.15 * repeat_state))

        velocity_base = (0.72 * intensity) + (0.20 * energy_pre) + (0.08 * slope)
        brightness = _clamp01((0.42 * intensity) + (0.35 * slope) + (0.18 * energy_pre) - (0.20 * contact_state))
        transient_gain = _clamp01((0.25 + (0.65 * slope) + (0.10 * repeat_state)) * (1.0 - (0.25 * contact_state)))
        decay_ms = (
            (tau_decay_free_ms * (0.55 + (0.55 * energy_pre) + (0.12 * repeat_state)))
            * (1.0 - (0.55 * contact_state))
        ) + (tau_decay_hold_ms * contact_state)
        mute_damping = _clamp01((0.12 + (0.72 * contact_state) + (0.10 * repeat_state)))
        velocity_main = int(round(20 + (107 * _clamp01(velocity_base))))

        energy_state = _clamp01(energy_pre + (0.58 * intensity) + (0.18 * slope))

        predictions.append(
            {
                "model_name": "state_map_v1",
                "hit_id": int(item["hit_id"]),
                "velocity_main": velocity_main,
                "brightness_0_1": round(brightness, 6),
                "transient_gain": round(transient_gain, 6),
                "decay_ms": round(max(40.0, decay_ms), 6),
                "mute_damping_0_1": round(mute_damping, 6),
                "energy_state": round(energy_state, 6),
                "contact_state": round(contact_state, 6),
                "repeat_state": round(repeat_state, 6),
            }
        )
    return predictions


def _repeat_target(dt_ms: float) -> float:
    if dt_ms >= 300.0:
        return 0.0
    return _clamp01((300.0 - dt_ms) / 300.0)


def _positive_or(value: float, default: float) -> float:
    return value if value > 0 else default


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
