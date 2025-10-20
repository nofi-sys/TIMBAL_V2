import os, sys
from pathlib import Path

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

        self._build_menu()
        self.statusBar().hide()

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu('Configuracion')
        act_change_sf2 = QAction('Cambiar SoundFont...', self)
        act_change_sf2.triggered.connect(self._change_soundfont)
        menu.addAction(act_change_sf2)

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
