"""Patch profile calibration from recorded sessions."""
from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from app.timbal_lab.profiles.patch_profile import PatchProfileManager


def calibrate_profile_from_analysis(
    *,
    session_dir: Path,
    report: dict[str, object],
    features: list[dict[str, object]],
    winner_predictions: list[dict[str, object]],
) -> tuple[dict[str, object], Path, dict[str, object]]:
    profile_path = _resolve_profile_path(session_dir)
    manager = PatchProfileManager(profile_path.parent)
    patch_id = str(_load_manifest(session_dir).get("patch_id") or profile_path.stem)
    profile = manager.load_profile(patch_id) or _default_profile(manager, patch_id)

    hit_values = _float_values(features, "raw_hit_value")
    slope_values = _float_values(features, "initial_slope")
    pre_energy_values = _float_values(features, "pre_hit_energy")
    ioi_values = [value for value in _float_values(features, "ioi_prev_ms") if value > 0.0]
    lag_values = _float_values(features, "lag_ms")
    decay_values = _float_values(winner_predictions, "decay_ms")
    brightness_values = _float_values(winner_predictions, "brightness_0_1")
    mute_values = _float_values(winner_predictions, "mute_damping_0_1")
    velocity_values = _float_values(winner_predictions, "velocity_main")

    thresholds = dict(profile.get("thresholds", {}))
    thresholds["hit_threshold"] = int(
        round(
            _clamp(
                _quantile(hit_values, 0.15, default=80.0) * 0.88,
                20.0,
                1023.0,
            )
        )
    )
    thresholds["delta_threshold"] = int(
        round(
            _clamp(
                _quantile(slope_values, 0.20, default=25.0) * 0.35,
                5.0,
                512.0,
            )
        )
    )
    thresholds["refractory_ms"] = int(
        round(
            _clamp(
                (_quantile(ioi_values, 0.15, default=90.0) * 0.28) if ioi_values else 28.0,
                8.0,
                90.0,
            )
        )
    )

    temporal = dict(profile.get("temporal", {}))
    temporal["tau_energy_ms"] = int(
        round(
            _clamp(
                _quantile(ioi_values, 0.50, default=180.0) * 0.95,
                90.0,
                360.0,
            )
        )
    )
    temporal["tau_decay_free_ms"] = int(
        round(
            _clamp(
                _quantile(decay_values, 0.60, default=620.0),
                180.0,
                1400.0,
            )
        )
    )
    temporal["tau_decay_hold_ms"] = int(
        round(
            _clamp(
                temporal["tau_decay_free_ms"] * 0.38,
                60.0,
                max(60.0, temporal["tau_decay_free_ms"] - 40.0),
            )
        )
    )

    profile["thresholds"] = thresholds
    profile["temporal"] = temporal
    profile["model_curves"] = {
        "velocity_curve": _build_curve(features, winner_predictions, "intensity_input_norm", "velocity_main"),
        "brightness_curve": _build_curve(features, winner_predictions, "intensity_input_norm", "brightness_0_1"),
        "mute_curve": _build_curve(features, winner_predictions, "intensity_input_norm", "mute_damping_0_1"),
    }
    profile["analysis"] = {
        "last_calibration_at_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_calibration_session": str(session_dir),
        "winner_model": str(report.get("winner", "unknown")),
        "feature_count": len(features),
        "noise_rms": round(_noise_rms(pre_energy_values), 6),
        "avg_lag_ms": round(statistics.mean(lag_values), 6) if lag_values else None,
        "avg_decay_ms": round(statistics.mean(decay_values), 6) if decay_values else None,
        "avg_brightness": round(statistics.mean(brightness_values), 6) if brightness_values else None,
        "avg_mute_damping": round(statistics.mean(mute_values), 6) if mute_values else None,
        "avg_velocity": round(statistics.mean(velocity_values), 6) if velocity_values else None,
    }
    profile["updated_at_local"] = time.strftime("%Y-%m-%d %H:%M:%S")

    saved_path = manager.write_profile(profile_path, profile)
    calibration_summary = {
        "patch_profile_path": str(saved_path),
        "thresholds": thresholds,
        "temporal": temporal,
        "analysis": profile["analysis"],
        "curve_sizes": {
            "velocity_curve": len(profile["model_curves"]["velocity_curve"]),
            "brightness_curve": len(profile["model_curves"]["brightness_curve"]),
            "mute_curve": len(profile["model_curves"]["mute_curve"]),
        },
    }
    (session_dir / "analysis" / "calibration_summary.json").write_text(
        json.dumps(calibration_summary, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return profile, saved_path, calibration_summary


def _resolve_profile_path(session_dir: Path) -> Path:
    manifest = _load_manifest(session_dir)
    explicit = manifest.get("patch_profile_path")
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit)
    patch_id = str(manifest.get("patch_id") or "unlabeled")
    return PatchProfileManager().profile_path(patch_id)


def _default_profile(manager: PatchProfileManager, patch_id: str) -> dict[str, object]:
    path = manager.ensure_profile(patch_id=patch_id)
    return manager.load_profile(patch_id) or {"patch_id": patch_id, "profile_path": str(path)}


def _load_manifest(session_dir: Path) -> dict[str, object]:
    return json.loads((session_dir / "manifest.json").read_text(encoding="utf-8"))


def _float_values(rows: list[dict[str, object]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(field)
        if value in (None, ""):
            continue
        try:
            values.append(float(value))
        except Exception:
            continue
    return values


def _quantile(values: list[float], q: float, *, default: float) -> float:
    if not values:
        return default
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = _clamp(q, 0.0, 1.0) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * weight)


def _build_curve(
    features: list[dict[str, object]],
    predictions: list[dict[str, object]],
    feature_field: str,
    prediction_field: str,
) -> list[dict[str, float]]:
    by_hit_id = {int(row["hit_id"]): row for row in predictions if "hit_id" in row}
    merged = []
    for feature in features:
        prediction = by_hit_id.get(int(feature["hit_id"]))
        if prediction is None:
            continue
        try:
            merged.append(
                (
                    float(feature[feature_field]),
                    float(prediction[prediction_field]),
                )
            )
        except Exception:
            continue
    if not merged:
        return []
    merged.sort(key=lambda item: item[0])
    knots = [0.0, 0.25, 0.5, 0.75, 1.0]
    curve = []
    for knot in knots:
        nearest = min(merged, key=lambda item: abs(item[0] - knot))
        curve.append(
            {
                "input": round(float(nearest[0]), 6),
                "output": round(float(nearest[1]), 6),
            }
        )
    return curve


def _noise_rms(values: list[float]) -> float:
    if not values:
        return 0.0
    mean_square = sum(value * value for value in values) / len(values)
    return math.sqrt(mean_square)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))
