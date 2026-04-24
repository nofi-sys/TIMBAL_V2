"""Core timing loop for the standalone rhythm trainer."""

from __future__ import annotations

import time
from dataclasses import dataclass


DEFAULT_PATTERN_OFFSETS = (0.0, 1.0, 2.0, 3.0)
DEFAULT_PATTERN_LABELS = ("1", "2", "3", "4")


@dataclass
class BeatTarget:
    index: int
    beat_in_bar: str
    scheduled_time: float
    state: str = "upcoming"
    accuracy_ms: float | None = None


@dataclass
class HitFeedback:
    label: str
    grade: str
    timestamp: float
    accuracy_ms: float | None = None


@dataclass
class TrainerMetrics:
    total_hits: int = 0
    perfect_hits: int = 0
    good_hits: int = 0
    misses: int = 0
    offbeat_hits: int = 0
    streak: int = 0
    best_streak: int = 0
    resolved_targets: int = 0
    accuracy_sum_ms: float = 0.0
    targets_per_bar: int = 4

    @property
    def successful_hits(self) -> int:
        return self.perfect_hits + self.good_hits

    @property
    def average_accuracy_ms(self) -> float:
        if self.successful_hits == 0:
            return 0.0
        return self.accuracy_sum_ms / self.successful_hits

    @property
    def hit_rate(self) -> float:
        if self.resolved_targets <= 0:
            return 0.0
        return self.successful_hits / self.resolved_targets

    @property
    def bars_completed(self) -> int:
        return self.resolved_targets // max(1, self.targets_per_bar)


class FourFourQuarterTrainer:
    def __init__(
        self,
        *,
        bpm: int = 80,
        lookahead_beats: float = 4.0,
        window_ms: int = 140,
        perfect_window_ms: int = 45,
        count_in_beats: float = 2.0,
        bar_length_beats: float = 4.0,
        pattern_offsets: list[float] | tuple[float, ...] | None = None,
        pattern_labels: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.bpm = bpm
        self.lookahead_beats = lookahead_beats
        self.window_ms = window_ms
        self.perfect_window_ms = perfect_window_ms
        self.count_in_beats = count_in_beats
        self.bar_length_beats = bar_length_beats
        self.pattern_offsets = list(DEFAULT_PATTERN_OFFSETS)
        self.pattern_labels = list(DEFAULT_PATTERN_LABELS)
        self.targets: list[BeatTarget] = []
        self.metrics = TrainerMetrics()
        self.last_feedback = HitFeedback(
            label="Esperando primer pulso",
            grade="idle",
            timestamp=time.perf_counter(),
            accuracy_ms=None,
        )
        self.configure(
            bpm=bpm,
            lookahead_beats=lookahead_beats,
            window_ms=window_ms,
            perfect_window_ms=perfect_window_ms,
            count_in_beats=count_in_beats,
            bar_length_beats=bar_length_beats,
            pattern_offsets=pattern_offsets,
            pattern_labels=pattern_labels,
        )

    @property
    def beat_duration(self) -> float:
        return 60.0 / float(self.bpm)

    @property
    def lookahead_seconds(self) -> float:
        return self.lookahead_beats * self.beat_duration

    @property
    def window_seconds(self) -> float:
        return self.window_ms / 1000.0

    def configure(
        self,
        *,
        bpm: int | None = None,
        lookahead_beats: float | None = None,
        window_ms: int | None = None,
        perfect_window_ms: int | None = None,
        count_in_beats: float | None = None,
        bar_length_beats: float | None = None,
        pattern_offsets: list[float] | tuple[float, ...] | None = None,
        pattern_labels: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        if bpm is not None:
            self.bpm = int(bpm)
        if lookahead_beats is not None:
            self.lookahead_beats = float(lookahead_beats)
        if window_ms is not None:
            self.window_ms = int(window_ms)
        if perfect_window_ms is not None:
            self.perfect_window_ms = int(perfect_window_ms)
        if count_in_beats is not None:
            self.count_in_beats = float(count_in_beats)
        if bar_length_beats is not None:
            self.bar_length_beats = float(bar_length_beats)

        offsets = list(pattern_offsets or DEFAULT_PATTERN_OFFSETS)
        labels = list(pattern_labels or DEFAULT_PATTERN_LABELS)
        if not offsets:
            offsets = list(DEFAULT_PATTERN_OFFSETS)
        if len(labels) != len(offsets):
            labels = [str(index + 1) for index in range(len(offsets))]
        self.pattern_offsets = offsets
        self.pattern_labels = labels
        self.restart()

    def restart(self) -> None:
        now = time.perf_counter()
        self.start_time = now + self.count_in_beats * self.beat_duration
        self.targets = []
        self.metrics = TrainerMetrics(targets_per_bar=len(self.pattern_offsets))
        self.last_feedback = HitFeedback(
            label="Cuenta 1, 2... y entra en la referencia",
            grade="idle",
            timestamp=now,
            accuracy_ms=None,
        )
        self._seed_targets(now)

    def _target_time(self, index: int) -> float:
        pattern_size = len(self.pattern_offsets)
        bar_index = index // pattern_size
        pattern_index = index % pattern_size
        beat_offset = (bar_index * self.bar_length_beats) + self.pattern_offsets[pattern_index]
        return self.start_time + (beat_offset * self.beat_duration)

    def _target_label(self, index: int) -> str:
        return self.pattern_labels[index % len(self.pattern_labels)]

    def _seed_targets(self, now: float) -> None:
        horizon = now + self.lookahead_seconds
        next_index = self.targets[-1].index + 1 if self.targets else 0
        while self._target_time(next_index) <= horizon:
            self.targets.append(
                BeatTarget(
                    index=next_index,
                    beat_in_bar=self._target_label(next_index),
                    scheduled_time=self._target_time(next_index),
                )
            )
            next_index += 1

    def update(self, now: float) -> bool:
        changed = False
        self._seed_targets(now)
        for target in self.targets:
            if target.state != "upcoming":
                continue
            if (now - target.scheduled_time) > self.window_seconds:
                target.state = "miss"
                self.metrics.misses += 1
                self.metrics.streak = 0
                self.metrics.resolved_targets += 1
                self.last_feedback = HitFeedback(
                    label=f"Miss en referencia {target.beat_in_bar}",
                    grade="miss",
                    timestamp=now,
                    accuracy_ms=None,
                )
                changed = True
        self._prune_targets(now)
        return changed

    def _prune_targets(self, now: float) -> None:
        cutoff = now - (self.beat_duration * 2.0)
        self.targets = [
            target
            for target in self.targets
            if target.state == "upcoming" or target.scheduled_time >= cutoff
        ]

    def register_hit(self, now: float) -> HitFeedback:
        self.update(now)
        self.metrics.total_hits += 1

        for target in self.targets:
            if target.state != "upcoming":
                continue
            delta = now - target.scheduled_time
            if delta < -self.window_seconds:
                break
            if abs(delta) <= self.window_seconds:
                accuracy_ms = abs(delta) * 1000.0
                target.accuracy_ms = accuracy_ms
                target.state = (
                    "perfect" if accuracy_ms <= self.perfect_window_ms else "good"
                )
                if target.state == "perfect":
                    self.metrics.perfect_hits += 1
                else:
                    self.metrics.good_hits += 1
                self.metrics.accuracy_sum_ms += accuracy_ms
                self.metrics.streak += 1
                self.metrics.best_streak = max(
                    self.metrics.best_streak,
                    self.metrics.streak,
                )
                self.metrics.resolved_targets += 1
                direction = "adelantado" if delta < 0 else "tarde"
                feedback = HitFeedback(
                    label=(
                        f"{target.state.title()} ref {target.beat_in_bar} "
                        f"({accuracy_ms:.0f} ms {direction})"
                    ),
                    grade=target.state,
                    timestamp=now,
                    accuracy_ms=accuracy_ms,
                )
                self.last_feedback = feedback
                return feedback

        self.metrics.offbeat_hits += 1
        self.metrics.streak = 0
        feedback = HitFeedback(
            label="Golpe fuera del patron",
            grade="offbeat",
            timestamp=now,
            accuracy_ms=None,
        )
        self.last_feedback = feedback
        return feedback

    def visible_targets(self, now: float) -> list[BeatTarget]:
        past_window = self.beat_duration * 0.8
        self._seed_targets(now)
        return [
            target
            for target in self.targets
            if (-past_window) <= (target.scheduled_time - now) <= self.lookahead_seconds
        ]
