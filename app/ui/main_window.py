import os, sys
import subprocess
from pathlib import Path

import mido
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QAction
from PyQt5.QtCore import Qt, QCoreApplication

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
    resolved = Path(sf2_entry) if sf2_entry else None
    if not resolved or not resolved.exists():
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
        self._setup_midi()

        self._build_menu()
        self.statusBar().hide()

    def _setup_midi(self):
        try:
            # No especificar el nombre crea un puerto virtual que recibe
            # mensajes de todos los dispositivos, evitando conflictos.
            self.midi_port = mido.open_input(virtual=True, callback=self._on_midi_message)
            print(f"INFO: App principal escuchando en puerto MIDI virtual: {self.midi_port.name}")
        except BaseException as e:
            print(f"WARN: No se pudo abrir el puerto MIDI en la app principal: {e}")

    def _on_midi_message(self, message):
        # Primero, disparamos el sonido en la app principal
        if message.type == 'note_on':
            self.engine.disparar(message)

        # Luego, si el juego está abierto, le enviamos el golpe
        if self.dino_process and self.dino_process.poll() is None:
            if message.type == 'note_on':
                try:
                    self.dino_process.stdin.write("HIT\n")
                    self.dino_process.stdin.flush()
                except Exception as e:
                    print(f"ERROR: No se pudo comunicar con DINO_RITMO: {e}")

    def closeEvent(self, event):
        if self.midi_port:
            self.midi_port.close()
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
            self.dino_process = subprocess.Popen(
                [sys.executable, "rhythm_dino_game.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, # Opcional: para ver la salida del juego
                stderr=subprocess.PIPE, # Opcional: para ver los errores del juego
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
