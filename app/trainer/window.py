"""Standalone rhythm trainer window."""

from __future__ import annotations

import sys
import time
from collections import deque
from dataclasses import dataclass

from mido import Message
from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.io.timbal_input import TimbalHit, TimbalInputRouter
from app.runtime import build_application, build_audio_engine
from app.theme.qss import TOKENS
from app.trainer.core import BeatTarget, FourFourQuarterTrainer, HitFeedback
from app.ui.testing_shell import MetricCard, SectionCard, StatusChip, build_testing_qss


@dataclass(frozen=True)
class ExercisePreset:
    key: str
    name: str
    summary: str
    bpm: int
    window_ms: int
    perfect_window_ms: int
    pattern_offsets: tuple[float, ...]
    pattern_labels: tuple[str, ...]
    count_in_beats: float = 2.0


TRAINER_PRESETS: tuple[ExercisePreset, ...] = (
    ExercisePreset(
        key="quarters",
        name="Pulso 4/4",
        summary="La referencia cae en cada negra. Es el modo base para medir estabilidad.",
        bpm=84,
        window_ms=140,
        perfect_window_ms=45,
        pattern_offsets=(0.0, 1.0, 2.0, 3.0),
        pattern_labels=("1", "2", "3", "4"),
    ),
    ExercisePreset(
        key="eighths",
        name="Corcheas",
        summary="Mas denso. Sirve para ver si el parche mantiene coherencia con subdivision constante.",
        bpm=82,
        window_ms=120,
        perfect_window_ms=40,
        pattern_offsets=(0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5),
        pattern_labels=("1", "+", "2", "+", "3", "+", "4", "+"),
    ),
    ExercisePreset(
        key="backbeat",
        name="2 y 4",
        summary="Solo entran referencias en 2 y 4. Bueno para ver lectura del pulso interno.",
        bpm=78,
        window_ms=150,
        perfect_window_ms=50,
        pattern_offsets=(1.0, 3.0),
        pattern_labels=("2", "4"),
    ),
    ExercisePreset(
        key="triplets",
        name="Tresillos",
        summary="Exige mas resolucion temporal. Aca suelen aparecer dobles y golpes tragados.",
        bpm=72,
        window_ms=125,
        perfect_window_ms=42,
        pattern_offsets=(
            0.0,
            1.0 / 3.0,
            2.0 / 3.0,
            1.0,
            4.0 / 3.0,
            5.0 / 3.0,
            2.0,
            7.0 / 3.0,
            8.0 / 3.0,
            3.0,
            10.0 / 3.0,
            11.0 / 3.0,
        ),
        pattern_labels=("1", "t", "l", "2", "t", "l", "3", "t", "l", "4", "t", "l"),
    ),
)


def _preset_by_key(key: str) -> ExercisePreset:
    for preset in TRAINER_PRESETS:
        if preset.key == key:
            return preset
    return TRAINER_PRESETS[0]


class BeatLaneWidget(QWidget):
    def __init__(self, trainer: FourFourQuarterTrainer, parent=None) -> None:
        super().__init__(parent)
        self.trainer = trainer
        self.setMinimumHeight(420)

    def _target_color(self, target: BeatTarget) -> QColor:
        if target.state == "perfect":
            return QColor("#22c55e")
        if target.state == "good":
            return QColor("#0ea5e9")
        if target.state == "miss":
            return QColor("#ef4444")
        return QColor(TOKENS["accent"])

    def paintEvent(self, event) -> None:  # pragma: no cover - UI drawing
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        panel = self.rect().adjusted(12, 12, -12, -12)
        painter.fillRect(panel, QColor("#0b1220"))
        painter.setPen(QPen(QColor("#243244"), 1))
        painter.drawRoundedRect(panel, 28, 28)

        lane_rect = panel.adjusted(36, 58, -36, -58)
        lane_y = lane_rect.center().y()
        hit_x = lane_rect.center().x()
        ahead_distance = lane_rect.width() * 0.42
        behind_distance = lane_rect.width() * 0.18

        painter.setPen(QPen(QColor("#334155"), 2))
        painter.drawLine(lane_rect.left(), lane_y, lane_rect.right(), lane_y)

        hit_zone = QRectF(hit_x - 42, lane_y - 78, 84, 156)
        painter.fillRect(hit_zone, QColor(59, 130, 246, 36))
        painter.setPen(QPen(QColor("#60a5fa"), 2))
        painter.drawRoundedRect(hit_zone, 20, 20)
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(
            QRectF(hit_x - 110, lane_y + 88, 220, 28),
            Qt.AlignCenter,
            "Zona de golpe",
        )

        now = time.perf_counter()
        for target in self.trainer.visible_targets(now):
            delta = target.scheduled_time - now
            if delta >= 0:
                ratio = min(1.0, delta / max(0.001, self.trainer.lookahead_seconds))
                x = hit_x + (ratio * ahead_distance)
            else:
                ratio = min(1.0, abs(delta) / max(0.001, self.trainer.beat_duration))
                x = hit_x - (ratio * behind_distance)

            size = 54
            rect = QRectF(x - size / 2.0, lane_y - size / 2.0, size, size)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._target_color(target))
            painter.drawRoundedRect(rect, 14, 14)
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(rect, Qt.AlignCenter, str(target.beat_in_bar))

        painter.setPen(QColor("#94a3b8"))
        painter.drawText(
            QRectF(lane_rect.left(), panel.top() + 16, lane_rect.width(), 24),
            Qt.AlignCenter,
            "Golpea cuando la referencia entra en la zona azul",
        )


class RhythmTrainerWindow(QMainWindow):
    def __init__(self, engine) -> None:
        super().__init__()
        self.engine = engine
        default_preset = TRAINER_PRESETS[0]
        self.trainer = FourFourQuarterTrainer(
            bpm=default_preset.bpm,
            window_ms=default_preset.window_ms,
            perfect_window_ms=default_preset.perfect_window_ms,
            count_in_beats=default_preset.count_in_beats,
            pattern_offsets=default_preset.pattern_offsets,
            pattern_labels=default_preset.pattern_labels,
        )
        self._control_sync = False
        self._recent_velocities: deque[int] = deque(maxlen=8)
        self.setWindowTitle("Trainer ritmico - Testeo")
        self._build_ui()

        self.input_router = TimbalInputRouter(self, prefer_midi_hits=False)
        self.input_router.hit_received.connect(self._on_external_hit)
        self.input_router.status_changed.connect(self._on_router_status)
        self.input_router.start()

        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(16)
        self.frame_timer.timeout.connect(self._tick)
        self.frame_timer.start()
        self._load_preset(default_preset)
        self._set_router_status("Buscando entrada...", tone="neutral")
        self._refresh_metrics()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(18)

        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        heading = QLabel("Trainer ritmico")
        heading.setObjectName("TestingHeadline")
        subtitle = QLabel(
            "Ventana de testeo pensada para chequear timing, lectura real del parche y respuesta del soundfont sin tocar la app central."
        )
        subtitle.setObjectName("TestingSubheadline")
        subtitle.setWordWrap(True)
        title_col.addWidget(heading)
        title_col.addWidget(subtitle)
        title_row.addLayout(title_col, 1)

        chips_col = QVBoxLayout()
        chips_col.setSpacing(8)
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        self.device_chip = StatusChip("Buscando entrada")
        self.exercise_chip = StatusChip("Pulso 4/4")
        self.exercise_chip.set_status("Pulso 4/4", tone="info")
        chips_row.addWidget(self.device_chip)
        chips_row.addWidget(self.exercise_chip)
        chips_col.addLayout(chips_row)
        self.router_detail_label = QLabel("Todavia no entro informacion del router.")
        self.router_detail_label.setObjectName("TestingHint")
        self.router_detail_label.setWordWrap(True)
        chips_col.addWidget(self.router_detail_label)
        title_row.addLayout(chips_col, 0)
        root.addLayout(title_row)

        metrics_row = QGridLayout()
        metrics_row.setHorizontalSpacing(12)
        metrics_row.setVerticalSpacing(12)
        self.metric_bpm = MetricCard("Tempo")
        self.metric_exercise = MetricCard("Ejercicio", value_size=20)
        self.metric_source = MetricCard("Entrada", value_size=20)
        self.metric_velocity = MetricCard("Dinamica", value_size=20)
        self.metric_streak = MetricCard("Racha")
        self.metric_accuracy = MetricCard("Promedio")
        self.metric_hit_rate = MetricCard("Precision")
        self.metric_bars = MetricCard("Compases")
        cards = [
            self.metric_bpm,
            self.metric_exercise,
            self.metric_source,
            self.metric_velocity,
            self.metric_streak,
            self.metric_accuracy,
            self.metric_hit_rate,
            self.metric_bars,
        ]
        for index, card in enumerate(cards):
            metrics_row.addWidget(card, index // 4, index % 4)
        root.addLayout(metrics_row)

        body = QHBoxLayout()
        body.setSpacing(16)
        self.board = BeatLaneWidget(self.trainer)
        body.addWidget(self.board, 1)

        side_col = QVBoxLayout()
        side_col.setSpacing(14)

        controls_card = SectionCard(
            "Controles rapidos",
            "Cambia ejercicio, tempo y tolerancia sin salir de la ventana.",
        )
        controls_grid = QGridLayout()
        controls_grid.setHorizontalSpacing(10)
        controls_grid.setVerticalSpacing(8)

        self.exercise_combo = QComboBox()
        for preset in TRAINER_PRESETS:
            self.exercise_combo.addItem(preset.name, preset.key)
        self.exercise_combo.currentIndexChanged.connect(self._on_exercise_changed)

        self.tempo_spin = QSpinBox()
        self.tempo_spin.setRange(40, 220)
        self.tempo_spin.valueChanged.connect(self._on_trainer_param_changed)

        self.window_spin = QSpinBox()
        self.window_spin.setRange(60, 280)
        self.window_spin.valueChanged.connect(self._on_trainer_param_changed)

        self.perfect_spin = QSpinBox()
        self.perfect_spin.setRange(20, 160)
        self.perfect_spin.valueChanged.connect(self._on_trainer_param_changed)

        self.dynamics_combo = QComboBox()
        self.dynamics_combo.addItem("Estabilizada", "stable")
        self.dynamics_combo.addItem("Directa", "raw")
        self.dynamics_combo.addItem("Amplificada", "wide")
        self.dynamics_combo.currentIndexChanged.connect(self._refresh_metrics)

        self.restart_button = QPushButton("Reiniciar ciclo")
        self.restart_button.clicked.connect(self._restart_session)

        controls = [
            ("Ejercicio", self.exercise_combo),
            ("Tempo", self.tempo_spin),
            ("Ventana", self.window_spin),
            ("Perfect", self.perfect_spin),
            ("Dinamica", self.dynamics_combo),
        ]
        for row, (label_text, widget) in enumerate(controls):
            label = QLabel(label_text)
            label.setObjectName("TestingHint")
            controls_grid.addWidget(label, row, 0)
            controls_grid.addWidget(widget, row, 1)
        controls_grid.addWidget(self.restart_button, len(controls), 0, 1, 2)
        controls_card.body_layout.addLayout(controls_grid)

        self.exercise_summary_label = QLabel("")
        self.exercise_summary_label.setObjectName("TestingHint")
        self.exercise_summary_label.setWordWrap(True)
        controls_card.body_layout.addWidget(self.exercise_summary_label)
        side_col.addWidget(controls_card)

        input_card = SectionCard(
            "Entrada real",
            "Te dice por donde entran los golpes y que dinamica termino sonando.",
        )
        self.last_input_label = QLabel("Sin golpes detectados todavia.")
        self.last_input_label.setObjectName("TestingHint")
        self.last_input_label.setWordWrap(True)
        self.feedback_label = QLabel("Esperando primer pulso")
        self.feedback_label.setObjectName("TrainerFeedback")
        self.feedback_label.setWordWrap(True)
        self.guide_label = QLabel(
            "Consejo: usa la barra espaciadora para entender el patron antes de probar con el parche."
        )
        self.guide_label.setObjectName("TestingHint")
        self.guide_label.setWordWrap(True)
        input_card.body_layout.addWidget(self.last_input_label)
        input_card.body_layout.addWidget(self.feedback_label)
        input_card.body_layout.addWidget(self.guide_label)
        side_col.addWidget(input_card)
        side_col.addStretch(1)
        body.addLayout(side_col, 0)
        root.addLayout(body, 1)

        self.setStyleSheet(
            self.styleSheet()
            + build_testing_qss(
                """
                QLabel#TrainerFeedback {
                    color: #e5e7eb;
                    font-size: 15px;
                    font-weight: 700;
                }
                """
            )
        )

    def closeEvent(self, event) -> None:
        self.input_router.close()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            self._register_hit(
                TimbalHit(
                    source="keyboard",
                    timestamp=time.perf_counter(),
                    note=60,
                    velocity=110,
                    pad_idx=None,
                )
            )
            event.accept()
            return
        super().keyPressEvent(event)

    def _tick(self) -> None:
        changed = self.trainer.update(time.perf_counter())
        if changed:
            self._refresh_metrics()
            self._apply_feedback(self.trainer.last_feedback)
        self.board.update()

    def _on_exercise_changed(self) -> None:
        self._load_preset(_preset_by_key(str(self.exercise_combo.currentData())))

    def _load_preset(self, preset: ExercisePreset) -> None:
        self._control_sync = True
        self.tempo_spin.setValue(preset.bpm)
        self.window_spin.setValue(preset.window_ms)
        self.perfect_spin.setValue(preset.perfect_window_ms)
        self._control_sync = False
        self.exercise_summary_label.setText(preset.summary)
        self.exercise_chip.set_status(preset.name, tone="info")
        self._apply_trainer_settings()

    def _on_trainer_param_changed(self) -> None:
        if self._control_sync:
            return
        self._apply_trainer_settings()

    def _apply_trainer_settings(self) -> None:
        preset = _preset_by_key(str(self.exercise_combo.currentData()))
        self.trainer.configure(
            bpm=self.tempo_spin.value(),
            window_ms=self.window_spin.value(),
            perfect_window_ms=self.perfect_spin.value(),
            count_in_beats=preset.count_in_beats,
            pattern_offsets=preset.pattern_offsets,
            pattern_labels=preset.pattern_labels,
        )
        self.metric_exercise.set_value(preset.name)
        self._apply_feedback(self.trainer.last_feedback)
        self._refresh_metrics()
        self.board.update()

    def _restart_session(self) -> None:
        self.trainer.restart()
        self._apply_feedback(self.trainer.last_feedback)
        self._refresh_metrics()
        self.board.update()

    def _set_router_status(self, text: str, *, tone: str) -> None:
        self.device_chip.set_status(text, tone=tone)

    def _on_router_status(self, text: str) -> None:
        clean = text.replace("INFO: ", "").replace("WARN: ", "")
        tone = "neutral"
        chip_text = "Buscando entrada"
        if "Escuchando serial" in text:
            tone = "ok"
            chip_text = "Serial activo"
        elif "Escuchando MIDI" in text:
            tone = "ok"
            chip_text = "MIDI activo"
        elif text.startswith("WARN:"):
            tone = "warn"
            chip_text = "Sin dispositivo"
        elif "No se detect" in text or "No hay" in text:
            tone = "warn"
            chip_text = "Sin dispositivo"
        elif clean:
            tone = "info"
            chip_text = "Entrada lista"
        self._set_router_status(chip_text, tone=tone)
        self.router_detail_label.setText(clean or "Sin detalle del router.")

    def _on_external_hit(self, hit: TimbalHit) -> None:
        self._register_hit(hit)

    def _register_hit(self, hit: TimbalHit) -> None:
        feedback = self.trainer.register_hit(hit.timestamp)
        played_velocity = self._play_hit_sound(hit.velocity)
        source_text = self._describe_hit(hit)
        self.metric_source.set_value(source_text)
        self.metric_velocity.set_value(f"{int(hit.velocity or 0)} -> {played_velocity}")
        self.last_input_label.setText(
            f"Ultimo hit: {source_text} | raw={int(hit.velocity or 0)} | salida={played_velocity}"
        )
        if hit.source == "serial":
            self._set_router_status("Serial activo", tone="ok")
        elif hit.source == "midi":
            self._set_router_status("MIDI activo", tone="ok")
        elif hit.source == "keyboard":
            self._set_router_status("Teclado", tone="info")
        self._apply_feedback(feedback)

    def _apply_feedback(self, feedback: HitFeedback) -> None:
        colors = {
            "perfect": "#22c55e",
            "good": "#38bdf8",
            "miss": "#ef4444",
            "offbeat": "#f59e0b",
            "idle": "#94a3b8",
        }
        color = colors.get(feedback.grade, "#e5e7eb")
        self.feedback_label.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: 700;"
        )
        self.feedback_label.setText(feedback.label)
        self._refresh_metrics()
        self.board.update()

    def _refresh_metrics(self) -> None:
        metrics = self.trainer.metrics
        preset = _preset_by_key(str(self.exercise_combo.currentData()))
        self.metric_bpm.set_value(f"{self.trainer.bpm} bpm")
        self.metric_exercise.set_value(preset.name)
        if self.metric_source.value_label.text() == "--":
            self.metric_source.set_value("Esperando")
        if self.metric_velocity.value_label.text() == "--":
            self.metric_velocity.set_value(self._dynamics_mode_label())
        self.metric_streak.set_value(f"{metrics.streak} / {metrics.best_streak}")
        self.metric_accuracy.set_value(f"{metrics.average_accuracy_ms:.0f} ms")
        self.metric_hit_rate.set_value(f"{metrics.hit_rate * 100:.0f}%")
        self.metric_bars.set_value(str(metrics.bars_completed))

    def _dynamics_mode_label(self) -> str:
        labels = {
            "stable": "estable",
            "raw": "directa",
            "wide": "amplificada",
        }
        return labels.get(str(self.dynamics_combo.currentData()), "estable")

    def _shape_velocity(self, velocity: int) -> int:
        raw = max(1, min(127, int(velocity or 110)))
        mode = str(self.dynamics_combo.currentData())
        anchor = raw
        if self._recent_velocities:
            anchor = int(round(sum(self._recent_velocities) / len(self._recent_velocities)))
        self._recent_velocities.append(raw)
        if mode == "raw":
            return raw
        if mode == "wide":
            shaped = int(round(anchor + ((raw - anchor) * 1.45)))
            return max(10, min(127, shaped))
        shaped = int(round((anchor * 0.72) + (raw * 0.28)))
        return max(18, min(127, shaped))

    def _play_hit_sound(self, velocity: int) -> int:
        shaped = self._shape_velocity(velocity)
        try:
            self.engine.disparar(Message("note_on", note=60, velocity=shaped, channel=0))
            QTimer.singleShot(
                170,
                lambda: self.engine.disparar(
                    Message("note_off", note=60, velocity=0, channel=0)
                ),
            )
        except Exception as exc:
            print(f"WARN: no se pudo reproducir hit del trainer: {exc}")
        return shaped

    def _describe_hit(self, hit: TimbalHit) -> str:
        if hit.source == "serial" and hit.pad_idx is not None:
            return f"serial P{hit.pad_idx + 1}"
        if hit.source == "midi" and hit.note is not None:
            return f"midi nota {hit.note}"
        if hit.source == "keyboard":
            return "teclado"
        if hit.note is not None:
            return f"{hit.source} nota {hit.note}"
        return hit.source


def run_trainer_window() -> None:
    app = build_application()
    try:
        engine, _ = build_audio_engine(None, allow_prompt=False)
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Error",
            f"No se pudo iniciar el trainer ritmico\n{exc}",
        )
        return

    window = RhythmTrainerWindow(engine)
    window.resize(1420, 900)
    window.show()
    sys.exit(app.exec_())
