"""Feature extraction for recorded timbal hits."""
from __future__ import annotations

import csv
import json
import math
from bisect import bisect_left
from pathlib import Path
from statistics import median

from app.host_analog.stream import AnalogSample
from app.timbal_lab.eval.session_loader import SessionData, load_session_dir

PRE_WINDOW_US = 10_000
POST_WINDOW_US = 40_000


def extract_session_features(session_dir: Path) -> tuple[list[dict[str, object]], Path]:
    session = load_session_dir(session_dir)
    features = extract_features(session)
    analysis_dir = session_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    _write_features_jsonl(analysis_dir / "hits_features.jsonl", features)
    _write_features_csv(analysis_dir / "hits_features.csv", features)
    return features, analysis_dir


def extract_features(session: SessionData) -> list[dict[str, object]]:
    samples_by_channel: dict[int, list[AnalogSample]] = {}
    times_by_channel: dict[int, list[int]] = {}
    for sample in session.samples:
        channel_samples = samples_by_channel.setdefault(sample.channel, [])
        channel_samples.append(sample)
    for channel, channel_samples in samples_by_channel.items():
        channel_samples.sort(key=lambda item: item.device_us)
        times_by_channel[channel] = [item.device_us for item in channel_samples]

    previous_hit_us_by_channel: dict[int, int] = {}
    features: list[dict[str, object]] = []
    for hit_index, hit in enumerate(session.hits):
        channel_samples = samples_by_channel.get(hit.channel, [])
        channel_times = times_by_channel.get(hit.channel, [])
        if not channel_samples:
            continue

        start_us = hit.device_us - PRE_WINDOW_US
        end_us = hit.device_us + POST_WINDOW_US
        start_idx = bisect_left(channel_times, start_us)
        end_idx = bisect_left(channel_times, end_us)
        window_samples = channel_samples[start_idx:end_idx]
        if not window_samples:
            continue

        baseline = _estimate_baseline(window_samples, hit.device_us)
        signed_series = [
            (sample.device_us - hit.device_us, float(sample.value) - baseline)
            for sample in window_samples
        ]
        relative_series = [
            (offset_us, max(0.0, value))
            for offset_us, value in signed_series
        ]

        peak_value, time_to_peak_ms = _peak_and_time(relative_series, 15_000)
        trough_value, time_to_trough_ms = _trough_and_time(signed_series, 15_000)
        negative_peak_abs = abs(trough_value)
        absolute_peak_value = _absolute_peak(signed_series, 15_000)
        initial_slope = _max_slope(relative_series, 2_000)
        max_abs_slope = _max_abs_slope(signed_series, 2_000)
        area_5ms = _area(relative_series, 5_000)
        area_15ms = _area(relative_series, 15_000)
        signed_area_15ms = _signed_area(signed_series, 15_000)
        absolute_area_15ms = _absolute_area(signed_series, 15_000)
        zero_crossings_15ms = _zero_crossings(signed_series, 15_000)
        attack_area = _area(relative_series, 6_000)
        tail_area = _area_range(relative_series, 6_000, 30_000)
        tail_ratio = 0.0 if attack_area <= 1e-9 else tail_area / attack_area
        pre_hit_energy = _pre_hit_energy(relative_series)

        prev_hit_us = previous_hit_us_by_channel.get(hit.channel)
        ioi_prev_ms = None if prev_hit_us is None else (hit.device_us - prev_hit_us) / 1000.0
        previous_hit_us_by_channel[hit.channel] = hit.device_us

        features.append(
            {
                "hit_id": hit_index,
                "channel": int(hit.channel),
                "device_us": int(hit.device_us),
                "host_time_s": float(hit.host_time),
                "raw_hit_value": int(hit.value),
                "peak_value": round(peak_value, 6),
                "trough_value": round(trough_value, 6),
                "negative_peak_abs": round(negative_peak_abs, 6),
                "absolute_peak_value": round(absolute_peak_value, 6),
                "dominant_polarity": _dominant_polarity(peak_value, negative_peak_abs),
                "initial_slope": round(initial_slope, 6),
                "max_abs_slope": round(max_abs_slope, 6),
                "area_5ms": round(area_5ms, 6),
                "area_15ms": round(area_15ms, 6),
                "signed_area_15ms": round(signed_area_15ms, 6),
                "absolute_area_15ms": round(absolute_area_15ms, 6),
                "time_to_peak_ms": round(time_to_peak_ms, 6),
                "time_to_trough_ms": round(time_to_trough_ms, 6),
                "zero_crossings_15ms": int(zero_crossings_15ms),
                "tail_ratio": round(tail_ratio, 6),
                "pre_hit_energy": round(pre_hit_energy, 6),
                "ioi_prev_ms": None if ioi_prev_ms is None else round(ioi_prev_ms, 6),
                "lag_ms": None if hit.lag_ms is None else round(float(hit.lag_ms), 6),
                "sample_count_window": len(window_samples),
                "source_kind": session.manifest.get("source_kind"),
            }
        )

    _annotate_intensity(features)
    return features


def _estimate_baseline(window_samples: list[AnalogSample], hit_device_us: int) -> float:
    pre_values = [sample.value for sample in window_samples if sample.device_us < hit_device_us]
    if pre_values:
        return float(median(pre_values))
    return float(window_samples[0].value)


def _peak_and_time(relative_series: list[tuple[int, float]], until_us: int) -> tuple[float, float]:
    candidates = [(offset_us, value) for offset_us, value in relative_series if 0 <= offset_us <= until_us]
    if not candidates:
        return 0.0, 0.0
    offset_us, peak_value = max(candidates, key=lambda item: item[1])
    return peak_value, offset_us / 1000.0


def _trough_and_time(signed_series: list[tuple[int, float]], until_us: int) -> tuple[float, float]:
    candidates = [
        (offset_us, value)
        for offset_us, value in signed_series
        if 0 <= offset_us <= until_us and value < 0.0
    ]
    if not candidates:
        return 0.0, 0.0
    offset_us, trough_value = min(candidates, key=lambda item: item[1])
    return trough_value, offset_us / 1000.0


def _absolute_peak(signed_series: list[tuple[int, float]], until_us: int) -> float:
    candidates = [
        abs(value)
        for offset_us, value in signed_series
        if 0 <= offset_us <= until_us
    ]
    return max(candidates) if candidates else 0.0


def _max_slope(relative_series: list[tuple[int, float]], until_us: int) -> float:
    best = 0.0
    previous = None
    for offset_us, value in relative_series:
        if offset_us < 0:
            previous = (offset_us, value)
            continue
        if offset_us > until_us:
            break
        if previous is not None:
            dt_us = offset_us - previous[0]
            if dt_us > 0:
                slope = (value - previous[1]) / (dt_us / 1000.0)
                if slope > best:
                    best = slope
        previous = (offset_us, value)
    return best


def _max_abs_slope(signed_series: list[tuple[int, float]], until_us: int) -> float:
    best = 0.0
    previous = None
    for offset_us, value in signed_series:
        if offset_us < 0:
            previous = (offset_us, value)
            continue
        if offset_us > until_us:
            break
        if previous is not None:
            dt_us = offset_us - previous[0]
            if dt_us > 0:
                slope = abs(value - previous[1]) / (dt_us / 1000.0)
                if slope > best:
                    best = slope
        previous = (offset_us, value)
    return best


def _area(relative_series: list[tuple[int, float]], until_us: int) -> float:
    return _area_range(relative_series, 0, until_us)


def _signed_area(signed_series: list[tuple[int, float]], until_us: int) -> float:
    return _signed_or_absolute_area(signed_series, 0, until_us, absolute=False)


def _absolute_area(signed_series: list[tuple[int, float]], until_us: int) -> float:
    return _signed_or_absolute_area(signed_series, 0, until_us, absolute=True)


def _signed_or_absolute_area(
    signed_series: list[tuple[int, float]],
    start_us: int,
    end_us: int,
    *,
    absolute: bool,
) -> float:
    area = 0.0
    previous = None
    for offset_us, value in signed_series:
        if offset_us < start_us:
            previous = (offset_us, value)
            continue
        if offset_us > end_us:
            break
        if previous is not None:
            dt_ms = (offset_us - previous[0]) / 1000.0
            if dt_ms > 0:
                sample_value = abs(previous[1]) if absolute else previous[1]
                area += sample_value * dt_ms
        previous = (offset_us, value)
    return area


def _zero_crossings(signed_series: list[tuple[int, float]], until_us: int) -> int:
    crossings = 0
    previous_sign = 0
    deadband = 2.0
    for offset_us, value in signed_series:
        if offset_us < 0:
            continue
        if offset_us > until_us:
            break
        sign = 1 if value > deadband else (-1 if value < -deadband else 0)
        if sign == 0:
            continue
        if previous_sign and sign != previous_sign:
            crossings += 1
        previous_sign = sign
    return crossings


def _dominant_polarity(positive_peak: float, negative_peak_abs: float) -> str:
    if positive_peak <= 1e-9 and negative_peak_abs <= 1e-9:
        return "flat"
    if positive_peak >= negative_peak_abs * 1.2:
        return "positive"
    if negative_peak_abs >= positive_peak * 1.2:
        return "negative"
    return "mixed"


def _area_range(relative_series: list[tuple[int, float]], start_us: int, end_us: int) -> float:
    area = 0.0
    previous = None
    for offset_us, value in relative_series:
        if offset_us < start_us:
            previous = (offset_us, value)
            continue
        if offset_us > end_us:
            break
        if previous is not None:
            dt_ms = (offset_us - previous[0]) / 1000.0
            if dt_ms > 0:
                area += max(0.0, previous[1]) * dt_ms
        previous = (offset_us, value)
    return area


def _pre_hit_energy(relative_series: list[tuple[int, float]]) -> float:
    values = [value for offset_us, value in relative_series if -PRE_WINDOW_US <= offset_us < 0]
    if not values:
        return 0.0
    mean_square = sum(value * value for value in values) / len(values)
    return math.sqrt(mean_square)


def _annotate_intensity(features: list[dict[str, object]]) -> None:
    if not features:
        return

    max_peak = max(float(item["peak_value"]) for item in features) or 1.0
    max_slope = max(float(item["initial_slope"]) for item in features) or 1.0
    max_area = max(float(item["area_5ms"]) for item in features) or 1.0
    max_pre = max(float(item["pre_hit_energy"]) for item in features) or 1.0

    for item in features:
        peak_norm = float(item["peak_value"]) / max_peak
        slope_norm = float(item["initial_slope"]) / max_slope
        area_norm = float(item["area_5ms"]) / max_area
        pre_norm = float(item["pre_hit_energy"]) / max_pre
        intensity = (0.5 * peak_norm) + (0.3 * slope_norm) + (0.15 * area_norm) + (0.05 * pre_norm)
        item["peak_norm"] = round(peak_norm, 6)
        item["slope_norm"] = round(slope_norm, 6)
        item["area_5ms_norm"] = round(area_norm, 6)
        item["pre_hit_energy_norm"] = round(pre_norm, 6)
        item["intensity_input_norm"] = round(min(1.0, max(0.0, intensity)), 6)


def _write_features_jsonl(path: Path, features: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in features:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")


def _write_features_csv(path: Path, features: list[dict[str, object]]) -> None:
    if not features:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(features[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(features)
