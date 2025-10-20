"""Effects controls migrated from the legacy UI."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QCheckBox,
    QSlider,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)

from app.ui.pages.effects_presets import get_reverb_preset
from app.state.settings import load_config, save_config


class EffectsPage(QWidget):
    def __init__(self, engine, config: dict | None = None):
        super().__init__()
        self.audio = engine
        self.config = config if config is not None else load_config()
        self.min_velocity = 8
        initial_level = int(round(getattr(self.audio, 'reverb_level', 0.4) * 100))
        self._last_reverb_level_value = initial_level if initial_level > 0 else 40
        self.setObjectName("EffectsPage")
        self._build_ui()
        self.setStyleSheet(
            "QWidget#EffectsPage{color:#e5e7eb;}"
            "QWidget#EffectsPage QLabel{color:#e5e7eb;}"
            "QWidget#EffectsPage QGroupBox{color:#e5e7eb;}"
            "QWidget#EffectsPage QCheckBox{color:#e5e7eb;}"
            "QWidget#EffectsPage QPushButton{color:#e5e7eb;}"
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        reverb_box = QGroupBox("Reverb")
        rev_layout = QVBoxLayout()

        self.chk_rev_on = QCheckBox("Reverb ON")
        self.chk_rev_on.setChecked(True)
        self.chk_rev_on.stateChanged.connect(lambda state: self._toggle_reverb(bool(state)))
        rev_layout.addWidget(self.chk_rev_on)

        self.lbl_rev_level = QLabel()
        self.sld_rev_level = QSlider(Qt.Horizontal)
        self.sld_rev_level.setRange(0, 100)
        self.sld_rev_level.setValue(int(self.audio.reverb_level * 100))
        self.sld_rev_level.valueChanged.connect(self._apply_reverb_level)
        rev_layout.addWidget(self.lbl_rev_level)
        rev_layout.addWidget(self.sld_rev_level)

        self.lbl_rev_room = QLabel()
        self.sld_rev_room = QSlider(Qt.Horizontal)
        self.sld_rev_room.setRange(0, 100)
        self.sld_rev_room.setValue(int(self.audio.reverb_roomsize * 100))
        self.sld_rev_room.valueChanged.connect(self._apply_reverb_room)
        rev_layout.addWidget(self.lbl_rev_room)
        rev_layout.addWidget(self.sld_rev_room)

        self.lbl_rev_damp = QLabel()
        self.sld_rev_damp = QSlider(Qt.Horizontal)
        self.sld_rev_damp.setRange(0, 100)
        self.sld_rev_damp.setValue(int(self.audio.reverb_damping * 100))
        self.sld_rev_damp.valueChanged.connect(self._apply_reverb_damp)
        rev_layout.addWidget(self.lbl_rev_damp)
        rev_layout.addWidget(self.sld_rev_damp)

        presets_row = QHBoxLayout()
        for key, label in (("seco", "Preset: Seco"), ("media", "Preset: Media"), ("sala", "Preset: Sala")):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, name=key: self.apply_reverb_preset(name))
            presets_row.addWidget(btn)
        rev_layout.addLayout(presets_row)

        reverb_box.setLayout(rev_layout)
        layout.addWidget(reverb_box)

        dynamics_box = QGroupBox("Dinamica")
        dyn_layout = QVBoxLayout()

        self.lbl_bright = QLabel()
        self.sld_bright = QSlider(Qt.Horizontal)
        self.sld_bright.setRange(0, 127)
        self.sld_bright.setValue(100)
        self.sld_bright.valueChanged.connect(self._apply_brightness)
        dyn_layout.addWidget(self.lbl_bright)
        dyn_layout.addWidget(self.sld_bright)

        current_boost = float(getattr(self.audio, 'velocity_gain', 0.0))
        if current_boost <= 0.0 or abs(current_boost - 3.0) < 1e-6:
            current_boost = 30.0
            try:
                self.audio.velocity_gain = current_boost
            except Exception:
                pass
        self.lbl_boost = QLabel(f"Boost (vel x): {current_boost:.0f}")
        self.sld_boost = QSlider(Qt.Horizontal)
        self.sld_boost.setRange(0, 50)
        self.sld_boost.setSingleStep(1)
        self.sld_boost.setValue(int(round(current_boost)))
        self.sld_boost.valueChanged.connect(self._apply_boost)
        dyn_layout.addWidget(self.lbl_boost)
        dyn_layout.addWidget(self.sld_boost)

        self.lbl_master = QLabel(f"Master boost (dB): {self.audio.master_db:+.1f}")
        self.sld_master = QSlider(Qt.Horizontal)
        self.sld_master.setRange(-600, int(getattr(self.audio, 'max_master_db', 30.0) * 10))
        self.sld_master.setValue(int(self.audio.master_db * 10))
        self.sld_master.valueChanged.connect(self._apply_master)
        dyn_layout.addWidget(self.lbl_master)
        dyn_layout.addWidget(self.sld_master)

        self.chk_limiter = QCheckBox("Limitador ON")
        self.chk_limiter.setChecked(self.audio.limiter_enabled)
        self.chk_limiter.stateChanged.connect(lambda state: self.audio.set_limiter_enabled(bool(state)))
        dyn_layout.addWidget(self.chk_limiter)

        self.lbl_gate = QLabel(f"Filtro golpes leves: {self.min_velocity}")
        self.sld_gate = QSlider(Qt.Horizontal)
        self.sld_gate.setRange(0, 40)
        self.sld_gate.setValue(self.min_velocity)
        self.sld_gate.valueChanged.connect(self._apply_gate)
        dyn_layout.addWidget(self.lbl_gate)
        dyn_layout.addWidget(self.sld_gate)

        dynamics_box.setLayout(dyn_layout)
        layout.addWidget(dynamics_box)

        config_box = QGroupBox("Configuracion")
        cfg_layout = QVBoxLayout()
        self.lbl_sf = QLabel(self._current_sf_text())
        self.btn_sf = QPushButton("Seleccionar SoundFont")
        self.btn_sf.clicked.connect(self._select_sf2)
        cfg_layout.addWidget(self.lbl_sf)
        cfg_layout.addWidget(self.btn_sf, alignment=Qt.AlignLeft)
        config_box.setLayout(cfg_layout)
        layout.addWidget(config_box)
        layout.addStretch(1)

        self._apply_reverb_room(self.sld_rev_room.value())
        self._apply_reverb_damp(self.sld_rev_damp.value())
        self._apply_reverb_level(self.sld_rev_level.value())
        self._apply_brightness(self.sld_bright.value())
        self._apply_boost(self.sld_boost.value())
        self._apply_master(self.sld_master.value())
        self._apply_gate(self.sld_gate.value())

    def apply_reverb_preset(self, preset: str) -> None:
        params = get_reverb_preset(preset)
        room = params.get('room')
        if room is not None:
            self._set_slider(self.sld_rev_room, int(room), self._apply_reverb_room)
        damp = params.get('damp')
        if damp is not None:
            self._set_slider(self.sld_rev_damp, int(damp), self._apply_reverb_damp)
        level = params.get('level')
        if level is not None:
            self._set_level_slider(int(level))

    def _set_slider(self, slider: QSlider, value: int, callback: Callable[[int], None]) -> None:
        bounded = int(max(slider.minimum(), min(slider.maximum(), value)))
        if slider.value() == bounded:
            callback(bounded)
            return
        slider.blockSignals(True)
        slider.setValue(bounded)
        slider.blockSignals(False)
        callback(bounded)

    def _set_level_slider(self, value: int) -> None:
        self._set_slider(self.sld_rev_level, value, self._apply_reverb_level)

    def _toggle_reverb(self, active: bool) -> None:
        if active:
            target = self._last_reverb_level_value if self._last_reverb_level_value > 0 else max(1, self.sld_rev_level.maximum() // 2)
            self._set_level_slider(target)
        else:
            self._set_level_slider(0)

    def _apply_reverb_level(self, value: int) -> None:
        level = max(0.0, min(1.0, value / 100.0))
        self.audio.set_reverb(level=level)
        send = min(1.0, max(0.0, value / 60.0))
        self.audio.set_reverb_send(send)
        is_active = value > 0
        self.audio.set_reverb_active(is_active)
        if is_active:
            self._last_reverb_level_value = value
        self._sync_reverb_toggle(is_active)
        self.lbl_rev_level.setText(self._format_reverb_level())

    def _apply_reverb_room(self, value: int) -> None:
        room = max(0.0, min(1.0, value / 100.0))
        self.audio.set_reverb(roomsize=room)
        self.lbl_rev_room.setText(f"Reverb room: {self.audio.reverb_roomsize:.2f}")

    def _apply_reverb_damp(self, value: int) -> None:
        damp = max(0.0, min(1.0, value / 100.0))
        self.audio.set_reverb(damping=damp)
        self.lbl_rev_damp.setText(f"Reverb damp: {self.audio.reverb_damping:.2f}")

    def _apply_brightness(self, value: int) -> None:
        try:
            for ch in range(16):
                self.audio.fs.cc(ch, 74, int(value))
        except Exception:
            pass
        self.lbl_bright.setText(f"Brillo (CC74): {int(value)}")

    def _apply_boost(self, value: int) -> None:
        bounded = max(self.sld_boost.minimum(), min(self.sld_boost.maximum(), int(value)))
        try:
            self.audio.velocity_gain = float(bounded)
        except Exception:
            pass
        self.lbl_boost.setText(f"Boost (vel x): {getattr(self.audio, 'velocity_gain', bounded):.0f}")

    def _apply_master(self, value: int) -> None:
        db = value / 10.0
        self.audio.set_master_gain_db(db)
        self.lbl_master.setText(f"Master boost (dB): {self.audio.master_db:+.1f}")

    def _apply_gate(self, value: int) -> None:
        self.min_velocity = max(0, int(value))
        self.lbl_gate.setText(f"Filtro golpes leves: {self.min_velocity}")

    def _sync_reverb_toggle(self, active: bool) -> None:
        self.chk_rev_on.blockSignals(True)
        self.chk_rev_on.setChecked(active)
        self.chk_rev_on.blockSignals(False)

    def _format_reverb_level(self) -> str:
        return f"Reverb level: {self.audio.reverb_level:.2f} (send: {self.audio.reverb_send:.2f})"

    def _current_sf_text(self) -> str:
        path = self.config.get('last_sf2')
        name = Path(path).name if path else 'Sin seleccionar'
        return f'SoundFont activo: {name}'

    def _select_sf2(self) -> None:
        start = Path(self.config.get('last_sf2', '.'))
        directory = start.parent if start.is_file() else Path('.')
        chosen, _ = QFileDialog.getOpenFileName(self, 'Seleccionar SoundFont', str(directory), 'SoundFont (*.sf2)')
        if not chosen:
            return
        path = Path(chosen)
        try:
            self.audio.load_sf2_live(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Error', f'No se pudo cargar el SoundFont\n{exc}')
            return
        self.config['last_sf2'] = str(path)
        save_config(self.config)
        self.lbl_sf.setText(self._current_sf_text())

