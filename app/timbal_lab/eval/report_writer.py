"""Human-readable analysis reports for timbal lab sessions."""
from __future__ import annotations

from pathlib import Path


def write_benchmark_markdown(
    *,
    session_dir: Path,
    analysis_dir: Path,
    report: dict[str, object],
    calibration_summary: dict[str, object],
) -> Path:
    models = report.get("models", {})
    winner = str(report.get("winner", "unknown"))
    thresholds = calibration_summary.get("thresholds", {})
    temporal = calibration_summary.get("temporal", {})
    analysis = calibration_summary.get("analysis", {})

    lines = [
        f"# Benchmark Session {session_dir.name}",
        "",
        f"- Session: `{session_dir}`",
        f"- Winner: `{winner}`",
        f"- Feature count: `{report.get('feature_count', 0)}`",
        f"- Patch profile: `{calibration_summary.get('patch_profile_path', report.get('patch_profile_path', 'n/a'))}`",
        "",
        "## Model Metrics",
        "",
        "| Model | Score | Monotonicity | Continuity | Repeat Velocity | Repeat Decay | Avg Velocity | Avg Brightness |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    if isinstance(models, dict):
        for model_name, metrics in models.items():
            if not isinstance(metrics, dict):
                continue
            lines.append(
                "| "
                f"{model_name} | "
                f"{metrics.get('overall_score', 0)} | "
                f"{metrics.get('monotonicity_velocity', 0)} | "
                f"{metrics.get('continuity_brightness', 0)} | "
                f"{metrics.get('repeatability_velocity', 0)} | "
                f"{metrics.get('repeatability_decay', 0)} | "
                f"{metrics.get('avg_velocity_main', 0)} | "
                f"{metrics.get('avg_brightness_0_1', 0)} |"
            )

    lines.extend(
        [
            "",
            "## Detector Recommendation",
            "",
            f"- hit_threshold: `{thresholds.get('hit_threshold')}`",
            f"- delta_threshold: `{thresholds.get('delta_threshold')}`",
            f"- refractory_ms: `{thresholds.get('refractory_ms')}`",
            "",
            "## Temporal Recommendation",
            "",
            f"- tau_energy_ms: `{temporal.get('tau_energy_ms')}`",
            f"- tau_decay_free_ms: `{temporal.get('tau_decay_free_ms')}`",
            f"- tau_decay_hold_ms: `{temporal.get('tau_decay_hold_ms')}`",
            "",
            "## Calibration Summary",
            "",
            f"- last_calibration_at_local: `{analysis.get('last_calibration_at_local')}`",
            f"- avg_lag_ms: `{analysis.get('avg_lag_ms')}`",
            f"- noise_rms: `{analysis.get('noise_rms')}`",
            f"- avg_decay_ms: `{analysis.get('avg_decay_ms')}`",
            f"- avg_brightness: `{analysis.get('avg_brightness')}`",
            f"- avg_mute_damping: `{analysis.get('avg_mute_damping')}`",
            "",
            "## Next Use",
            "",
            "- Volve a abrir una sesion con este mismo `patch_id` para reutilizar automaticamente el perfil calibrado.",
            "- Si la deteccion sigue sensible o ciega, ajusta primero `hit_threshold` y `delta_threshold` antes de tocar el modelo.",
            "- Si el benchmark no mejora de forma consistente, el siguiente limite ya no es software sino observabilidad del cableado actual.",
            "",
        ]
    )

    path = analysis_dir / "benchmark_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
