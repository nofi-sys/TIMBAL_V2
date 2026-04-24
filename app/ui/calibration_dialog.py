from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.io.timbal_input import TimbalCalibrationState

PAD_COUNT = 5
DEFAULT_CALIBRATION = {
    "min_hit": 24,
    "quiet": 28,
    "presence_noise": 16,
    "refractory": 38,
    "keep_connected": 900,
}


class CalibrationDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        config: dict,
        send_config: Callable[[dict], bool],
        request_state: Callable[[], bool],
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.send_config = send_config
        self.request_state = request_state
        self.pad_labels: list[QLabel] = []
        self.controls: dict[str, QSlider] = {}
        self.value_labels: dict[str, QLabel] = {}
        self._build_ui()
        self._load_from_config()
        self._refresh_value_labels()

    def _build_ui(self) -> None:
        self.setWindowTitle("Calibracion en vivo")
        self.resize(760, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        intro = QLabel(
            "Ajusta el firmware en caliente. 'Aplicar' manda los parametros al Leonardo actual."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        top = QHBoxLayout()
        top.setSpacing(16)
        root.addLayout(top)

        controls_box = QGroupBox("Parametros firmware")
        controls_layout = QFormLayout(controls_box)
        controls_layout.setSpacing(10)

        for key, label, min_value, max_value in (
            ("min_hit", "Umbral golpe", 8, 120),
            ("quiet", "Ventana quieta", 4, 96),
            ("presence_noise", "Ruido max estable", 2, 96),
            ("refractory", "Refractory ms", 10, 140),
            ("keep_connected", "Hold estable ms", 100, 2000),
        ):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_value, max_value)
            slider.valueChanged.connect(self._refresh_value_labels)
            value_label = QLabel()
            value_label.setMinimumWidth(54)
            row_layout.addWidget(slider, 1)
            row_layout.addWidget(value_label, 0)
            controls_layout.addRow(label, row)
            self.controls[key] = slider
            self.value_labels[key] = value_label

        top.addWidget(controls_box, 1)

        stats_box = QGroupBox("Pads")
        stats_layout = QGridLayout(stats_box)
        stats_layout.setHorizontalSpacing(10)
        stats_layout.setVerticalSpacing(10)
        for idx in range(PAD_COUNT):
            lbl = QLabel(f"P{idx + 1}: sin datos")
            lbl.setWordWrap(True)
            lbl.setMinimumWidth(210)
            stats_layout.addWidget(lbl, idx // 2, idx % 2)
            self.pad_labels.append(lbl)
        top.addWidget(stats_box, 1)

        self.status_label = QLabel("Esperando datos del firmware...")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        root.addLayout(buttons)

        btn_defaults = QPushButton("Recomendados")
        btn_defaults.clicked.connect(self._apply_defaults)
        buttons.addWidget(btn_defaults)

        btn_read = QPushButton("Leer firmware")
        btn_read.clicked.connect(self._request_state)
        buttons.addWidget(btn_read)

        btn_apply = QPushButton("Aplicar")
        btn_apply.clicked.connect(self._apply_to_firmware)
        buttons.addWidget(btn_apply)

        buttons.addStretch(1)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)

    def _refresh_value_labels(self) -> None:
        for key, slider in self.controls.items():
            self.value_labels[key].setText(str(int(slider.value())))

    def _stored_calibration(self) -> dict:
        raw = self.config.get("firmware_calibration")
        if not isinstance(raw, dict):
            return dict(DEFAULT_CALIBRATION)

        merged = dict(DEFAULT_CALIBRATION)
        for key in merged:
            try:
                merged[key] = int(raw.get(key, merged[key]))
            except (TypeError, ValueError):
                pass
        return merged

    def _load_from_config(self) -> None:
        values = self._stored_calibration()
        for key, slider in self.controls.items():
            slider.setValue(int(values.get(key, DEFAULT_CALIBRATION[key])))

    def _apply_defaults(self) -> None:
        for key, slider in self.controls.items():
            slider.setValue(DEFAULT_CALIBRATION[key])
        self.status_label.setText("Valores recomendados listos para aplicar.")

    def _current_payload(self) -> dict:
        return {key: int(slider.value()) for key, slider in self.controls.items()}

    def _request_state(self) -> None:
        if self.request_state():
            self.status_label.setText("Solicitando estado actual del firmware...")
        else:
            self.status_label.setText("No pude pedir el estado: puerto serial no disponible.")

    def _apply_to_firmware(self) -> None:
        payload = self._current_payload()
        self.config["firmware_calibration"] = dict(payload)
        if self.send_config(payload):
            self.status_label.setText("Configuracion enviada al firmware.")
        else:
            self.status_label.setText("No pude enviar la configuracion al firmware.")

    def update_pad_state(
        self,
        *,
        pad_idx: int,
        connected: bool | None,
        noise: int | None,
        value: int | None,
        peak: int | None,
    ) -> None:
        if pad_idx < 0 or pad_idx >= len(self.pad_labels):
            return

        if connected is True:
            state = "estable"
        elif connected is False:
            state = "flotante"
        else:
            state = "sin datos"

        parts = [f"P{pad_idx + 1}: {state}"]
        if value is not None:
            parts.append(f"val={value}")
        if noise is not None:
            parts.append(f"ruido={noise}")
        if peak is not None:
            parts.append(f"pico={peak}")
        self.pad_labels[pad_idx].setText(" | ".join(parts))

    def update_calibration_state(self, state: TimbalCalibrationState) -> None:
        mapping = {
            "min_hit": state.min_hit,
            "quiet": state.quiet,
            "presence_noise": state.presence_noise,
            "refractory": state.refractory,
            "keep_connected": state.keep_connected,
        }
        for key, value in mapping.items():
            if value is None or key not in self.controls:
                continue
            slider = self.controls[key]
            slider.blockSignals(True)
            slider.setValue(int(value))
            slider.blockSignals(False)
        self._refresh_value_labels()
        self.config["firmware_calibration"] = self._current_payload()
        self.status_label.setText("Estado del firmware sincronizado.")
