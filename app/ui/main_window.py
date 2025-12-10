import os, sys, json, subprocess
from pathlib import Path

import mido
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QAction
from PyQt5.QtCore import Qt, QCoreApplication, QTimer

from app.paths import resource_path
from app.theme.qss import build_qss
from app.audio.engine_legacy import SoundEngine
from app.state.settings import load_config, save_config
from app.ui.pages.pads import PadsPage


def run_new_ui():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyleSheet(build_qss())

    config = load_config()
    sf2_entry = config.get('last_sf2')
    resolved = None
    if sf2_entry:
        candidate = Path(sf2_entry)
        if candidate.exists():
            resolved = candidate

    bundled_sf2 = resource_path("soundonts", "timpani_collections.sf2")
    if resolved is None and bundled_sf2.exists():
        resolved = bundled_sf2

    if resolved is None:
        chosen, _ = QFileDialog.getOpenFileName(None, 'Seleccionar SoundFont', '.', 'SoundFont (*.sf2)')
        if not chosen:
            QMessageBox.critical(None, 'Error', 'No seleccionaste ningun SoundFont.')
            return
        resolved = Path(chosen)
        config['last_sf2'] = str(resolved)
        save_config(config)

    try:
        engine = SoundEngine(resolved)
    except Exception as exc:
        QMessageBox.critical(None, "Error", f"No se pudo iniciar el motor de audio\n{exc}")
        return
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
        self.midi_port = None
        self.serial_port = None
        self.serial_timer = None
        self._serial_buf = b""
        self._setup_midi()
        self._setup_serial()

        self._build_menu()
        self.statusBar().hide()

    def _setup_midi(self):
        try:
            # Crear un puerto virtual con un nombre específico.
            # Otros programas pueden enviar mensajes a este puerto.
            port_name = "TimbalDigitalInput"
            self.midi_port = mido.open_input(name=port_name, virtual=True, callback=self._on_midi_message)
            print(f"INFO: App principal escuchando en puerto MIDI virtual: {self.midi_port.name}")
        except BaseException as e:
            print(f"WARN: No se pudo abrir el puerto MIDI virtual: {e}. Probando puertos físicos...")
            try:
                inputs = mido.get_input_names()
                print(f"DEBUG: Puertos MIDI disponibles: {inputs}")
                if inputs:
                    name = inputs[0]
                    self.midi_port = mido.open_input(name, callback=self._on_midi_message)
                    print(f"INFO: Escuchando MIDI físico: {name}")
                else:
                    print("WARN: No hay puertos MIDI disponibles.")
            except Exception as e2:
                print(f"WARN: Fallback MIDI físico falló: {e2}")

    def _on_midi_message(self, message):
        typ = getattr(message, "type", "")
        note = getattr(message, "note", None)
        velocity = getattr(message, "velocity", 0)
        print(f"DEBUG: MIDI msg type={typ} note={note} vel={velocity}")
        if typ == "note_on" and velocity:
            handled = False
            try:
                handled = self.pads_page.handle_external_hit(note=note, velocity=velocity)
            except Exception as exc:
                print(f"WARN: error en hit MIDI -> pads: {exc}")
            if not handled:
                try:
                    self.engine.disparar(message)
                    print("DEBUG: MIDI note_on enviado directo al engine (sin pad match).")
                except Exception as exc:
                    print(f"WARN: error disparando engine: {exc}")
            self._forward_hit_to_dino()
        elif typ in ("note_off",) or (typ == "note_on" and velocity == 0):
            try:
                self.engine.disparar(message)
                print("DEBUG: MIDI note_off enviado al engine.")
            except Exception:
                pass

    def closeEvent(self, event):
        if self.midi_port:
            self.midi_port.close()
        if self.serial_port:
            try:
                self.serial_port.close()
            except Exception:
                pass
        if self.dino_process:
            self.dino_process.kill()
        event.accept()

    def _build_menu(self) -> None:
        menu_config = self.menuBar().addMenu('Configuracion')
        act_change_sf2 = QAction('Cambiar SoundFont...', self)
        act_change_sf2.triggered.connect(self._change_soundfont)
        menu_config.addAction(act_change_sf2)

        menu_games = self.menuBar().addMenu('Juegos')
        act_dino = QAction('Iniciar DINO RITMO', self)
        act_dino.triggered.connect(self._launch_dino_ritmo)
        menu_games.addAction(act_dino)

    def _launch_dino_ritmo(self):
        if self.dino_process and self.dino_process.poll() is None:
            QMessageBox.information(self, "DINO RITMO", "El juego ya está abierto.")
            return
        try:
            launcher = str(Path(sys.argv[0]).resolve())
            self.dino_process = subprocess.Popen(
                [sys.executable, launcher, "--run-dino"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,  # Opcional: para ver la salida del juego
                stderr=subprocess.PIPE,  # Opcional: para ver los errores del juego
                text=True,
                bufsize=1
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar DINO RITMO:\n{e}")

    def _change_soundfont(self) -> None:
        start = Path(self.config.get('last_sf2', '.'))
        directory = start.parent if start.is_file() else Path('.')
        chosen, _ = QFileDialog.getOpenFileName(self, 'Seleccionar SoundFont', str(directory), 'SoundFont (*.sf2)')
        if not chosen:
            return
        path = Path(chosen)
        try:
            self.engine.load_sf2_live(path)
        except Exception as exc:
            QMessageBox.critical(self, 'Error', f'No se pudo cambiar el SoundFont\n{exc}')
            return
        self.config['last_sf2'] = str(path)
        save_config(self.config)
        QMessageBox.information(self, 'SoundFont', f'SoundFont cargado: {path.name}')

    def _forward_hit_to_dino(self) -> None:
        if self.dino_process and self.dino_process.poll() is None:
            try:
                self.dino_process.stdin.write("HIT\n")
                self.dino_process.stdin.flush()
            except Exception as e:
                print(f"ERROR: No se pudo comunicar con DINO_RITMO: {e}")

    def _setup_serial(self):
        try:
            import serial  # type: ignore
            import serial.tools.list_ports  # type: ignore
        except Exception as e:
            print(f"WARN: pyserial no disponible ({e}); se omite lectura de mute/patch.")
            return

        try:
            port = None
            for p in serial.tools.list_ports.comports():
                if "Arduino" in p.description or "USB-SERIAL" in p.description or "USB Serial" in p.description:
                    port = p.device
                    break
            if not port:
                print("INFO: No se encontró puerto Arduino para leer HIT/MUTE.")
                return
            self.serial_port = serial.Serial(port, 9600, timeout=0)
            self.serial_timer = QTimer(self)
            self.serial_timer.setInterval(15)
            self.serial_timer.timeout.connect(self._poll_serial)
            self.serial_timer.start()
            print(f"INFO: Leyendo HIT/MUTE desde {port}")
        except Exception as e:
            print(f"WARN: No se pudo abrir serial para HIT/MUTE: {e}")
            self.serial_port = None

    def _poll_serial(self):
        if not self.serial_port:
            return
        try:
            waiting = self.serial_port.in_waiting
        except Exception as exc:
            print(f"WARN: Serial desconectado ({exc}), deteniendo lectura.")
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None
            if self.serial_timer:
                self.serial_timer.stop()
            return
        try:
            if waiting:
                self._serial_buf += self.serial_port.read(waiting)
        except Exception:
            return
        parts = self._serial_buf.split(b"\n")
        self._serial_buf = parts[-1]
        for raw in parts[:-1]:
            line = raw.decode(errors="ignore").strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                print(f"DEBUG: Línea serial no JSON: {line}")
                continue
            self._process_serial_message(data)

    def _process_serial_message(self, data):
        if not isinstance(data, dict):
            return
        if "HIT" in data:
            hit = data.get("HIT", {})
            try:
                pad_idx = int(hit.get("ch", -1))
            except Exception:
                pad_idx = None
            try:
                vel = int(hit.get("vel", 0))
            except Exception:
                vel = 0
            note = hit.get("note")
            print(f"DEBUG: Serial HIT ch={pad_idx} vel={vel} note={note}")
            try:
                self.pads_page.handle_external_hit(note=note, velocity=vel, pad_idx=pad_idx)
                self._forward_hit_to_dino()
            except Exception as exc:
                print(f"WARN: procesando HIT serial: {exc}")
        if "MUTE" in data:
            m = data.get("MUTE", {})
            try:
                pad_idx = int(m.get("ch", -1))
            except Exception:
                pad_idx = None
            state = m.get("state", 1)
            note = m.get("note")
            print(f"DEBUG: Serial MUTE ch={pad_idx} state={state} note={note}")
            try:
                self.pads_page.handle_mute(pad_idx=pad_idx, note=note, state=state)
            except Exception as exc:
                print(f"WARN: procesando MUTE serial: {exc}")
