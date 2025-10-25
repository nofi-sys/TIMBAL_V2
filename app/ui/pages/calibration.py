"""
Página de calibración de pads.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QGridLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from app.state.settings import save_calibration_profile

class CalibrationPage(QWidget):
    def __init__(self, engine, config: dict | None = None) -> None:
        super().__init__()
        self.engine = engine
        self.config = config if config is not None else {}
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Calibración de Pads")
        title.setObjectName("PageTitle")
        main_layout.addWidget(title, alignment=Qt.AlignCenter)

        # Pad selection
        pad_selection_layout = QHBoxLayout()
        pad_selection_label = QLabel("Seleccionar Pad:")
        pad_selection_layout.addWidget(pad_selection_label)
        self.pad_buttons = []
        for i in range(5):
            btn = QPushButton(f"Pad {i+1}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, pad_idx=i: self._select_pad(pad_idx))
            self.pad_buttons.append(btn)
            pad_selection_layout.addWidget(btn)
        main_layout.addLayout(pad_selection_layout)

        # Calibration steps
        calibration_layout = QGridLayout()

        # Soft hit
        self.soft_hit_label = QLabel("Golpea el pad suavemente")
        self.soft_hit_value = QLabel("-")
        self.soft_hit_button = QPushButton("Capturar valor suave")
        self.soft_hit_button.clicked.connect(self._start_capturing_soft)
        calibration_layout.addWidget(self.soft_hit_label, 0, 0)
        calibration_layout.addWidget(self.soft_hit_value, 0, 1)
        calibration_layout.addWidget(self.soft_hit_button, 0, 2)

        # Hard hit
        self.hard_hit_label = QLabel("Golpea el pad fuertemente")
        self.hard_hit_value = QLabel("-")
        self.hard_hit_button = QPushButton("Capturar valor fuerte")
        self.hard_hit_button.clicked.connect(self._start_capturing_hard)
        calibration_layout.addWidget(self.hard_hit_label, 1, 0)
        calibration_layout.addWidget(self.hard_hit_value, 1, 1)
        calibration_layout.addWidget(self.hard_hit_button, 1, 2)

        main_layout.addLayout(calibration_layout)

        # Save profile
        save_layout = QHBoxLayout()
        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("Nombre del perfil de calibración")
        save_button = QPushButton("Guardar Perfil")
        save_button.clicked.connect(self._save_profile)
        save_layout.addWidget(self.profile_name_input)
        save_layout.addWidget(save_button)
        main_layout.addLayout(save_layout)

        self.selected_pad = -1
        self.calibrating_midi_note = None
        self.capturing_soft = False
        self.capturing_hard = False

        self._apply_styles()

    def _select_pad(self, pad_idx: int):
        for i, btn in enumerate(self.pad_buttons):
            if i != pad_idx:
                btn.setChecked(False)
        self.selected_pad = pad_idx
        self.calibrating_midi_note = None
        self.soft_hit_value.setText("-")
        self.hard_hit_value.setText("-")
        QMessageBox.information(self, "Calibración", f"Pad {pad_idx + 1} seleccionado. Por favor, golpea el pad una vez para identificarlo.")

    def on_midi_message(self, message):
        if message.type != 'note_on' or self.selected_pad == -1:
            return

        if self.calibrating_midi_note is None:
            self.calibrating_midi_note = message.note
            QMessageBox.information(self, "Calibración", f"Pad identificado (nota MIDI: {message.note}). Ahora puedes capturar los valores.")
            return

        if message.note == self.calibrating_midi_note:
            velocity = message.velocity
            if self.capturing_soft:
                self.soft_hit_value.setText(str(velocity))
                self.capturing_soft = False
            elif self.capturing_hard:
                self.hard_hit_value.setText(str(velocity))
                self.capturing_hard = False

    def _start_capturing_soft(self):
        if self.selected_pad != -1:
            self.capturing_soft = True
            self.capturing_hard = False

    def _start_capturing_hard(self):
        if self.selected_pad != -1:
            self.capturing_hard = True
            self.capturing_soft = False

    def _save_profile(self):
        profile_name = self.profile_name_input.text()
        if not profile_name:
            QMessageBox.warning(self, "Error", "Por favor, introduce un nombre para el perfil.")
            return

        if self.selected_pad == -1:
            QMessageBox.warning(self, "Error", "Por favor, selecciona un pad para calibrar.")
            return

        soft_value = self.soft_hit_value.text()
        hard_value = self.hard_hit_value.text()

        if soft_value == "-" or hard_value == "-":
            QMessageBox.warning(self, "Error", "Por favor, captura los valores para el golpe suave y fuerte.")
            return

        settings = {
            "pad": self.selected_pad,
            "soft": int(soft_value),
            "hard": int(hard_value)
        }
        save_calibration_profile(profile_name, settings)
        QMessageBox.information(self, "Éxito", f"Perfil de calibración '{profile_name}' guardado.")

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QLabel#PageTitle {
                font-size: 24px;
                font-weight: 700;
                margin-bottom: 20px;
            }
            QPushButton {
                background-color: #1f2937;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 10px 14px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            QPushButton:checked {
                background-color: #1d4ed8;
            }
            QLineEdit {
                background-color: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 10px;
            }
        """)
