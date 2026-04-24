"""Minimal timbal lab window for capture-oriented experiments."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from mido import Message
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.runtime import build_application, build_audio_engine
from app.timbal_lab.eval.model_bench import benchmark_session
from app.timbal_lab.logging.session_recorder import SessionRecorder
from app.timbal_lab.profiles.patch_profile import PatchProfileManager
from app.timbal_lab.render.renderer_adapter import RendererAdapter
from app.timbal_lab.sources.analog_raw_source import AnalogRawSource, SourceAvailability
from app.timbal_lab.sources.replay_source import ReplaySource
from app.timbal_lab.ui.hit_inspector import HitInspector
from app.ui.testing_shell import MetricCard, SectionCard, StatusChip, build_testing_qss


class SyncFlash(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setStyleSheet("background: white;")


class TimbalLabWindow(QMainWindow):
    def __init__(self, engine=None, *, audio_status: str = "Audio no inicializado") -> None:
        super().__init__()
        self.engine = engine
        self.audio_status = audio_status
        self.recorder = SessionRecorder()
        self.profile_manager = PatchProfileManager()
        self.renderer = RendererAdapter(engine)
        self.analog_source = AnalogRawSource(self)
        self.replay_source = ReplaySource(self)
        self.source = self.analog_source
        self._current_source_name = "analog_raw"
        self.sample_count = 0
        self.hit_count = 0
        self.mute_sw_enabled = False
        self.last_session_dir: Path | None = None
        self.last_analysis_dir: Path | None = None
        self.last_report: dict[str, object] | None = None

        for src in (self.analog_source, self.replay_source):
            src.availability_changed.connect(self._on_availability_changed)
            src.status_changed.connect(self._on_source_status)
            src.running_changed.connect(self._on_running_changed)
            src.samples_received.connect(self._on_samples)
            src.hit_detected.connect(self._on_hit)

        self.setWindowTitle("Timbal Lab")
        self._build_ui()
        self._set_current_source("analog_raw")
        self._append_log("Laboratorio listo. Fuente analogica en espera.")

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = QLabel("Timbal Lab")
        title.setObjectName("TestingHeadline")
        subtitle = QLabel(
            "Laboratorio de captura, replay y benchmark. Mantiene el pipeline actual, pero ordenado para que sea claro que hacer primero."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("TestingSubheadline")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        self.workflow_label = QLabel(
            "Flujo sugerido: 1. Elegi fuente. 2. Inicia fuente. 3. Graba sesion. 4. Corre analisis. 5. Reproduce modelos."
        )
        self.workflow_label.setObjectName("TestingHint")
        self.workflow_label.setWordWrap(True)
        title_col.addWidget(self.workflow_label)
        title_row.addLayout(title_col, 1)

        status_col = QVBoxLayout()
        status_col.setSpacing(8)
        self.source_chip = StatusChip("Fuente en espera")
        self.source_hint_label = QLabel("La fuente analogica queda seleccionada por defecto.")
        self.source_hint_label.setObjectName("TestingHint")
        self.source_hint_label.setWordWrap(True)
        status_col.addWidget(self.source_chip, 0, Qt.AlignRight)
        status_col.addWidget(self.source_hint_label)
        title_row.addLayout(status_col, 0)
        root.addLayout(title_row)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)
        self.availability_metric = MetricCard("Fuente")
        self.state_metric = MetricCard("Estado")
        self.samples_metric = MetricCard("Muestras")
        self.hits_metric = MetricCard("Hits")
        self.audio_metric = MetricCard("Audio")
        self.session_metric = MetricCard("Sesion")
        self.analysis_metric = MetricCard("Analisis")
        self.profile_metric = MetricCard("Perfil")
        for idx, card in enumerate(
            [
                self.availability_metric,
                self.state_metric,
                self.samples_metric,
                self.hits_metric,
                self.audio_metric,
                self.session_metric,
                self.analysis_metric,
                self.profile_metric,
            ]
        ):
            metrics.addWidget(card, idx // 4, idx % 4)
        root.addLayout(metrics)

        body = QHBoxLayout()
        body.setSpacing(16)

        controls_col = QVBoxLayout()
        controls_col.setSpacing(14)

        source_card = SectionCard(
            "Fuente",
            "Usa analog raw para captura en vivo o replay para abrir una sesion ya grabada.",
        )
        self.patch_edit = QLineEdit("patch_A")
        self.patch_edit.editingFinished.connect(self._on_patch_changed)
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notas de la sesion, afinacion, observaciones")
        self.source_combo = QComboBox()
        self.source_combo.addItem("Analog Raw", "analog_raw")
        self.source_combo.addItem("Replay", "replay")
        self.source_combo.currentIndexChanged.connect(self._on_source_combo_changed)
        self.refresh_button = QPushButton("Refrescar fuente")
        self.refresh_button.clicked.connect(self._refresh_active_source)
        self.load_replay_button = QPushButton("Cargar replay")
        self.load_replay_button.setObjectName("SecondaryAction")
        self.load_replay_button.clicked.connect(self._load_replay_session)
        self.start_source_button = QPushButton("Iniciar fuente")
        self.start_source_button.clicked.connect(self._start_source)
        self.stop_source_button = QPushButton("Detener fuente")
        self.stop_source_button.setObjectName("SecondaryAction")
        self.stop_source_button.clicked.connect(self._stop_source)
        source_grid = QGridLayout()
        source_grid.setHorizontalSpacing(10)
        source_grid.setVerticalSpacing(8)
        source_grid.addWidget(QLabel("Fuente"), 0, 0)
        source_grid.addWidget(self.source_combo, 0, 1)
        source_grid.addWidget(self.refresh_button, 1, 0, 1, 2)
        source_grid.addWidget(self.load_replay_button, 2, 0, 1, 2)
        source_grid.addWidget(self.start_source_button, 3, 0)
        source_grid.addWidget(self.stop_source_button, 3, 1)
        source_card.body_layout.addLayout(source_grid)
        controls_col.addWidget(source_card)

        session_card = SectionCard(
            "Sesion",
            "Define patch y notas, activa mute software si queres y marca SYNC durante la grabacion.",
        )
        self.start_session_button = QPushButton("Iniciar sesion")
        self.start_session_button.clicked.connect(self._start_session)
        self.stop_session_button = QPushButton("Cerrar sesion")
        self.stop_session_button.setObjectName("SecondaryAction")
        self.stop_session_button.clicked.connect(self._stop_session)
        self.sync_button = QPushButton("SYNC")
        self.sync_button.setObjectName("SecondaryAction")
        self.sync_button.clicked.connect(self._run_sync)
        self.mute_toggle_button = QPushButton("Mute SW OFF")
        self.mute_toggle_button.setCheckable(True)
        self.mute_toggle_button.clicked.connect(self._toggle_mute_sw)
        session_grid = QGridLayout()
        session_grid.setHorizontalSpacing(10)
        session_grid.setVerticalSpacing(8)
        session_grid.addWidget(QLabel("Patch ID"), 0, 0)
        session_grid.addWidget(self.patch_edit, 0, 1)
        session_grid.addWidget(QLabel("Notas"), 1, 0)
        session_grid.addWidget(self.notes_edit, 1, 1)
        session_grid.addWidget(self.start_session_button, 2, 0)
        session_grid.addWidget(self.stop_session_button, 2, 1)
        session_grid.addWidget(self.sync_button, 3, 0)
        session_grid.addWidget(self.mute_toggle_button, 3, 1)
        session_card.body_layout.addLayout(session_grid)
        self.session_hint_label = QLabel("Sin sesion activa.")
        self.session_hint_label.setObjectName("TestingHint")
        self.session_hint_label.setWordWrap(True)
        session_card.body_layout.addWidget(self.session_hint_label)
        controls_col.addWidget(session_card)

        analysis_card = SectionCard(
            "Analisis y playback",
            "Corre el benchmark y luego compara la reproduccion de legacy_map contra state_map_v1.",
        )
        self.analyze_button = QPushButton("Analizar sesion")
        self.analyze_button.clicked.connect(self._analyze_session)
        self.play_legacy_button = QPushButton("Play Legacy")
        self.play_legacy_button.setObjectName("SecondaryAction")
        self.play_legacy_button.clicked.connect(
            lambda: self._play_analysis_model("legacy_map")
        )
        self.play_state_button = QPushButton("Play State")
        self.play_state_button.setObjectName("SecondaryAction")
        self.play_state_button.clicked.connect(
            lambda: self._play_analysis_model("state_map_v1")
        )
        analysis_grid = QGridLayout()
        analysis_grid.setHorizontalSpacing(10)
        analysis_grid.setVerticalSpacing(8)
        analysis_grid.addWidget(self.analyze_button, 0, 0, 1, 2)
        analysis_grid.addWidget(self.play_legacy_button, 1, 0)
        analysis_grid.addWidget(self.play_state_button, 1, 1)
        analysis_card.body_layout.addLayout(analysis_grid)
        self.analysis_hint_label = QLabel("Todavia no hay analisis cargado.")
        self.analysis_hint_label.setObjectName("TestingHint")
        self.analysis_hint_label.setWordWrap(True)
        analysis_card.body_layout.addWidget(self.analysis_hint_label)
        controls_col.addWidget(analysis_card)
        controls_col.addStretch(1)
        body.addLayout(controls_col, 0)

        content_col = QVBoxLayout()
        content_col.setSpacing(12)
        self.last_hit_label = QLabel("Sin hits todavia.")
        self.last_hit_label.setObjectName("LabLastHit")
        content_col.addWidget(self.last_hit_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LabLog")
        self.log_view.setMinimumHeight(280)
        self.hit_inspector = HitInspector()
        self.content_tabs = QTabWidget()
        self.content_tabs.addTab(self.log_view, "Log")
        self.content_tabs.addTab(self.hit_inspector, "Inspector")
        content_col.addWidget(self.content_tabs, 1)
        body.addLayout(content_col, 1)
        root.addLayout(body, 1)

        self.audio_metric.set_value(self.audio_status)
        self.state_metric.set_value("idle")
        self.samples_metric.set_value("0")
        self.hits_metric.set_value("0")
        self.session_metric.set_value("sin grabar")
        self.analysis_metric.set_value("sin correr")
        self.profile_metric.set_value("sin perfil")
        self.stop_source_button.setEnabled(False)
        self.stop_session_button.setEnabled(False)
        self.load_replay_button.setEnabled(False)
        self.play_legacy_button.setEnabled(self.renderer.is_available())
        self.play_state_button.setEnabled(self.renderer.is_available())

        self.setStyleSheet(
            self.styleSheet()
            + build_testing_qss(
                """
                QLabel#LabLastHit {
                    color: #e5e7eb;
                    font-size: 15px;
                    font-weight: 700;
                }
                QPushButton:checked {
                    background-color: #7f1d1d;
                    color: #fee2e2;
                }
                QPlainTextEdit#LabLog {
                    background: #020617;
                    color: #cbd5e1;
                    border: 1px solid #243244;
                    border-radius: 16px;
                    padding: 8px;
                }
                """
            )
        )

    def closeEvent(self, event) -> None:
        self.renderer.stop()
        self.analog_source.close()
        self.replay_source.close()
        self._stop_session()
        event.accept()

    def _start_source(self) -> None:
        if self.source.start():
            self._append_log(f"Fuente iniciada: {self.source.source_name}")
            self.source_hint_label.setText(f"Fuente corriendo: {self.source.source_name}")
        else:
            self._append_log(f"No se pudo iniciar la fuente {self.source.source_name}.")
            self.source_hint_label.setText(
                f"No se pudo iniciar la fuente {self.source.source_name}."
            )

    def _stop_source(self) -> None:
        self.source.close()
        self._append_log(f"Fuente detenida: {self.source.source_name}")
        self.source_hint_label.setText(f"Fuente detenida: {self.source.source_name}")

    def _start_session(self) -> None:
        if not self.source.is_running():
            QMessageBox.information(
                self,
                "Sesion",
                "Primero inicia la fuente analogica.",
            )
            return
        if self.recorder.is_active:
            QMessageBox.information(self, "Sesion", "Ya hay una sesion en curso.")
            return

        patch_id = self.patch_edit.text().strip() or "unlabeled"
        notes = self.notes_edit.text().strip()
        availability = self.source.refresh_availability()
        source_detail = availability.port_name or availability.detail
        profile_path = self.profile_manager.ensure_profile(
            patch_id=patch_id,
            notes=notes,
            source_kind=self.source.source_name,
        )
        profile = self.profile_manager.load_profile(patch_id) or {}
        detector_config = self._apply_patch_profile(patch_id, profile)
        self.profile_metric.set_value(profile_path.name)
        session_dir = self.recorder.start(
            patch_id=patch_id,
            notes=notes,
            source_kind=self.source.source_name,
            source_detail=source_detail,
        )
        self.recorder.update_manifest_fields(
            patch_profile_path=str(profile_path),
            mute_sw_enabled=self.mute_sw_enabled,
            detector_config=detector_config,
        )
        self.recorder.log_event(
            "PATCH_PROFILE",
            {
                "patch_id": patch_id,
                "profile_path": str(profile_path),
                "detector_config": detector_config,
            },
        )
        self.session_metric.set_value(session_dir.name)
        self.analysis_metric.set_value("pendiente")
        self.last_analysis_dir = None
        self.last_report = None
        self.hit_inspector.clear()
        self.start_session_button.setEnabled(False)
        self.stop_session_button.setEnabled(True)
        self._append_log(f"Sesion iniciada en {session_dir}")
        self.session_hint_label.setText(f"Sesion activa: {session_dir.name}")

    def _stop_session(self) -> None:
        session_dir = self.recorder.close()
        if session_dir is None:
            self.start_session_button.setEnabled(self.source.is_running())
            self.stop_session_button.setEnabled(False)
            if self.session_metric.value_label.text() == "--":
                self.session_metric.set_value("sin grabar")
            if not self.recorder.is_active:
                self.session_hint_label.setText("Sin sesion activa.")
            return
        self.session_metric.set_value(session_dir.name)
        self.last_session_dir = session_dir
        self.start_session_button.setEnabled(self.source.is_running())
        self.stop_session_button.setEnabled(False)
        self._append_log(f"Sesion cerrada: {session_dir}")
        self.session_hint_label.setText(f"Ultima sesion cerrada: {session_dir.name}")

    def _apply_patch_profile(
        self,
        patch_id: str,
        profile: dict[str, object] | None = None,
    ) -> dict[str, int] | None:
        loaded_profile = profile if profile is not None else (self.profile_manager.load_profile(patch_id) or {})
        self.profile_metric.set_value(self.profile_manager.profile_path(patch_id).name)
        if self.source is not self.analog_source:
            return None
        thresholds = loaded_profile.get("thresholds", {}) if isinstance(loaded_profile, dict) else {}
        if not isinstance(thresholds, dict):
            thresholds = {}
        detector_config = self.analog_source.configure_detector(
            threshold=_safe_int(thresholds.get("hit_threshold")),
            delta=_safe_int(thresholds.get("delta_threshold")),
            refractory_ms=_safe_int(thresholds.get("refractory_ms")),
        )
        self._append_log(
            "Perfil aplicado"
            f" {patch_id}: thr={detector_config['hit_threshold']}"
            f" delta={detector_config['delta_threshold']}"
            f" refr={detector_config['refractory_ms']}ms"
        )
        return detector_config

    def _on_availability_changed(self, info: SourceAvailability) -> None:
        sender = self.sender()
        if sender is not self.source:
            return
        self.availability_metric.set_value(
            info.port_name or ("lista" if info.available else "sin fuente")
        )
        if info.available:
            self.source_chip.set_status("Fuente lista", tone="ok")
        else:
            self.source_chip.set_status("Sin fuente", tone="warn")
        self.source_hint_label.setText(info.detail)
        if not self.source.is_running():
            self.start_source_button.setEnabled(info.available)

    def _on_running_changed(self, running: bool) -> None:
        sender = self.sender()
        if sender is not self.source:
            return
        self.state_metric.set_value("capturando" if running else "idle")
        self.source_chip.set_status(
            "Capturando" if running else "Fuente lista",
            tone="ok" if running else ("ok" if self.start_source_button.isEnabled() else "warn"),
        )
        self.start_source_button.setEnabled(not running)
        self.stop_source_button.setEnabled(running)
        if not running and self.recorder.is_active:
            self._stop_session()
        self.start_session_button.setEnabled(running and not self.recorder.is_active)

    def _on_samples(self, samples: list[object]) -> None:
        sender = self.sender()
        if sender is not self.source:
            return
        self.sample_count += len(samples)
        self.samples_metric.set_value(str(self.sample_count))
        if self.recorder.is_active:
            self.recorder.log_samples(samples)

    def _on_hit(self, hit) -> None:
        sender = self.sender()
        if sender is not self.source:
            return
        self.hit_count += 1
        self.hits_metric.set_value(str(self.hit_count))
        lag_text = "--" if hit.lag_ms is None else f"{hit.lag_ms:.1f} ms"
        self.last_hit_label.setText(
            f"Ultimo hit: ch={hit.channel} value={hit.value} lag~{lag_text}"
        )
        if self.recorder.is_active:
            self.recorder.log_hit(hit)

    def _append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def _on_patch_changed(self) -> None:
        patch_id = self.patch_edit.text().strip() or "patch_A"
        profile = self.profile_manager.load_profile(patch_id)
        if profile is None:
            self.profile_metric.set_value("sin perfil")
            return
        self._apply_patch_profile(patch_id, profile)

    def _on_source_status(self, text: str) -> None:
        sender = self.sender()
        if sender is not self.source:
            return
        self._append_log(text)
        self.source_hint_label.setText(text.replace("INFO: ", "").replace("WARN: ", ""))

    def _on_source_combo_changed(self) -> None:
        if self.recorder.is_active:
            QMessageBox.information(
                self,
                "Fuente",
                "Cierra la sesion actual antes de cambiar de fuente.",
            )
            self.source_combo.blockSignals(True)
            self.source_combo.setCurrentIndex(
                self.source_combo.findData(self._current_source_name)
            )
            self.source_combo.blockSignals(False)
            return
        source_name = self.source_combo.currentData()
        self._set_current_source(str(source_name))

    def _set_current_source(self, source_name: str) -> None:
        self.analog_source.close()
        self.replay_source.close()
        self.source = self.analog_source if source_name == "analog_raw" else self.replay_source
        self._current_source_name = source_name
        self.load_replay_button.setEnabled(self.source is self.replay_source)
        self.sample_count = 0
        self.hit_count = 0
        self.samples_metric.set_value("0")
        self.hits_metric.set_value("0")
        self.last_hit_label.setText("Sin hits todavia.")
        self.state_metric.set_value("idle")
        self.start_session_button.setEnabled(False)
        self.stop_session_button.setEnabled(False)
        self.last_analysis_dir = None
        self.last_report = None
        self.hit_inspector.clear()
        self.source.refresh_availability()
        self._on_patch_changed()
        self._append_log(f"Fuente seleccionada: {self.source.source_name}")
        self.session_hint_label.setText("Sin sesion activa.")
        self.analysis_hint_label.setText("Todavia no hay analisis cargado.")

    def _refresh_active_source(self) -> None:
        self.source.refresh_availability()

    def _load_replay_session(self) -> None:
        session_dir = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar sesion de replay",
            str(Path("data") / "sessions"),
        )
        if not session_dir:
            return
        session_path = Path(session_dir)
        ok = self.replay_source.load_session(session_path)
        if ok and self.source is self.replay_source:
            self.last_session_dir = session_path
            self.replay_source.refresh_availability()
            self.session_metric.set_value(session_path.name)
            self.session_hint_label.setText(f"Replay cargado: {session_path.name}")
            try:
                manifest = json.loads((session_path / "manifest.json").read_text(encoding="utf-8"))
                patch_id = str(manifest.get("patch_id") or "").strip()
                if patch_id:
                    self.patch_edit.setText(patch_id)
                    self._on_patch_changed()
            except Exception:
                pass
            self._load_existing_analysis(session_path)

    def _run_sync(self) -> None:
        if not self.recorder.is_active:
            QMessageBox.information(self, "SYNC", "Inicia una sesion antes de marcar SYNC.")
            return
        self._flash_sync()
        self._play_sync_click()
        self.recorder.log_event(
            "SYNC_HOST",
            {
                "source_kind": self.source.source_name,
                "mute_sw_enabled": self.mute_sw_enabled,
            },
        )
        self._append_log("SYNC_HOST registrado.")
        self.session_hint_label.setText("SYNC_HOST registrado en la sesion actual.")

    def _flash_sync(self) -> None:
        flash = SyncFlash()
        screen = QApplication.primaryScreen()
        if screen is not None:
            flash.setGeometry(screen.geometry())
        flash.showFullScreen()
        QTimer.singleShot(150, flash.close)

    def _play_sync_click(self) -> None:
        if self.engine is None:
            QApplication.beep()
            return
        try:
            self.engine.disparar(Message("note_on", note=96, velocity=120, channel=0))
            QTimer.singleShot(
                90,
                lambda: self.engine.disparar(
                    Message("note_off", note=96, velocity=0, channel=0)
                ),
            )
        except Exception:
            QApplication.beep()

    def _toggle_mute_sw(self, checked: bool) -> None:
        self.mute_sw_enabled = bool(checked)
        self.mute_toggle_button.setText("Mute SW ON" if checked else "Mute SW OFF")
        self._append_log(f"Mute SW {'ON' if checked else 'OFF'}")
        self.session_hint_label.setText(
            f"Mute software {'activo' if checked else 'apagado'}."
        )
        if self.recorder.is_active:
            self.recorder.update_manifest_fields(mute_sw_enabled=self.mute_sw_enabled)
            self.recorder.log_event("MUTE_SW", {"enabled": self.mute_sw_enabled})

    def _analyze_session(self) -> None:
        if self.recorder.is_active:
            QMessageBox.information(
                self,
                "Analisis",
                "Cierra la sesion actual antes de correr el analisis offline.",
            )
            return
        if self.last_session_dir is None:
            QMessageBox.information(
                self,
                "Analisis",
                "No hay una sesion disponible para analizar.",
            )
            return
        try:
            report, analysis_dir = benchmark_session(self.last_session_dir)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Analisis",
                f"No se pudo analizar la sesion.\n{exc}",
            )
            self._append_log(f"WARN: analisis fallido: {exc}")
            return

        winner = str(report.get("winner", "unknown"))
        self.last_report = report
        self.analysis_metric.set_value(winner)
        self.last_analysis_dir = analysis_dir
        self._load_existing_analysis(self.last_session_dir)
        self._append_log(f"Analisis listo en {analysis_dir}")
        self.analysis_hint_label.setText(f"Analisis listo. Ganador: {winner}")
        models = report.get("models", {})
        if isinstance(models, dict):
            for model_name, metrics in models.items():
                if not isinstance(metrics, dict):
                    continue
                score = metrics.get("overall_score")
                monotonicity = metrics.get("monotonicity_velocity")
                continuity = metrics.get("continuity_brightness")
                self._append_log(
                    f"{model_name}: score={score} mono={monotonicity} cont={continuity}"
                )
        calibration_summary_path = analysis_dir / "calibration_summary.json"
        if calibration_summary_path.exists():
            try:
                calibration = json.loads(calibration_summary_path.read_text(encoding="utf-8"))
                thresholds = calibration.get("thresholds", {})
                temporal = calibration.get("temporal", {})
                self._append_log(
                    "Calibracion:"
                    f" thr={thresholds.get('hit_threshold')}"
                    f" delta={thresholds.get('delta_threshold')}"
                    f" refr={thresholds.get('refractory_ms')}ms"
                    f" tauE={temporal.get('tau_energy_ms')}ms"
                )
            except Exception:
                pass
        self._on_patch_changed()
        self.content_tabs.setCurrentWidget(self.hit_inspector)

    def _play_analysis_model(self, model_name: str) -> None:
        if self.last_session_dir is None:
            QMessageBox.information(
                self,
                "Playback",
                "No hay una sesion cargada o grabada para reproducir.",
            )
            return
        if self.last_analysis_dir is None:
            QMessageBox.information(
                self,
                "Playback",
                "Corre el analisis primero para generar las predicciones.",
            )
            return
        ok = self.renderer.play_session_analysis(self.last_session_dir, model_name)
        if not ok:
            QMessageBox.warning(
                self,
                "Playback",
                f"No se pudo reproducir {model_name}. Verifica que exista el analisis y que el audio este disponible.",
            )
            return
        self._append_log(f"Playback iniciado: {model_name}")
        self.analysis_hint_label.setText(f"Playback iniciado con {model_name}.")

    def _load_existing_analysis(self, session_dir: Path) -> None:
        analysis_dir = session_dir / "analysis"
        report_path = analysis_dir / "benchmark_report.json"
        if not analysis_dir.exists() or not report_path.exists():
            self.last_analysis_dir = None
            self.last_report = None
            self.analysis_metric.set_value("pendiente")
            self.hit_inspector.clear()
            self.analysis_hint_label.setText("Todavia no hay analisis cargado.")
            return
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._append_log(f"WARN: no se pudo leer benchmark_report.json: {exc}")
            self.last_analysis_dir = None
            self.last_report = None
            self.analysis_metric.set_value("pendiente")
            self.hit_inspector.clear()
            self.analysis_hint_label.setText("El analisis existe pero no se pudo leer.")
            return
        self.last_analysis_dir = analysis_dir
        self.last_report = report if isinstance(report, dict) else {}
        self.analysis_metric.set_value(str(self.last_report.get("winner", "listo")))
        self.hit_inspector.load_analysis(session_dir, analysis_dir)
        self.analysis_hint_label.setText(
            f"Analisis cargado para {session_dir.name}. Winner: {self.last_report.get('winner', 'listo')}"
        )


def _safe_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except Exception:
        return None


def run_timbal_lab_window() -> None:
    app = build_application()

    engine = None
    audio_status = "Audio no disponible"
    try:
        engine, _ = build_audio_engine(None, allow_prompt=False)
        audio_status = "Audio listo"
    except Exception as exc:
        print(f"WARN: Timbal Lab sin audio: {exc}")
        audio_status = "Audio no disponible"

    window = TimbalLabWindow(engine, audio_status=audio_status)
    window.resize(1480, 860)
    window.show()
    sys.exit(app.exec_())
