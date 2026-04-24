import sys
import subprocess
from pathlib import Path

from mido import Message
from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QAction,
    QInputDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
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
    win.resize(1600, 900)
    win.show()
    sys.exit(app.exec_())


class AppChrome(QWidget):
    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.setObjectName("AppChrome")
        self.setFixedHeight(58)
        self._drag_pos: QPoint | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.window.move(event.globalPos() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and hasattr(self.window, "_toggle_maximize"):
            self.window._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, engine, config):
        super().__init__()
        self.engine = engine
        self.config = config
        self.setWindowTitle("Timbal Digital - Testeo")
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)

        self.pads_page = PadsPage(engine, config)

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
        self._build_shell()
        self.statusBar().hide()
        QTimer.singleShot(1200, self._push_saved_calibration)

    def closeEvent(self, event):
        self.input_router.close()
        if self.dino_process:
            self.dino_process.kill()
        event.accept()

    def _build_menu(self) -> None:
        self.menu_config = QMenu("Configuración", self)
        act_change_sf2 = QAction("Cambiar SoundFont...", self)
        act_change_sf2.triggered.connect(self._change_soundfont)
        self.menu_config.addAction(act_change_sf2)
        act_program_sf2 = QAction("Preset/Bank SoundFont...", self)
        act_program_sf2.triggered.connect(self._change_soundfont_program)
        self.menu_config.addAction(act_program_sf2)
        act_calibration = QAction("Calibración en vivo...", self)
        act_calibration.triggered.connect(self._open_calibration_dialog)
        self.menu_config.addAction(act_calibration)

        self.menu_games = QMenu("Juegos", self)
        act_dino = QAction("Iniciar DINO RITMO", self)
        act_dino.triggered.connect(self._launch_dino_ritmo)
        self.menu_games.addAction(act_dino)

    def _build_shell(self) -> None:
        shell = QWidget()
        shell.setObjectName("AppShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        chrome = AppChrome(self)
        chrome_layout = QHBoxLayout(chrome)
        chrome_layout.setContentsMargins(28, 0, 22, 0)
        chrome_layout.setSpacing(12)

        mark = QLabel(chr(0x25CE))
        mark.setObjectName("AppMark")
        chrome_layout.addWidget(mark)

        title = QLabel("Timbal Digital")
        title.setObjectName("AppTitle")
        chrome_layout.addWidget(title)

        subtitle = QLabel("- Testeo")
        subtitle.setObjectName("AppTitleMuted")
        chrome_layout.addWidget(subtitle)
        chrome_layout.addStretch(1)

        btn_min = self._window_button("-")
        btn_min.clicked.connect(self.showMinimized)
        btn_max = self._window_button("□")
        btn_max.clicked.connect(self._toggle_maximize)
        btn_close = self._window_button("X", close=True)
        btn_close.clicked.connect(self.close)
        chrome_layout.addWidget(btn_min)
        chrome_layout.addWidget(btn_max)
        chrome_layout.addWidget(btn_close)

        tabs = QWidget()
        tabs.setObjectName("AppTabs")
        tabs.setFixedHeight(45)
        tabs_layout = QHBoxLayout(tabs)
        tabs_layout.setContentsMargins(4, 0, 0, 0)
        tabs_layout.setSpacing(0)

        self.btn_config = self._tab_button("Configuración")
        self.btn_config.clicked.connect(
            lambda: self._show_tab_menu(self.btn_config, self.menu_config)
        )
        self.btn_games = self._tab_button("Juegos")
        self.btn_games.clicked.connect(
            lambda: self._show_tab_menu(self.btn_games, self.menu_games)
        )
        self.btn_test = self._tab_button("Testeo", active=True)
        tabs_layout.addWidget(self.btn_config)
        tabs_layout.addWidget(self.btn_games)
        tabs_layout.addWidget(self.btn_test)
        tabs_layout.addStretch(1)

        shell_layout.addWidget(chrome)
        shell_layout.addWidget(tabs)
        shell_layout.addWidget(self.pads_page, 1)
        self.setCentralWidget(shell)

    def _window_button(self, text: str, *, close: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("WindowCloseButton" if close else "WindowButton")
        btn.setFixedSize(44, 34)
        btn.setFocusPolicy(Qt.NoFocus)
        return btn

    def _tab_button(self, text: str, *, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("ChromeTab")
        btn.setProperty("active", active)
        btn.setCheckable(False)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        return btn

    def _show_tab_menu(self, button: QPushButton, menu: QMenu) -> None:
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

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
