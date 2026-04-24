import sys
import subprocess
from pathlib import Path

from mido import Message
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QAction,
    QInputDialog,
)

from app.io.timbal_input import (
    TimbalHit,
    TimbalCalibrationState,
    TimbalInputRouter,
    TimbalMute,
    TimbalPadState,
)
from app.runtime import build_application, build_audio_engine
from app.state.settings import load_config, save_config
from app.ui.calibration_dialog import CalibrationDialog
from app.ui.pages.pads import PadsPage


def run_new_ui():
    app = build_application()
    config = load_config()
    try:
        engine, resolved = build_audio_engine(config, allow_prompt=True)
    except Exception as exc:
        QMessageBox.critical(None, "Error", f"No se pudo iniciar el motor de audio\n{exc}")
        return

    config["last_sf2"] = str(resolved)
    try:
        bank = int(config.get("sf2_bank", 0))
    except (TypeError, ValueError):
        bank = 0
    try:
        preset = int(config.get("sf2_preset", 0))
    except (TypeError, ValueError):
        preset = 0
    try:
        engine.load_sf2_live(resolved, bank=bank, preset=preset)
    except Exception as exc:
        print(f"WARN: no se pudo re-aplicar bank/preset al iniciar: {exc}")
    save_config(config)

    win = MainWindow(engine, config)
    win.resize(1400, 820)
    win.show()
    sys.exit(app.exec_())


class MainWindow(QMainWindow):
    def __init__(self, engine, config):
        super().__init__()
        self.engine = engine
        self.config = config
        self.setWindowTitle("Timbal Digital - Nueva UI (beta segura)")

        self.pads_page = PadsPage(engine, config)
        self.setCentralWidget(self.pads_page)

        self.dino_process = None
        self.calibration_dialog: CalibrationDialog | None = None
        self.input_router = TimbalInputRouter(self, prefer_midi_hits=False)
        self.input_router.hit_received.connect(self._on_router_hit)
        self.input_router.mute_received.connect(self._on_router_mute)
        self.input_router.pad_state_received.connect(self._on_router_pad_state)
        self.input_router.calibration_state_received.connect(
            self._on_router_calibration_state
        )
        self.input_router.midi_message_received.connect(self._on_router_midi_message)
        self.input_router.status_changed.connect(print)
        self.input_router.start()

        self._build_menu()
        self.statusBar().hide()
        QTimer.singleShot(1200, self._push_saved_calibration)

    def closeEvent(self, event):
        self.input_router.close()
        if self.dino_process:
            self.dino_process.kill()
        event.accept()

    def _build_menu(self) -> None:
        menu_config = self.menuBar().addMenu("Configuracion")
        act_change_sf2 = QAction("Cambiar SoundFont...", self)
        act_change_sf2.triggered.connect(self._change_soundfont)
        menu_config.addAction(act_change_sf2)
        act_program_sf2 = QAction("Preset/Bank SoundFont...", self)
        act_program_sf2.triggered.connect(self._change_soundfont_program)
        menu_config.addAction(act_program_sf2)
        act_calibration = QAction("Calibracion en vivo...", self)
        act_calibration.triggered.connect(self._open_calibration_dialog)
        menu_config.addAction(act_calibration)

        menu_games = self.menuBar().addMenu("Juegos")
        act_dino = QAction("Iniciar DINO RITMO", self)
        act_dino.triggered.connect(self._launch_dino_ritmo)
        menu_games.addAction(act_dino)

    def _build_child_command(self, mode_flag: str) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, mode_flag]
        launcher = str(Path(sys.argv[0]).resolve())
        return [sys.executable, launcher, mode_flag]

    def _launch_dino_ritmo(self):
        if self.dino_process and self.dino_process.poll() is None:
            QMessageBox.information(self, "DINO RITMO", "El juego ya esta abierto.")
            return
        try:
            self.dino_process = subprocess.Popen(
                self._build_child_command("--run-dino"),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar DINO RITMO:\n{exc}")

    def _change_soundfont(self) -> None:
        start = Path(self.config.get("last_sf2", "."))
        directory = start.parent if start.is_file() else Path(".")
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar SoundFont",
            str(directory),
            "SoundFont (*.sf2)",
        )
        if not chosen:
            return
        path = Path(chosen)
        try:
            self.engine.load_sf2_live(
                path,
                bank=self._current_sf2_bank(),
                preset=self._current_sf2_preset(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo cambiar el SoundFont\n{exc}")
            return
        self.config["last_sf2"] = str(path)
        save_config(self.config)
        QMessageBox.information(self, "SoundFont", f"SoundFont cargado: {path.name}")

    def _current_sf2_bank(self) -> int:
        try:
            return int(self.config.get("sf2_bank", 0))
        except (TypeError, ValueError):
            return 0

    def _current_sf2_preset(self) -> int:
        try:
            return int(self.config.get("sf2_preset", 0))
        except (TypeError, ValueError):
            return 0

    def _change_soundfont_program(self) -> None:
        bank, ok = QInputDialog.getInt(
            self,
            "Bank SoundFont",
            "Bank MIDI (0-127):",
            self._current_sf2_bank(),
            0,
            127,
            1,
        )
        if not ok:
            return

        preset, ok = QInputDialog.getInt(
            self,
            "Preset SoundFont",
            "Preset MIDI (0-127). Timpani GM suele ser 47:",
            self._current_sf2_preset(),
            0,
            127,
            1,
        )
        if not ok:
            return

        current_sf2 = self.config.get("last_sf2")
        if not current_sf2:
            QMessageBox.information(
                self,
                "Preset SoundFont",
                "Primero carga un SoundFont.",
            )
            return

        path = Path(current_sf2)
        try:
            self.engine.load_sf2_live(path, bank=bank, preset=preset)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo aplicar bank/preset al SoundFont\n{exc}",
            )
            return

        self.config["sf2_bank"] = int(bank)
        self.config["sf2_preset"] = int(preset)
        save_config(self.config)
        QMessageBox.information(
            self,
            "Preset SoundFont",
            f"Bank {bank}, preset {preset} aplicados a {path.name}",
        )

    def _forward_hit_to_dino(self) -> None:
        if self.dino_process and self.dino_process.poll() is None:
            try:
                self.dino_process.stdin.write("HIT\n")
                self.dino_process.stdin.flush()
            except Exception as exc:
                print(f"ERROR: No se pudo comunicar con DINO_RITMO: {exc}")

    def _on_router_hit(self, hit: TimbalHit) -> None:
        print(
            f"DEBUG: {hit.source} HIT pad={hit.pad_idx} "
            f"note={hit.note} vel={hit.velocity}"
        )
        resolved_pad_idx = hit.pad_idx
        if resolved_pad_idx is None and hit.note is not None:
            resolved_pad_idx = self.pads_page.find_pad_by_midi(hit.note)

        handled = False
        try:
            handled = self.pads_page.handle_external_hit(
                note=hit.note,
                velocity=hit.velocity,
                pad_idx=resolved_pad_idx,
            )
        except Exception as exc:
            print(f"WARN: error en hit externo -> pads: {exc}")

        if handled:
            self._forward_hit_to_dino()
            return

        if resolved_pad_idx is None and hit.note is not None:
            try:
                self.engine.disparar(
                    Message(
                        "note_on",
                        note=int(hit.note),
                        velocity=int(hit.velocity),
                        channel=0,
                    )
                )
                print("DEBUG: note_on externo enviado directo al engine.")
                self._forward_hit_to_dino()
            except Exception as exc:
                print(f"WARN: error disparando engine: {exc}")

    def _on_router_mute(self, mute: TimbalMute) -> None:
        print(
            f"DEBUG: {mute.source} MUTE pad={mute.pad_idx} "
            f"state={mute.state} note={mute.note}"
        )
        try:
            self.pads_page.handle_mute(
                pad_idx=mute.pad_idx,
                note=mute.note,
                state=mute.state,
            )
        except Exception as exc:
            print(f"WARN: procesando MUTE externo: {exc}")

    def _on_router_pad_state(self, state: TimbalPadState) -> None:
        try:
            self.pads_page.handle_pad_state(
                pad_idx=state.pad_idx,
                connected=state.connected,
                noise=state.noise,
                value=state.value,
                peak=state.peak,
            )
        except Exception as exc:
            print(f"WARN: procesando PADSTATE externo: {exc}")
        if self.calibration_dialog is not None:
            self.calibration_dialog.update_pad_state(
                pad_idx=state.pad_idx,
                connected=state.connected,
                noise=state.noise,
                value=state.value,
                peak=state.peak,
            )

    def _on_router_calibration_state(self, state: TimbalCalibrationState) -> None:
        payload = {
            "min_hit": state.min_hit,
            "quiet": state.quiet,
            "presence_noise": state.presence_noise,
            "refractory": state.refractory,
            "keep_connected": state.keep_connected,
        }
        clean = {k: int(v) for k, v in payload.items() if v is not None}
        if clean:
            self.config["firmware_calibration"] = clean
            save_config(self.config)
        if self.calibration_dialog is not None:
            self.calibration_dialog.update_calibration_state(state)

    def _on_router_midi_message(self, message) -> None:
        typ = getattr(message, "type", "")
        velocity = getattr(message, "velocity", 0)
        if typ == "control_change" or typ == "note_off" or (typ == "note_on" and velocity == 0):
            try:
                self.engine.disparar(message)
            except Exception as exc:
                print(f"WARN: error pasando mensaje MIDI al engine: {exc}")

    def _push_saved_calibration(self) -> None:
        raw = self.config.get("firmware_calibration")
        if not isinstance(raw, dict):
            self.input_router.request_calibration_state()
            return
        payload = {}
        for key in ("min_hit", "quiet", "presence_noise", "refractory", "keep_connected"):
            try:
                payload[key] = int(raw[key])
            except Exception:
                pass
        if payload:
            self.input_router.send_calibration_config(payload)
        self.input_router.request_calibration_state()

    def _open_calibration_dialog(self) -> None:
        if self.calibration_dialog is None:
            self.calibration_dialog = CalibrationDialog(
                self,
                config=self.config,
                send_config=self._send_calibration_payload,
                request_state=self.input_router.request_calibration_state,
            )
            self.calibration_dialog.finished.connect(self._clear_calibration_dialog)

        self.calibration_dialog.show()
        self.calibration_dialog.raise_()
        self.calibration_dialog.activateWindow()
        self.input_router.request_calibration_state()

    def _send_calibration_payload(self, payload: dict) -> bool:
        self.config["firmware_calibration"] = dict(payload)
        save_config(self.config)
        return self.input_router.send_calibration_config(payload)

    def _clear_calibration_dialog(self) -> None:
        self.calibration_dialog = None
