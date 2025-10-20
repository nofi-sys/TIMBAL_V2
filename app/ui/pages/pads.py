"""Pads page with legacy note sets, VU meters and optional effects dock."""
from __future__ import annotations

from typing import List

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from mido import Message

from app.ui.components.note_selector import NoteSelectorDialog
from app.ui.pages.effects import EffectsPage

NOTE_NAMES = "C C# D D# E F F# G G# A A# B".split()


def to_midi(note: str) -> int:
    name = note[:-1]
    octave = int(note[-1])
    return NOTE_NAMES.index(name) + 12 * (octave + 1)


DEFAULT_NOTE_SETS: List[List[str]] = [
    ["A2", "E3", "A3", "C4", "E4"],
    ["E2", "B2", "E3", "G#3", "B3"],
    ["D2", "A2", "D3", "F#3", "A3"],
    ["C2", "G2", "C3", "E3", "G3"],
    ["G2", "D3", "G3", "B3", "D4"],
]


class Vu(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(48, 320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(4)
        self.bars: List[QLabel] = []
        for _ in range(21):
            bar = QLabel()
            bar.setFixedHeight(18)
            bar.setStyleSheet("background:#2b3648;")
            layout.addWidget(bar)
            self.bars.append(bar)
        layout.addStretch(1)
        self.level = 0
        self.timer = QTimer(self)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def actualizar(self, value: int) -> None:
        self.level = max(self.level, int(value))

    def _tick(self) -> None:
        self.level = max(0, self.level - 6)
        active = self.level // 9
        for idx, bar in enumerate(reversed(self.bars)):
            bar.setStyleSheet(
                "background:#22c55e" if idx < active else "background:#2b3648;"
            )


class PadsPage(QWidget):
    def __init__(self, engine, config: dict | None = None) -> None:
        super().__init__()
        self.engine = engine
        self.config = config if config is not None else {}
        self._config_key = "effects_panel_collapsed"
        self.note_sets: List[List[str]] = [list(row) for row in DEFAULT_NOTE_SETS]
        self.active_set = 0
        self.pad_buttons: List[QPushButton] = []
        self.prev_labels: List[QLabel] = []
        self.next_labels: List[QLabel] = []

        wrapper = QHBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)
        wrapper.addStretch(1)

        container = QWidget()
        container.setObjectName("PadsContent")
        container.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)
        container.setMinimumWidth(1260)
        container.setMaximumWidth(1500)
        main = QHBoxLayout(container)
        main.setContentsMargins(24, 16, 24, 16)
        main.setSpacing(24)

        effects_collapsed = bool(self.config.get(self._config_key, False))
        self.effects_widget = EffectsPage(engine, self.config)
        self.effects_holder = QWidget()
        self.effects_holder.setObjectName("EffectsHolder")
        self.effects_holder.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        effects_layout = QVBoxLayout(self.effects_holder)
        effects_layout.setContentsMargins(0, 12, 0, 12)
        effects_layout.setSpacing(12)

        self.effects_toggle = QPushButton()
        self.effects_toggle.setObjectName("EffectsToggle")
        self.effects_toggle.setCheckable(True)
        self.effects_toggle.setChecked(not effects_collapsed)
        self.effects_toggle.clicked.connect(self._handle_effects_toggle)
        effects_layout.addWidget(self.effects_toggle, alignment=Qt.AlignHCenter)

        self.effects_container = QWidget()
        self.effects_container.setObjectName("EffectsContainer")
        container_layout = QVBoxLayout(self.effects_container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.addWidget(self.effects_widget)
        effects_layout.addWidget(self.effects_container, 1)
        effects_layout.addStretch(1)

        board = QWidget()
        board.setObjectName("PadBoard")
        board.setMinimumSize(540, 380)
        board.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        board_layout = QVBoxLayout(board)
        board_layout.setContentsMargins(28, 16, 28, 22)
        board_layout.setSpacing(10)

        vu_grid = QGridLayout()
        vu_grid.setHorizontalSpacing(18)
        for idx in range(5):
            vu = Vu()
            vu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            vu_grid.addWidget(vu, 0, idx)
            vu_grid.setColumnStretch(idx, 1)
        self.vus = [vu_grid.itemAt(i).widget() for i in range(vu_grid.count())]
        board_layout.addLayout(vu_grid)

        prev_row = QHBoxLayout()
        prev_row.setContentsMargins(0, 8, 0, 6)
        prev_row.setSpacing(14)
        for _ in range(5):
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumHeight(24)
            lbl.setObjectName("SetGhostPrev")
            prev_row.addWidget(lbl)
            self.prev_labels.append(lbl)
        board_layout.addLayout(prev_row)

        grid = QGridLayout()
        grid.setContentsMargins(16, 0, 16, 0)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)
        for idx in range(5):
            btn = QPushButton()
            btn.setMinimumSize(150, 88)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setToolTip('Click para tocar - clic derecho para cambiar nota')
            btn.clicked.connect(lambda _, pad=idx: self._trigger_pad(pad))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _, pad=idx: self._edit_pad_note(pad)
            )
            grid.addWidget(btn, 0, idx)
            self.pad_buttons.append(btn)
            grid.setColumnStretch(idx, 1)
        board_layout.addLayout(grid)

        next_row = QHBoxLayout()
        next_row.setContentsMargins(0, 6, 0, 0)
        next_row.setSpacing(14)
        for _ in range(5):
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumHeight(24)
            lbl.setObjectName("SetGhostNext")
            next_row.addWidget(lbl)
            self.next_labels.append(lbl)
        board_layout.addLayout(next_row)

        self.btn_up = QPushButton(chr(0x25B2))
        self.btn_up.setFixedSize(54, 58)
        self.btn_up.clicked.connect(lambda: self._change_set(-1))
        self.btn_down = QPushButton(chr(0x25BC))
        self.btn_down.setFixedSize(54, 58)
        self.btn_down.clicked.connect(lambda: self._change_set(1))
        self.set_label = QLabel()
        self.set_label.setAlignment(Qt.AlignCenter)

        nav_widget = QWidget()
        nav_widget.setObjectName("PadSetNav")
        nav_widget.setFixedWidth(90)
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 60, 0, 60)
        nav_layout.setSpacing(24)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.btn_up, alignment=Qt.AlignHCenter)
        nav_layout.addWidget(self.set_label, alignment=Qt.AlignHCenter)
        nav_layout.addWidget(self.btn_down, alignment=Qt.AlignHCenter)
        nav_layout.addStretch(1)

        main.addWidget(self.effects_holder, 0)
        main.addWidget(board, 1)
        main.addWidget(nav_widget, 0, Qt.AlignVCenter)

        wrapper.addWidget(container)
        wrapper.addStretch(1)

        self._apply_styles()
        self._set_effects_visible(not effects_collapsed, init=True)
        self._refresh_ui()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#PadsContent {
                background: transparent;
            }
            QWidget#EffectsHolder {
                background: #111827;
                border: 1px solid #1f2937;
                border-radius: 22px;
            }
            QPushButton#EffectsToggle {
                background-color: #1f2937;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 14px;
                padding: 10px 14px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton#EffectsToggle:hover {
                background-color: #233044;
            }
            QWidget#EffectsContainer {
                background-color: #0f172a;
                border: 1px solid #1f2937;
                border-radius: 18px;
            }
            QWidget#PadBoard {
                background-color: #0f172a;
                border: 1px solid #1f2937;
                border-radius: 28px;
            }
            QWidget#PadBoard QPushButton {
                background-color: #1f2937;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 16px;
                font-size: 20px;
                font-weight: 700;
                letter-spacing: 0.6px;
            }
            QWidget#PadBoard QPushButton:hover {
                background-color: #3b82f6;
                border-color: #60a5fa;
            }
            QWidget#PadBoard QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QLabel#SetGhostPrev, QLabel#SetGhostNext {
                background-color: #111827;
                border: 1px dashed #1f2937;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel#SetGhostPrev {
                color: #475569;
            }
            QLabel#SetGhostNext {
                color: #94a3b8;
            }
            QWidget#PadSetNav {
                background: #111827;
                border: 1px solid #1f2937;
                border-radius: 22px;
            }
            QWidget#PadSetNav QPushButton {
                background-color: #1f2937;
                color: #e5e7eb;
                border: 1px solid #334155;
                border-radius: 12px;
                font-size: 22px;
                font-weight: 700;
            }
            QWidget#PadSetNav QPushButton:hover {
                background-color: #3b82f6;
            }
            QWidget#PadSetNav QLabel {
                color: #94a3b8;
                font-weight: 600;
                font-size: 18px;
            }
            """
        )

    def _set_effects_visible(self, expanded: bool, *, init: bool = False) -> None:
        self.effects_container.setVisible(expanded)
        if expanded:
            self.effects_toggle.setText("◀ Efectos")
            self.effects_holder.setMinimumWidth(280)
            self.effects_holder.setMaximumWidth(360)
        else:
            self.effects_toggle.setText("▶ Efectos")
            width = max(72, self.effects_toggle.sizeHint().width() + 16)
            self.effects_holder.setMinimumWidth(width)
            self.effects_holder.setMaximumWidth(width)
        if not init:
            self.config[self._config_key] = not expanded
            try:
                from app.state.settings import save_config
                save_config(self.config)
            except Exception:
                pass

    def _handle_effects_toggle(self, checked: bool) -> None:
        self._set_effects_visible(checked)

    def _current_notes(self) -> List[str]:
        return self.note_sets[self.active_set]

    def _refresh_ui(self) -> None:
        notes = self._current_notes()
        for idx, btn in enumerate(self.pad_buttons):
            btn.setText(notes[idx])

        prev_index = (self.active_set - 1) % len(self.note_sets)
        for idx, lbl in enumerate(self.prev_labels):
            lbl.setText(self.note_sets[prev_index][idx])

        next_index = (self.active_set + 1) % len(self.note_sets)
        for idx, lbl in enumerate(self.next_labels):
            lbl.setText(self.note_sets[next_index][idx])

        self.set_label.setText(f"{self.active_set + 1}/{len(self.note_sets)}")

    def _change_set(self, delta: int) -> None:
        self.active_set = (self.active_set + delta) % len(self.note_sets)
        self._refresh_ui()

    def _trigger_pad(self, pad_idx: int) -> None:
        note_name = self._current_notes()[pad_idx]
        midi_note = to_midi(note_name)
        velocity = 110
        self.vus[pad_idx].actualizar(velocity)
        try:
            self.engine.disparar(
                Message('note_on', note=midi_note, velocity=velocity, channel=0)
            )
            QTimer.singleShot(
                250,
                lambda n=midi_note: self.engine.disparar(
                    Message('note_off', note=n, velocity=0, channel=0)
                ),
            )
        except Exception as exc:
            print("hit error:", exc)

    def _edit_pad_note(self, pad_idx: int) -> None:
        dialog = NoteSelectorDialog(self)
        dialog.set_current_note(self._current_notes()[pad_idx])
        if dialog.exec_():
            new_note = dialog.note()
            self.note_sets[self.active_set][pad_idx] = new_note
            self.pad_buttons[pad_idx].setText(new_note)
