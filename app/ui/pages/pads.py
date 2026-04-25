"""Pads page with legacy note sets, VU meters and optional effects dock."""
from __future__ import annotations

from typing import List

from PyQt5.QtCore import QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
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

from app.state.settings import save_config
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

PAD_COUNT = 5
DEFAULT_PAD_ENABLED: List[bool] = [True for _ in range(PAD_COUNT)]


class Vu(QWidget):
    SEGMENTS = 26

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("VuMeter")
        self.setMinimumSize(130, 340)
        self.level = 0
        self._enabled = True

        self.timer = QTimer(self)
        self.timer.setInterval(45)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def actualizar(self, value: int) -> None:
        if not self._enabled:
            self.level = 0
            self.update()
            return
        self.level = max(self.level, int(max(0, min(127, value))))
        self.update()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self.level = 0
        self.update()

    def _tick(self) -> None:
        if not self._enabled:
            self.level = 0
        else:
            self.level = max(0, self.level - 5)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        outer_path = QPainterPath()
        outer_path.addRoundedRect(outer, 22, 22)

        bg = QLinearGradient(outer.topLeft(), outer.bottomLeft())
        bg.setColorAt(0.0, QColor("#132438"))
        bg.setColorAt(0.18, QColor("#091522"))
        bg.setColorAt(1.0, QColor("#040a11"))
        painter.fillPath(outer_path, bg)

        painter.setPen(QPen(QColor("#314b63"), 1.2))
        painter.drawPath(outer_path)

        painter.setPen(QPen(QColor(140, 190, 230, 70), 1))
        painter.drawLine(
            int(outer.left() + 18),
            int(outer.top() + 8),
            int(outer.right() - 18),
            int(outer.top() + 8),
        )

        slot = outer.adjusted(18, 18, -18, -18)
        slot_path = QPainterPath()
        slot_path.addRoundedRect(slot, 14, 14)

        slot_bg = QLinearGradient(slot.topLeft(), slot.bottomLeft())
        slot_bg.setColorAt(0.0, QColor("#070d14"))
        slot_bg.setColorAt(1.0, QColor("#02060a"))
        painter.fillPath(slot_path, slot_bg)

        painter.setPen(QPen(QColor("#172536"), 1))
        painter.drawPath(slot_path)

        active = 0
        if self._enabled:
            active = int(round((self.level / 127.0) * self.SEGMENTS))
            active = max(0, min(self.SEGMENTS, active))

        gap = 4.0
        side_pad = 8.0
        total_gap = gap * (self.SEGMENTS - 1)
        seg_h = max(5.0, (slot.height() - 22 - total_gap) / self.SEGMENTS)
        seg_w = slot.width() - side_pad * 2
        bottom = slot.bottom() - 12

        for i in range(self.SEGMENTS):
            y = bottom - (i + 1) * seg_h - i * gap
            rect = QRectF(slot.left() + side_pad, y, seg_w, seg_h)
            is_on = i < active and self._enabled

            if is_on:
                segment_bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                segment_bg.setColorAt(0.0, QColor("#25f3eb"))
                segment_bg.setColorAt(1.0, QColor("#0aa6a6"))
                painter.setPen(QPen(QColor("#35fff6"), 0.8))
                painter.setBrush(segment_bg)
            else:
                off = QColor("#121922") if self._enabled else QColor("#070b10")
                border = QColor("#243241") if self._enabled else QColor("#121923")
                painter.setPen(QPen(border, 0.8))
                painter.setBrush(off)

            painter.drawRoundedRect(rect, 3, 3)

        if active > 0 and self._enabled:
            glow = QRectF(slot.left() + 8, slot.bottom() - 34, slot.width() - 16, 28)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 224, 209, 35))
            painter.drawRoundedRect(glow, 10, 10)


class PadsPage(QWidget):
    def __init__(self, engine, config: dict | None = None) -> None:
        super().__init__()
        self.engine = engine
        self.config = config if config is not None else {}
        self._config_key = "effects_panel_collapsed"
        self.note_sets: List[List[str]] = [list(row) for row in DEFAULT_NOTE_SETS]
        self.active_set = 0
        self.pad_buttons: List[QPushButton] = []
        self.pad_power_buttons: List[QPushButton] = []
        self.pad_presence_labels: List[QLabel] = []
        self.prev_labels: List[QLabel] = []
        self.next_labels: List[QLabel] = []
        self.pad_muted: List[bool] = [False for _ in range(PAD_COUNT)]
        self.pad_enabled: List[bool] = self._load_pad_enabled()
        self.pad_connected: List[bool | None] = [None for _ in range(PAD_COUNT)]
        self.pad_noise: List[int | None] = [None for _ in range(PAD_COUNT)]
        self.pad_value: List[int | None] = [None for _ in range(PAD_COUNT)]
        self.pad_peak: List[int | None] = [None for _ in range(PAD_COUNT)]

        if "pad_enabled" not in self.config:
            self.config["pad_enabled"] = list(self.pad_enabled)
            self._save_config()

        wrapper = QHBoxLayout(self)
        wrapper.setContentsMargins(24, 18, 24, 24)
        wrapper.setSpacing(0)

        container = QWidget()
        container.setObjectName("PadsContent")
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        container.setMinimumWidth(1180)
        container.setMaximumWidth(16777215)
        main = QHBoxLayout(container)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(24)

        effects_collapsed = bool(self.config.get(self._config_key, False))
        self.effects_widget = EffectsPage(engine, self.config)
        self.effects_holder = QWidget()
        self.effects_holder.setObjectName("EffectsHolder")
        self.effects_holder.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        effects_layout = QVBoxLayout(self.effects_holder)
        effects_layout.setContentsMargins(14, 16, 14, 14)
        effects_layout.setSpacing(10)

        self.effects_toggle = QPushButton()
        self.effects_toggle.setObjectName("EffectsToggle")
        self.effects_toggle.setCheckable(True)
        self.effects_toggle.setChecked(not effects_collapsed)
        self.effects_toggle.clicked.connect(self._handle_effects_toggle)
        effects_layout.addWidget(self.effects_toggle, alignment=Qt.AlignHCenter)

        self.effects_container = QWidget()
        self.effects_container.setObjectName("EffectsContainer")
        container_layout = QVBoxLayout(self.effects_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.effects_widget)
        effects_layout.addWidget(self.effects_container, 1)
        effects_layout.addStretch(1)

        board = QWidget()
        board.setObjectName("PadBoard")
        board.setMinimumSize(780, 520)
        board.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        board_layout = QVBoxLayout(board)
        board_layout.setContentsMargins(30, 22, 30, 24)
        board_layout.setSpacing(10)

        vu_grid = QGridLayout()
        vu_grid.setHorizontalSpacing(20)
        for idx in range(PAD_COUNT):
            vu = Vu()
            vu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            vu_grid.addWidget(vu, 0, idx)
            vu_grid.setColumnStretch(idx, 1)
        self.vus = [vu_grid.itemAt(i).widget() for i in range(vu_grid.count())]
        board_layout.addLayout(vu_grid)

        bulk_row = QHBoxLayout()
        bulk_row.setContentsMargins(0, 0, 0, 0)
        bulk_row.setSpacing(12)
        for label, handler in (
            ("TODOS ON", lambda: self._set_all_pads_enabled(True)),
            ("TODOS OFF", lambda: self._set_all_pads_enabled(False)),
            ("SOLO ESTABLES", self._enable_only_stable_pads),
        ):
            btn = QPushButton(label)
            btn.setObjectName("PadGlobalButton")
            btn.clicked.connect(handler)
            bulk_row.addWidget(btn)
        bulk_row.addStretch(1)
        board_layout.addLayout(bulk_row)

        power_row = QHBoxLayout()
        power_row.setContentsMargins(0, 2, 0, 2)
        power_row.setSpacing(20)
        for idx in range(PAD_COUNT):
            toggle = QPushButton()
            toggle.setObjectName("PadPowerButton")
            toggle.setCheckable(True)
            toggle.setMinimumHeight(38)
            toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            toggle.clicked.connect(
                lambda checked, pad=idx: self._set_pad_enabled(pad, checked)
            )
            power_row.addWidget(toggle)
            self.pad_power_buttons.append(toggle)
        board_layout.addLayout(power_row)

        presence_row = QHBoxLayout()
        presence_row.setContentsMargins(0, 0, 0, 0)
        presence_row.setSpacing(20)
        for _ in range(PAD_COUNT):
            lbl = QLabel()
            lbl.setObjectName("PadPresenceLabel")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumHeight(28)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            presence_row.addWidget(lbl)
            self.pad_presence_labels.append(lbl)
        board_layout.addLayout(presence_row)

        prev_row = QHBoxLayout()
        prev_row.setContentsMargins(0, 4, 0, 2)
        prev_row.setSpacing(14)
        for _ in range(PAD_COUNT):
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumHeight(24)
            lbl.setObjectName("SetGhostPrev")
            prev_row.addWidget(lbl)
            self.prev_labels.append(lbl)
        board_layout.addLayout(prev_row)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)
        for idx in range(PAD_COUNT):
            btn = QPushButton()
            btn.setObjectName("PadNoteButton")
            btn.setMinimumSize(150, 88)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setToolTip("Click para tocar - clic derecho para cambiar nota")
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
        next_row.setContentsMargins(0, 4, 0, 0)
        next_row.setSpacing(14)
        for _ in range(PAD_COUNT):
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
        nav_layout.setContentsMargins(0, 46, 0, 46)
        nav_layout.setSpacing(26)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.btn_up, alignment=Qt.AlignHCenter)
        nav_layout.addWidget(self.set_label, alignment=Qt.AlignHCenter)
        nav_layout.addWidget(self.btn_down, alignment=Qt.AlignHCenter)
        nav_layout.addStretch(1)

        main.addWidget(self.effects_holder, 0)
        main.addWidget(board, 1)
        main.addWidget(nav_widget, 0, Qt.AlignVCenter)

        wrapper.addWidget(container, 1)

        self._apply_styles()
        self._set_effects_visible(not effects_collapsed, init=True)
        self._refresh_ui()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#PadsContent {
                background: #07111b;
            }
            QWidget#EffectsHolder {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #111f2c, stop:1 #07111b);
                border: 1px solid #2d465b;
                border-radius: 16px;
            }
            QPushButton#EffectsToggle {
                background: transparent;
                color: #19d8d2;
                border: 0;
                border-radius: 8px;
                padding: 0;
                font-size: 16px;
                font-weight: 800;
                text-align: left;
            }
            QPushButton#EffectsToggle:hover {
                color: #f2ffff;
            }
            QWidget#EffectsContainer {
                background: transparent;
                border: 0;
            }
            QWidget#PadBoard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #102033, stop:0.06 #17283a, stop:0.5 #07111b, stop:1 #08121c);
                border: 1px solid #2d465b;
                border-radius: 18px;
            }
            QWidget#VuMeter {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f1c2b, stop:0.5 #07111b, stop:1 #061019);
                border: 1px solid #1f3548;
                border-radius: 18px;
            }
            QWidget#PadBoard QPushButton#PadGlobalButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #123047, stop:0.45 #0a1826, stop:1 #061019);
                color: #d9f7fb;
                border: 1px solid #2d526a;
                border-radius: 9px;
                padding: 9px 20px;
                font-size: 12px;
                font-weight: 700;
            }
            QWidget#PadBoard QPushButton#PadGlobalButton:hover {
                border-color: #19d8d2;
                color: #ffffff;
            }
            QWidget#PadBoard QPushButton#PadNoteButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1b2c3f, stop:0.5 #122030, stop:1 #0b1420);
                color: #cfd8e6;
                border: 1px solid #36536b;
                border-radius: 12px;
                font-size: 32px;
                font-weight: 500;
            }
            QWidget#PadBoard QPushButton#PadNoteButton[armed="true"]:hover {
                border-color: #19d8d2;
                color: #ffffff;
            }
            QWidget#PadBoard QPushButton#PadNoteButton[armed="true"]:pressed {
                background: #061019;
                color: #19d8d2;
            }
            QWidget#PadBoard QPushButton#PadNoteButton[armed="false"] {
                background: #07111b;
                color: #475569;
                border-color: #162433;
            }
            QWidget#PadBoard QPushButton#PadNoteButton[armed="false"]:hover {
                background: #07111b;
                border-color: #162433;
            }
            QWidget#PadBoard QPushButton#PadPowerButton {
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
                padding: 8px 12px;
            }
            QWidget#PadBoard QPushButton#PadPowerButton[armed="true"] {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0d5661, stop:0.5 #092231, stop:1 #061019);
                color: #19d8d2;
                border: 1px solid #19d8d2;
            }
            QWidget#PadBoard QPushButton#PadPowerButton[armed="true"]:hover {
                color: #ffffff;
                border-color: #7dfcf6;
            }
            QWidget#PadBoard QPushButton#PadPowerButton[armed="false"] {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #121b26,
                    stop:1 #071019);
                color: #6f8195;
                border: 1px solid #27384a;
            }
            QWidget#PadBoard QPushButton#PadPowerButton[armed="false"]:hover {
                color: #9fb3c8;
                border-color: #3b536a;
            }
            QWidget#PadBoard QLabel#PadPresenceLabel {
                background: #07111b;
                border: 1px solid #2d526a;
                border-radius: 9px;
                color: #19d8d2;
                font-size: 12px;
                font-weight: 700;
                padding: 4px 6px;
            }
            QWidget#PadBoard QLabel#PadPresenceLabel[state="connected"] {
                color: #19d8d2;
                border-color: #19d8d2;
                background-color: #061a20;
            }
            QWidget#PadBoard QLabel#PadPresenceLabel[state="disconnected"] {
                color: #fecaca;
                border-color: #7f1d1d;
                background-color: #2f1212;
            }
            QWidget#PadBoard QLabel#PadPresenceLabel[state="unknown"] {
                color: #cbd5e1;
                border-color: #2d526a;
                background-color: #07111b;
            }
            QLabel#SetGhostPrev, QLabel#SetGhostNext {
                background: #07111b;
                border: 1px solid #26384d;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 3px 4px;
            }
            QLabel#SetGhostPrev {
                color: #b8c4d3;
            }
            QLabel#SetGhostNext {
                color: #b8c4d3;
            }
            QWidget#PadSetNav {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #111f2c, stop:1 #07111b);
                border: 1px solid #2d465b;
                border-radius: 16px;
            }
            QWidget#PadSetNav QPushButton {
                background: #07111b;
                color: #a8f7ff;
                border: 1px solid #2d526a;
                border-radius: 12px;
                font-size: 22px;
                font-weight: 700;
            }
            QWidget#PadSetNav QPushButton:hover {
                border-color: #19d8d2;
                color: #ffffff;
            }
            QWidget#PadSetNav QLabel {
                color: #dbe8f1;
                font-weight: 600;
                font-size: 20px;
            }
            """
        )

    def _set_effects_visible(self, expanded: bool, *, init: bool = False) -> None:
        self.effects_container.setVisible(expanded)
        if expanded:
            self.effects_toggle.setText("✣  EFECTOS")
            self.effects_holder.setMinimumWidth(340)
            self.effects_holder.setMaximumWidth(420)
        else:
            self.effects_toggle.setText(f"{chr(0x25B6)}")
            width = max(58, self.effects_toggle.sizeHint().width() + 18)
            self.effects_holder.setMinimumWidth(width)
            self.effects_holder.setMaximumWidth(width)
        if not init:
            self.config[self._config_key] = not expanded
            self._save_config()

    def _handle_effects_toggle(self, checked: bool) -> None:
        self._set_effects_visible(checked)

    def _power_icon(self) -> str:
        return chr(0x25B6)

    def _save_config(self) -> None:
        try:
            save_config(self.config)
        except Exception:
            pass

    def _load_pad_enabled(self) -> List[bool]:
        values = self.config.get("pad_enabled")
        if not isinstance(values, list):
            return list(DEFAULT_PAD_ENABLED)

        normalized: List[bool] = []
        for idx in range(PAD_COUNT):
            raw = values[idx] if idx < len(values) else True
            if isinstance(raw, str):
                enabled = raw.strip().lower() in ("1", "true", "on", "yes", "si")
            else:
                enabled = bool(raw)
            normalized.append(enabled)
        return normalized

    def _presence_state_name(self, pad_idx: int) -> str:
        connected = self.pad_connected[pad_idx]
        if connected is True:
            return "connected"
        if connected is False:
            return "disconnected"
        return "unknown"

    def _presence_text(self, pad_idx: int) -> str:
        connected = self.pad_connected[pad_idx]
        noise = self.pad_noise[pad_idx]
        if connected is True:
            return f"Estable n={noise}" if noise is not None else "Estable"
        if connected is False:
            return f"Flotante n={noise}" if noise is not None else "Flotante"
        return "Sin datos"

    def _is_pad_enabled(self, pad_idx: int) -> bool:
        return 0 <= pad_idx < len(self.pad_enabled) and self.pad_enabled[pad_idx]

    def _is_pad_active(self, pad_idx: int) -> bool:
        if not self._is_pad_enabled(pad_idx):
            return False
        connected = self.pad_connected[pad_idx]
        return connected is not False

    def _restyle(self, widget: QWidget) -> None:
        style = widget.style()
        if style is None:
            return
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _sync_pad_visual_state(self, pad_idx: int) -> None:
        enabled = self._is_pad_enabled(pad_idx)
        active = self._is_pad_active(pad_idx)
        presence_state = self._presence_state_name(pad_idx)

        if pad_idx < len(self.pad_buttons):
            note_button = self.pad_buttons[pad_idx]
            note_button.setProperty("armed", active)
            if not enabled:
                note_button.setToolTip(
                    "Pad apagado manualmente: no dispara ni acepta golpes externos"
                )
            elif presence_state == "disconnected":
                note_button.setToolTip(
                    "Entrada inestable o sin cable: firmware bloqueando este pad"
                )
            else:
                note_button.setToolTip("Click para tocar - clic derecho para cambiar nota")
            self._restyle(note_button)

        if pad_idx < len(self.pad_power_buttons):
            power_button = self.pad_power_buttons[pad_idx]
            power_button.blockSignals(True)
            power_button.setChecked(enabled)
            power_button.setProperty("armed", enabled)
            power_button.setText(
                f"{self._power_icon()}  P{pad_idx + 1} {'ON' if enabled else 'OFF'}"
            )
            if not enabled:
                power_button.setToolTip("Pad apagado manualmente")
            elif presence_state == "connected":
                power_button.setToolTip("Pad activo y con entrada estable")
            elif presence_state == "disconnected":
                power_button.setToolTip(
                    "Pad manualmente ON, pero bloqueado por entrada flotante"
                )
            else:
                power_button.setToolTip(
                    "Pad manual. Con el firmware nuevo vas a ver el estado real abajo"
                )
            power_button.blockSignals(False)
            self._restyle(power_button)

        if pad_idx < len(self.pad_presence_labels):
            lbl = self.pad_presence_labels[pad_idx]
            lbl.setProperty("state", presence_state)
            lbl.setText(self._presence_text(pad_idx))
            value = self.pad_value[pad_idx]
            peak = self.pad_peak[pad_idx]
            noise = self.pad_noise[pad_idx]
            tooltip = f"Estado: {self._presence_text(pad_idx)}"
            if value is not None:
                tooltip += f" | valor={value}"
            if peak is not None:
                tooltip += f" | pico={peak}"
            if noise is not None:
                tooltip += f" | ruido={noise}"
            lbl.setToolTip(tooltip)
            self._restyle(lbl)

        if pad_idx < len(self.vus):
            self.vus[pad_idx].set_enabled(active)

    def _set_pad_enabled(
        self,
        pad_idx: int,
        enabled: bool,
        *,
        persist: bool = True,
    ) -> None:
        if pad_idx < 0 or pad_idx >= PAD_COUNT:
            return

        enabled = bool(enabled)
        if pad_idx >= len(self.pad_enabled):
            self.pad_enabled.extend([True] * (pad_idx + 1 - len(self.pad_enabled)))

        self.pad_enabled[pad_idx] = enabled
        self.config["pad_enabled"] = list(self.pad_enabled)

        if not self._is_pad_active(pad_idx):
            target_note = self._pad_note_value(pad_idx)
            if target_note is not None:
                try:
                    self.engine.disparar(
                        Message("note_off", note=target_note, velocity=0, channel=0)
                    )
                except Exception:
                    pass
            try:
                self.vus[pad_idx].actualizar(0)
            except Exception:
                pass

        print(f"DEBUG: Pad {pad_idx} {'habilitado' if enabled else 'apagado'}")
        self._sync_pad_visual_state(pad_idx)
        if persist:
            self._save_config()

    def _set_all_pads_enabled(self, enabled: bool) -> None:
        for pad_idx in range(PAD_COUNT):
            self._set_pad_enabled(pad_idx, enabled, persist=False)
        self._save_config()

    def _enable_only_stable_pads(self) -> None:
        for pad_idx in range(PAD_COUNT):
            self._set_pad_enabled(
                pad_idx,
                self.pad_connected[pad_idx] is True,
                persist=False,
            )
        self._save_config()

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
        for pad_idx in range(PAD_COUNT):
            self._sync_pad_visual_state(pad_idx)

    def _change_set(self, delta: int) -> None:
        self.active_set = (self.active_set + delta) % len(self.note_sets)
        self._refresh_ui()

    def _trigger_pad(self, pad_idx: int) -> None:
        if not self._is_pad_active(pad_idx):
            print(f"DEBUG: Click ignorado; pad {pad_idx} no esta activo.")
            return

        note_name = self._current_notes()[pad_idx]
        midi_note = to_midi(note_name)
        velocity = 110
        self.vus[pad_idx].actualizar(velocity)
        try:
            self.engine.disparar(
                Message("note_on", note=midi_note, velocity=velocity, channel=0)
            )
            QTimer.singleShot(
                250,
                lambda n=midi_note: self.engine.disparar(
                    Message("note_off", note=n, velocity=0, channel=0)
                ),
            )
        except Exception as exc:
            print("hit error:", exc)

    def _pad_note_value(self, pad_idx: int) -> int | None:
        notes = self._current_notes()
        if 0 <= pad_idx < len(notes):
            return to_midi(notes[pad_idx])
        return None

    def _find_pad_by_midi(self, midi_note: int) -> int | None:
        try:
            target = int(midi_note)
        except Exception:
            return None
        notes = self._current_notes()
        for idx, name in enumerate(notes):
            try:
                if to_midi(name) == target:
                    return idx
            except Exception:
                continue
        return None

    def find_pad_by_midi(self, midi_note: int) -> int | None:
        return self._find_pad_by_midi(midi_note)

    def handle_pad_state(
        self,
        *,
        pad_idx: int,
        connected: bool | None,
        noise: int | None = None,
        value: int | None = None,
        peak: int | None = None,
    ) -> None:
        if pad_idx < 0 or pad_idx >= PAD_COUNT:
            return

        self.pad_connected[pad_idx] = connected
        self.pad_noise[pad_idx] = noise
        self.pad_value[pad_idx] = value
        self.pad_peak[pad_idx] = peak

        if not self._is_pad_active(pad_idx):
            target_note = self._pad_note_value(pad_idx)
            if target_note is not None:
                try:
                    self.engine.disparar(
                        Message("note_off", note=target_note, velocity=0, channel=0)
                    )
                except Exception:
                    pass
            try:
                self.vus[pad_idx].actualizar(0)
            except Exception:
                pass

        self._sync_pad_visual_state(pad_idx)

    def handle_external_hit(
        self,
        *,
        note: int | None,
        velocity: int,
        pad_idx: int | None = None,
    ) -> bool:
        """Reutiliza el mismo flujo de _trigger_pad para golpes externos."""
        raw_vel = int(max(1, min(127, velocity)))

        if pad_idx is None and note is not None:
            pad_idx = self._find_pad_by_midi(note)
        if pad_idx is not None and (pad_idx < 0 or pad_idx >= len(self._current_notes())):
            print(f"DEBUG: Pad fuera de rango ({pad_idx}); se ignora hit.")
            pad_idx = None

        if pad_idx is not None and not self._is_pad_active(pad_idx):
            try:
                self.vus[pad_idx].actualizar(0)
            except Exception:
                pass
            print(f"DEBUG: Hit bloqueado; pad {pad_idx} no esta activo.")
            return False

        if pad_idx is not None and pad_idx < len(self.pad_muted) and self.pad_muted[pad_idx]:
            try:
                self.vus[pad_idx].actualizar(0)
            except Exception:
                pass
            print(f"DEBUG: Hit bloqueado por mute en pad {pad_idx}")
            return False

        vel = raw_vel
        if pad_idx is not None:
            calib = self.config.get("pad_calibration", [0, 0, 0, 0, 0])
            extra = 0
            if 0 <= pad_idx < len(calib):
                try:
                    extra = int(calib[pad_idx])
                except (TypeError, ValueError):
                    extra = 0
            factor = 1.0 + (extra / 20.0)
            vel = int(max(1, min(127, round(vel * factor))))

        gate = int(getattr(self.effects_widget, "min_velocity", 0))
        if vel < gate:
            print(f"DEBUG: Hit descartado por gate ({vel} < {gate})")
            return False

        target_note = None
        if pad_idx is not None:
            target_note = self._pad_note_value(pad_idx)
        elif note is not None:
            target_note = int(note)

        if target_note is None:
            print("DEBUG: No se pudo resolver nota destino para el hit externo.")
            return False

        if pad_idx is not None:
            try:
                self.vus[pad_idx].actualizar(vel)
            except Exception:
                pass

        try:
            self.engine.disparar(
                Message("note_on", note=target_note, velocity=vel, channel=0)
            )
            print(f"DEBUG: Hit externo -> pad={pad_idx} note={target_note} vel={vel}")
            QTimer.singleShot(
                250,
                lambda n=target_note: self.engine.disparar(
                    Message("note_off", note=n, velocity=0, channel=0)
                ),
            )
            return True
        except Exception as exc:
            print("hit error ext:", exc)
            return False

    def handle_mute(
        self,
        *,
        pad_idx: int | None = None,
        note: int | None = None,
        state: int = 1,
    ) -> bool:
        """Recibe eventos de mute externos y manda note_off del pad correspondiente."""
        if pad_idx is None and note is not None:
            pad_idx = self._find_pad_by_midi(note)
        if pad_idx is None:
            if note is None:
                return False
            try:
                resolved_note = int(note)
                self.engine.disparar(
                    Message("note_off", note=resolved_note, velocity=0, channel=0)
                )
                print(f"DEBUG: Mute sin pad -> note_off nota {resolved_note}")
                return True
            except Exception as exc:
                print("mute error (fallback):", exc)
                return False
        if pad_idx < 0 or pad_idx >= len(self._current_notes()):
            return False

        muted = bool(state)
        if pad_idx >= len(self.pad_muted):
            self.pad_muted = self.pad_muted + [False] * (
                pad_idx + 1 - len(self.pad_muted)
            )
        self.pad_muted[pad_idx] = muted

        target_note = self._pad_note_value(pad_idx)
        if target_note is None:
            return False
        print(f"DEBUG: Mute pad={pad_idx} state={muted} -> note={target_note}")

        try:
            self.engine.disparar(
                Message("note_off", note=target_note, velocity=0, channel=0)
            )
            try:
                self.vus[pad_idx].actualizar(0)
            except Exception:
                pass
            return True
        except Exception as exc:
            print("mute error:", exc)
            return False

    def _edit_pad_note(self, pad_idx: int) -> None:
        dialog = NoteSelectorDialog(self)
        dialog.set_current_note(self._current_notes()[pad_idx])
        if dialog.exec_():
            new_note = dialog.note()
            self.note_sets[self.active_set][pad_idx] = new_note
            self.pad_buttons[pad_idx].setText(new_note)
