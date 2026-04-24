"""Qt window for the host-side analog processing experiment."""

from __future__ import annotations

import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from mido import Message
from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
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

from app.host_analog.stream import AnalogHit, AnalogSample, AnalogStreamReader
from app.runtime import build_application, build_audio_engine
from app.theme.qss import TOKENS
from app.ui.testing_shell import MetricCard, SectionCard, StatusChip, build_testing_qss


@dataclass(frozen=True)
class DetectorPreset:
    key: str
    name: str
    summary: str
    threshold: int
    delta: int
    refractory_ms: int


ANALOG_PRESETS: tuple[DetectorPreset, ...] = (
    DetectorPreset(
        key="balanced",
        name="Balanceado",
        summary="Punto medio para empezar. Suele servir para un solo parche conectado.",
        threshold=80,
        delta=25,
        refractory_ms=70,
    ),
    DetectorPreset(
        key="soft",
        name="Sensitivo",
        summary="Mas facil para golpes suaves, pero puede abrir la puerta a ruido o dobles.",
        threshold=60,
        delta=16,
        refractory_ms=60,
    ),
    DetectorPreset(
        key="strict",
        name="Estricto",
        summary="Mas duro con falsos disparos. Bueno si el parche esta muy caliente o rebota mucho.",
        threshold=120,
        delta=38,
        refractory_ms=90,
    ),
)


def _preset_by_key(key: str) -> DetectorPreset | None:
    for preset in ANALOG_PRESETS:
        if preset.key == key:
            return preset
    return None


def _find_matching_preset(threshold: int, delta: int, refractory_ms: int) -> str:
    for preset in ANALOG_PRESETS:
        if (
            preset.threshold == threshold
            and preset.delta == delta
            and preset.refractory_ms == refractory_ms
        ):
            return preset.key
    return "manual"


class WaveformWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.samples_by_channel: dict[int, deque[AnalogSample]] = defaultdict(
            lambda: deque(maxlen=400)
        )
        self.selected_channel = 0
        self.threshold = 80
        self.last_hit_value: int | None = None
        self.setMinimumHeight(460)

    def add_samples(self, samples: list[AnalogSample]) -> None:
        for sample in samples:
            self.samples_by_channel[sample.channel].append(sample)
        self.update()

    def set_selected_channel(self, channel: int) -> None:
        self.selected_channel = channel
        self.update()

    def set_threshold(self, threshold: int) -> None:
        self.threshold = threshold
        self.update()

    def set_last_hit(self, hit: AnalogHit) -> None:
        self.last_hit_value = hit.value
        self.update()

    def paintEvent(self, event) -> None:  # pragma: no cover - UI drawing
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        panel = self.rect().adjusted(12, 12, -12, -12)
        painter.fillRect(panel, QColor("#0b1220"))
        painter.setPen(QPen(QColor("#243244"), 1))
        painter.drawRoundedRect(panel, 24, 24)

        chart = panel.adjusted(20, 24, -20, -32)
        mid_y = chart.center().y()
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawLine(chart.left(), mid_y, chart.right(), mid_y)

        threshold_y = chart.bottom() - (self.threshold / 1023.0) * chart.height()
        painter.setPen(QPen(QColor("#f59e0b"), 1, Qt.DashLine))
        painter.drawLine(chart.left(), int(threshold_y), chart.right(), int(threshold_y))

        samples = list(self.samples_by_channel.get(self.selected_channel, ()))
        if len(samples) >= 2:
            poly = QPolygonF()
            count = len(samples)
            for index, sample in enumerate(samples):
                x = chart.left() + (index / max(1, count - 1)) * chart.width()
                y = chart.bottom() - (sample.value / 1023.0) * chart.height()
                poly.append(QRectF(x, y, 0, 0).topLeft())
            painter.setPen(QPen(QColor("#60a5fa"), 2))
            painter.drawPolyline(poly)

        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(
            QRectF(chart.left(), panel.top() + 2, chart.width(), 20),
            Qt.AlignLeft,
            f"Canal {self.selected_channel}",
        )
        if self.last_hit_value is not None:
            painter.drawText(
                QRectF(chart.left(), panel.top() + 2, chart.width(), 20),
                Qt.AlignRight,
                f"Ultimo pico {self.last_hit_value}",
            )


class HostAnalogWindow(QMainWindow):
    def __init__(self, engine) -> None:
        super().__init__()
        self.engine = engine
        self.reader = AnalogStreamReader(self)
        self.reader.status_changed.connect(self._on_status)
        self.reader.samples_received.connect(self._on_samples)
        self.reader.hit_detected.connect(self._on_hit)

        self.sample_counts: dict[int, int] = defaultdict(int)
        self.last_sample_times: dict[int, float] = {}
        self.latest_values: dict[int, int] = {}
        self.recent_sample_times: dict[int, deque[float]] = defaultdict(
            lambda: deque(maxlen=240)
        )
        self.detected_hits = 0
        self.last_lag_ms: float | None = None
        self._control_sync = False

        self.setWindowTitle("Entrada analogica - Testeo")
        self._build_ui()
        self._apply_detector_preset("balanced")
        self.reader.start()

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(120)
        self.ui_timer.timeout.connect(self._refresh_metrics)
        self.ui_timer.start()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = QLabel("Entrada analogica")
        title.setObjectName("TestingHeadline")
        subtitle = QLabel(
            "Lee muestras crudas del Arduino, detecta golpes en la PC y te deja comparar sensibilidad, lag y estabilidad sin tocar el runtime principal."
        )
        subtitle.setObjectName("TestingSubheadline")
        subtitle.setWordWrap(True)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_row.addLayout(title_col, 1)

        status_col = QVBoxLayout()
        status_col.setSpacing(8)
        self.source_chip = StatusChip("Buscando Arduino")
        self.status_label = QLabel("Esperando stream analogico...")
        self.status_label.setObjectName("TestingHint")
        self.status_label.setWordWrap(True)
        status_col.addWidget(self.source_chip, 0, Qt.AlignRight)
        status_col.addWidget(self.status_label)
        title_row.addLayout(status_col, 0)
        root.addLayout(title_row)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)
        self.port_metric = MetricCard("Puerto", value_size=20)
        self.rate_metric = MetricCard("Muestras/s")
        self.hit_metric = MetricCard("Golpes")
        self.lag_metric = MetricCard("Lag")
        self.value_metric = MetricCard("Valor")
        self.channel_metric = MetricCard("Canal", value_size=20)
        cards = [
            self.port_metric,
            self.rate_metric,
            self.hit_metric,
            self.lag_metric,
            self.value_metric,
            self.channel_metric,
        ]
        for index, card in enumerate(cards):
            metrics.addWidget(card, index // 3, index % 3)
        root.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(16)
        self.waveform = WaveformWidget()
        body.addWidget(self.waveform, 1)

        side_col = QVBoxLayout()
        side_col.setSpacing(14)

        source_card = SectionCard(
            "Fuente",
            "Reintenta el puerto si conectaste el Arduino despues de abrir la ventana.",
        )
        self.refresh_button = QPushButton("Reintentar puerto")
        self.refresh_button.setObjectName("SecondaryAction")
        self.refresh_button.clicked.connect(self._restart_reader)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["0", "1", "2", "3", "4"])
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        source_grid = QGridLayout()
        source_grid.setHorizontalSpacing(10)
        source_grid.setVerticalSpacing(8)
        source_grid.addWidget(QLabel("Canal"), 0, 0)
        source_grid.addWidget(self.channel_combo, 0, 1)
        source_grid.addWidget(self.refresh_button, 1, 0, 1, 2)
        self.source_detail_label = QLabel("Sin puerto abierto.")
        self.source_detail_label.setObjectName("TestingHint")
        self.source_detail_label.setWordWrap(True)
        source_card.body_layout.addLayout(source_grid)
        source_card.body_layout.addWidget(self.source_detail_label)
        side_col.addWidget(source_card)

        detector_card = SectionCard(
            "Detector",
            "Empieza con un preset y despues afina threshold, delta y refractory si hace falta.",
        )
        self.preset_combo = QComboBox()
        for preset in ANALOG_PRESETS:
            self.preset_combo.addItem(preset.name, preset.key)
        self.preset_combo.addItem("Manual", "manual")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 1023)
        self.threshold_spin.valueChanged.connect(self._on_manual_detector_change)

        self.delta_spin = QSpinBox()
        self.delta_spin.setRange(0, 1023)
        self.delta_spin.valueChanged.connect(self._on_manual_detector_change)

        self.refractory_spin = QSpinBox()
        self.refractory_spin.setRange(1, 500)
        self.refractory_spin.valueChanged.connect(self._on_manual_detector_change)

        detector_grid = QGridLayout()
        detector_grid.setHorizontalSpacing(10)
        detector_grid.setVerticalSpacing(8)
        detector_grid.addWidget(QLabel("Preset"), 0, 0)
        detector_grid.addWidget(self.preset_combo, 0, 1)
        detector_grid.addWidget(QLabel("Threshold"), 1, 0)
        detector_grid.addWidget(self.threshold_spin, 1, 1)
        detector_grid.addWidget(QLabel("Delta"), 2, 0)
        detector_grid.addWidget(self.delta_spin, 2, 1)
        detector_grid.addWidget(QLabel("Refractory"), 3, 0)
        detector_grid.addWidget(self.refractory_spin, 3, 1)
        self.detector_hint_label = QLabel("")
        self.detector_hint_label.setObjectName("TestingHint")
        self.detector_hint_label.setWordWrap(True)
        detector_card.body_layout.addLayout(detector_grid)
        detector_card.body_layout.addWidget(self.detector_hint_label)
        side_col.addWidget(detector_card)

        audio_card = SectionCard(
            "Audio y lectura",
            "Te muestra el ultimo hit util y te deja disparar una nota de prueba.",
        )
        self.note_spin = QSpinBox()
        self.note_spin.setRange(0, 127)
        self.note_spin.setValue(60)
        self.test_button = QPushButton("Test sonido")
        self.test_button.clicked.connect(self._play_test_note)
        audio_grid = QGridLayout()
        audio_grid.setHorizontalSpacing(10)
        audio_grid.setVerticalSpacing(8)
        audio_grid.addWidget(QLabel("Nota"), 0, 0)
        audio_grid.addWidget(self.note_spin, 0, 1)
        audio_grid.addWidget(self.test_button, 1, 0, 1, 2)
        self.feedback_label = QLabel("Sin golpes detectados todavia.")
        self.feedback_label.setObjectName("AnalogFeedback")
        self.feedback_label.setWordWrap(True)
        audio_card.body_layout.addLayout(audio_grid)
        audio_card.body_layout.addWidget(self.feedback_label)
        side_col.addWidget(audio_card)
        side_col.addStretch(1)
        body.addLayout(side_col, 0)

        root.addLayout(body, 1)
        self.channel_metric.set_value("ch 0")
        self.setStyleSheet(
            self.styleSheet()
            + build_testing_qss(
                """
                QLabel#AnalogFeedback {
                    color: #e5e7eb;
                    font-size: 14px;
                    font-weight: 700;
                }
                """
            )
        )

    def closeEvent(self, event) -> None:
        self.reader.close()
        event.accept()

    def _set_source_state(self, text: str, tone: str) -> None:
        self.source_chip.set_status(text, tone=tone)

    def _on_status(self, text: str) -> None:
        clean = text.replace("INFO: ", "").replace("WARN: ", "")
        self.status_label.setText(clean)
        self.source_detail_label.setText(clean)
        if text.startswith("WARN:"):
            self._set_source_state("Sin stream", "warn")
        elif "Analog stream en" in text:
            self._set_source_state("Arduino listo", "ok")
        else:
            self._set_source_state("Esperando", "info")
        if self.reader.serial_info is not None:
            self.port_metric.set_value(self.reader.serial_info.device)

    def _on_samples(self, samples: list[AnalogSample]) -> None:
        self.waveform.add_samples(samples)
        now = time.perf_counter()
        for sample in samples:
            self.sample_counts[sample.channel] += 1
            self.last_sample_times[sample.channel] = now
            self.latest_values[sample.channel] = sample.value
            self.recent_sample_times[sample.channel].append(sample.host_time)

    def _on_hit(self, hit: AnalogHit) -> None:
        selected_channel = int(self.channel_combo.currentText())
        if hit.channel != selected_channel:
            return
        self.detected_hits += 1
        self.last_lag_ms = hit.lag_ms
        self.waveform.set_last_hit(hit)
        lag_text = "--" if hit.lag_ms is None else f"{hit.lag_ms:.1f} ms"
        self.feedback_label.setText(
            f"Hit en ch {hit.channel}: value={hit.value} | lag~{lag_text}"
        )
        self._play_note(self.note_spin.value(), min(127, max(10, hit.value // 8)))
        self._refresh_metrics()

    def _on_channel_changed(self) -> None:
        channel = int(self.channel_combo.currentText())
        self.waveform.set_selected_channel(channel)
        self.channel_metric.set_value(f"ch {channel}")
        self._refresh_metrics()

    def _on_preset_changed(self) -> None:
        if self._control_sync:
            return
        key = str(self.preset_combo.currentData())
        if key == "manual":
            self.detector_hint_label.setText(
                "Modo manual. Usa los campos para afinar detector y mirar la forma de onda."
            )
            return
        self._apply_detector_preset(key)

    def _apply_detector_preset(self, key: str) -> None:
        preset = _preset_by_key(key)
        if preset is None:
            return
        self._control_sync = True
        self.preset_combo.setCurrentIndex(self.preset_combo.findData(preset.key))
        self.threshold_spin.setValue(preset.threshold)
        self.delta_spin.setValue(preset.delta)
        self.refractory_spin.setValue(preset.refractory_ms)
        self._control_sync = False
        self.detector_hint_label.setText(preset.summary)
        self._apply_detector_config()

    def _on_manual_detector_change(self) -> None:
        if self._control_sync:
            return
        self._sync_preset_combo()
        self._apply_detector_config()

    def _sync_preset_combo(self) -> None:
        key = _find_matching_preset(
            self.threshold_spin.value(),
            self.delta_spin.value(),
            self.refractory_spin.value(),
        )
        self._control_sync = True
        self.preset_combo.setCurrentIndex(self.preset_combo.findData(key))
        self._control_sync = False
        preset = _preset_by_key(key)
        if preset is None:
            self.detector_hint_label.setText(
                "Modo manual. Ajusta mirando la distancia entre ruido, pico y dobles."
            )
        else:
            self.detector_hint_label.setText(preset.summary)

    def _apply_detector_config(self) -> None:
        self.reader.configure_detector(
            threshold=self.threshold_spin.value(),
            delta=self.delta_spin.value(),
            refractory_ms=self.refractory_spin.value(),
        )
        self.waveform.set_threshold(self.threshold_spin.value())

    def _restart_reader(self) -> None:
        self._set_source_state("Reintentando", "info")
        self.reader.close()
        self.reader.start()

    def _play_test_note(self) -> None:
        self._play_note(self.note_spin.value(), 96)

    def _play_note(self, note: int, velocity: int) -> None:
        try:
            self.engine.disparar(
                Message("note_on", note=int(note), velocity=int(velocity), channel=0)
            )
            QTimer.singleShot(
                140,
                lambda: self.engine.disparar(
                    Message("note_off", note=int(note), velocity=0, channel=0)
                ),
            )
        except Exception as exc:
            print(f"WARN: no se pudo reproducir el hit host-side: {exc}")

    def _refresh_metrics(self) -> None:
        channel = int(self.channel_combo.currentText())
        sample_times = self.recent_sample_times.get(channel)
        if sample_times and len(sample_times) >= 2:
            span = max(0.001, sample_times[-1] - sample_times[0])
            sample_rate = int((len(sample_times) - 1) / span)
        else:
            sample_rate = 0
        self.rate_metric.set_value(str(sample_rate))
        self.hit_metric.set_value(str(self.detected_hits))
        self.value_metric.set_value(str(self.latest_values.get(channel, 0)))
        self.lag_metric.set_value(
            "--" if self.last_lag_ms is None else f"{self.last_lag_ms:.1f} ms"
        )


def run_host_analog_window() -> None:
    app = build_application()
    try:
        engine, _ = build_audio_engine(None, allow_prompt=False)
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Error",
            f"No se pudo iniciar el experimento host-side\n{exc}",
        )
        return

    window = HostAnalogWindow(engine)
    window.resize(1420, 900)
    window.show()
    sys.exit(app.exec_())
