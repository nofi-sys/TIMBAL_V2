"""Offline benchmark for timbal lab models."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from app.timbal_lab.features.onset_features import extract_session_features
from app.timbal_lab.profiles.calibration import calibrate_profile_from_analysis
from app.timbal_lab.models.legacy_map import run_legacy_map
from app.timbal_lab.models.state_map_v1 import run_state_map_v1
from app.timbal_lab.profiles.patch_profile import PatchProfileManager
from app.timbal_lab.eval.report_writer import write_benchmark_markdown


def benchmark_session(session_dir: Path) -> tuple[dict[str, object], Path]:
    features, analysis_dir = extract_session_features(session_dir)
    profile = _load_or_create_profile(session_dir)

    legacy_predictions = run_legacy_map(features, profile)
    state_predictions = run_state_map_v1(features, profile)
    analysis_rows = _merge_analysis_rows(features, legacy_predictions, state_predictions)

    _write_jsonl(analysis_dir / "predictions_legacy_map.jsonl", legacy_predictions)
    _write_jsonl(analysis_dir / "predictions_state_map_v1.jsonl", state_predictions)
    _write_predictions_csv(analysis_dir / "predictions_combined.csv", legacy_predictions, state_predictions)
    _write_jsonl(analysis_dir / "hits_analysis.jsonl", analysis_rows)
    _write_table_csv(analysis_dir / "hits_analysis.csv", analysis_rows)

    legacy_metrics = _metrics(features, legacy_predictions)
    state_metrics = _metrics(features, state_predictions)
    winner = _winner(legacy_metrics, state_metrics)
    winner_predictions = state_predictions if winner == "state_map_v1" else legacy_predictions

    report = {
        "session_dir": str(session_dir),
        "patch_profile_path": str(_profile_path_for_session(session_dir)),
        "feature_count": len(features),
        "models": {
            "legacy_map": legacy_metrics,
            "state_map_v1": state_metrics,
        },
        "winner": winner,
    }
    _, calibrated_profile_path, calibration_summary = calibrate_profile_from_analysis(
        session_dir=session_dir,
        report=report,
        features=features,
        winner_predictions=winner_predictions,
    )
    report["patch_profile_path"] = str(calibrated_profile_path)
    report["calibration_summary_path"] = str(analysis_dir / "calibration_summary.json")
    report["analysis_rows_path"] = str(analysis_dir / "hits_analysis.jsonl")

    (analysis_dir / "benchmark_report.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    report_md = write_benchmark_markdown(
        session_dir=session_dir,
        analysis_dir=analysis_dir,
        report=report,
        calibration_summary=calibration_summary,
    )
    report["benchmark_markdown_path"] = str(report_md)
    (analysis_dir / "benchmark_report.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return report, analysis_dir


def _load_or_create_profile(session_dir: Path) -> dict[str, object]:
    path = _profile_path_for_session(session_dir)
    manager = PatchProfileManager(path.parent)
    patch_id = path.stem
    if not path.exists():
        manager.ensure_profile(patch_id=patch_id)
    loaded = manager.load_profile(patch_id)
    return loaded or {}


def _profile_path_for_session(session_dir: Path) -> Path:
    manifest_path = session_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    explicit = manifest.get("patch_profile_path")
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit)
    patch_id = str(manifest.get("patch_id") or "unlabeled")
    return PatchProfileManager().profile_path(patch_id)


def _metrics(features: list[dict[str, object]], predictions: list[dict[str, object]]) -> dict[str, object]:
    merged = []
    by_hit_id = {int(item["hit_id"]): item for item in predictions}
    for feature in features:
        pred = by_hit_id.get(int(feature["hit_id"]))
        if pred is None:
            continue
        merged.append({**feature, **pred})

    merged.sort(key=lambda item: float(item.get("intensity_input_norm", 0.0)))
    monotonicity = _monotonicity_score(merged, "velocity_main")
    brightness_continuity = _continuity_score(merged, "brightness_0_1")
    velocity_repeatability = _repeatability_score(merged, "velocity_main")
    decay_repeatability = _repeatability_score(merged, "decay_ms")
    avg_velocity = statistics.mean(float(item["velocity_main"]) for item in merged) if merged else 0.0
    avg_brightness = statistics.mean(float(item["brightness_0_1"]) for item in merged) if merged else 0.0
    avg_mute = statistics.mean(float(item["mute_damping_0_1"]) for item in merged) if merged else 0.0

    overall_score = statistics.mean(
        [
            monotonicity,
            brightness_continuity,
            velocity_repeatability,
            decay_repeatability,
        ]
    ) if merged else 0.0

    return {
        "hit_count": len(merged),
        "monotonicity_velocity": round(monotonicity, 6),
        "continuity_brightness": round(brightness_continuity, 6),
        "repeatability_velocity": round(velocity_repeatability, 6),
        "repeatability_decay": round(decay_repeatability, 6),
        "avg_velocity_main": round(avg_velocity, 6),
        "avg_brightness_0_1": round(avg_brightness, 6),
        "avg_mute_damping_0_1": round(avg_mute, 6),
        "overall_score": round(overall_score, 6),
    }


def _monotonicity_score(rows: list[dict[str, object]], field: str) -> float:
    if len(rows) < 2:
        return 1.0
    ok = 0
    total = 0
    for left, right in zip(rows, rows[1:]):
        delta_input = float(right["intensity_input_norm"]) - float(left["intensity_input_norm"])
        if delta_input < 0.01:
            continue
        total += 1
        if float(right[field]) + 1e-9 >= float(left[field]):
            ok += 1
    return 1.0 if total == 0 else ok / total


def _continuity_score(rows: list[dict[str, object]], field: str) -> float:
    if len(rows) < 2:
        return 1.0
    ratios = []
    for left, right in zip(rows, rows[1:]):
        delta_input = abs(float(right["intensity_input_norm"]) - float(left["intensity_input_norm"]))
        if delta_input < 0.01:
            continue
        delta_output = abs(float(right[field]) - float(left[field]))
        ratios.append(delta_output / delta_input)
    if not ratios:
        return 1.0
    mean_ratio = statistics.mean(ratios)
    return 1.0 / (1.0 + mean_ratio)


def _repeatability_score(rows: list[dict[str, object]], field: str) -> float:
    if len(rows) < 4:
        return 1.0
    buckets: list[list[float]] = [[], [], []]
    for row in rows:
        intensity = float(row["intensity_input_norm"])
        if intensity < 0.33:
            buckets[0].append(float(row[field]))
        elif intensity < 0.66:
            buckets[1].append(float(row[field]))
        else:
            buckets[2].append(float(row[field]))
    spreads = []
    for bucket in buckets:
        if len(bucket) >= 2:
            spreads.append(statistics.pstdev(bucket))
    if not spreads:
        return 1.0
    mean_spread = statistics.mean(spreads)
    bucket_values = [abs(value) for bucket in buckets for value in bucket]
    scale = max(1.0, statistics.mean(bucket_values)) if bucket_values else 1.0
    return 1.0 / (1.0 + (mean_spread / scale))


def _winner(legacy_metrics: dict[str, object], state_metrics: dict[str, object]) -> str:
    legacy_score = float(legacy_metrics.get("overall_score", 0.0))
    state_score = float(state_metrics.get("overall_score", 0.0))
    if state_score > legacy_score:
        return "state_map_v1"
    if legacy_score > state_score:
        return "legacy_map"
    return "tie"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in rows:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")


def _write_predictions_csv(
    path: Path,
    legacy_predictions: list[dict[str, object]],
    state_predictions: list[dict[str, object]],
) -> None:
    rows = legacy_predictions + state_predictions
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _merge_analysis_rows(
    features: list[dict[str, object]],
    legacy_predictions: list[dict[str, object]],
    state_predictions: list[dict[str, object]],
) -> list[dict[str, object]]:
    legacy_by_hit = {int(item["hit_id"]): item for item in legacy_predictions}
    state_by_hit = {int(item["hit_id"]): item for item in state_predictions}
    merged_rows: list[dict[str, object]] = []
    for feature in features:
        hit_id = int(feature["hit_id"])
        legacy = legacy_by_hit.get(hit_id, {})
        state = state_by_hit.get(hit_id, {})
        row = dict(feature)
        for key, value in legacy.items():
            if key in {"model_name", "hit_id"}:
                continue
            row[f"legacy_{key}"] = value
        for key, value in state.items():
            if key in {"model_name", "hit_id"}:
                continue
            row[f"state_{key}"] = value
        merged_rows.append(row)
    return merged_rows


def _write_table_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
