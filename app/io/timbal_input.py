"""Shared MIDI/serial input router for the timbal apps."""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass

import mido
from PyQt5.QtCore import QObject, pyqtSignal

try:
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    serial = None  # type: ignore[assignment]

PREFERRED_MIDI_KEYWORDS = ("arduino", "leonardo", "timbal", "micro")
LOW_PRIORITY_MIDI_KEYWORDS = ("digital piano", "microsoft gs")
PREFERRED_SERIAL_KEYWORDS = (
    "arduino",
    "leonardo",
    "timbal",
    "usb serial",
    "usb-serial",
    "ch340",
    "cp210",
)
GENERIC_SERIAL_KEYWORDS = (
    "communications port",
    "standard port types",
    "acpi\\pnp0501",
)
DEFAULT_SERIAL_BAUD = int(os.environ.get("TIMBAL_SERIAL_BAUD", "115200"))
DEDUP_WINDOW_SECONDS = 0.045
DEFAULT_PREFER_MIDI_HITS = os.environ.get("TIMBAL_PREFER_MIDI_HITS", "1") != "0"


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def list_serial_ports():
    if serial is None:
        return []
    try:
        return list(serial.tools.list_ports.comports())
    except Exception:
        return []


def score_serial_port(port) -> int:
    text = " ".join(
        part
        for part in (
            getattr(port, "device", ""),
            getattr(port, "description", ""),
            getattr(port, "manufacturer", ""),
            getattr(port, "product", ""),
            getattr(port, "hwid", ""),
        )
        if part
    ).lower()
    score = 0
    for keyword in PREFERRED_SERIAL_KEYWORDS:
        if keyword in text:
            score += 100
    for keyword in GENERIC_SERIAL_KEYWORDS:
        if keyword in text:
            score -= 300
    if "bluetooth" in text:
        score -= 200
    return score


def pick_best_serial_port():
    ports = list_serial_ports()
    if not ports:
        return None
    ordered = sorted(ports, key=score_serial_port, reverse=True)
    best = ordered[0]
    if score_serial_port(best) <= 0:
        return None
    return best


@dataclass(frozen=True)
class TimbalHit:
    source: str
    timestamp: float
    note: int | None = None
    velocity: int = 0
    pad_idx: int | None = None


@dataclass(frozen=True)
class TimbalMute:
    source: str
    timestamp: float
    state: int
    note: int | None = None
    pad_idx: int | None = None


@dataclass(frozen=True)
class TimbalPadState:
    source: str
    timestamp: float
    pad_idx: int
    connected: bool | None = None
    noise: int | None = None
    value: int | None = None
    peak: int | None = None


@dataclass(frozen=True)
class TimbalCalibrationState:
    source: str
    timestamp: float
    min_hit: int | None = None
    quiet: int | None = None
    presence_noise: int | None = None
    refractory: int | None = None
    keep_connected: int | None = None


class TimbalInputRouter(QObject):
    hit_received = pyqtSignal(object)
    mute_received = pyqtSignal(object)
    pad_state_received = pyqtSignal(object)
    calibration_state_received = pyqtSignal(object)
    midi_message_received = pyqtSignal(object)
    status_changed = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        *,
        serial_baud: int = DEFAULT_SERIAL_BAUD,
        prefer_midi_hits: bool = DEFAULT_PREFER_MIDI_HITS,
    ) -> None:
        super().__init__(parent)
        self.serial_baud = serial_baud
        self.prefer_midi_hits = prefer_midi_hits
        self.midi_port = None
        self.serial_port = None
        self.serial_thread = None
        self.selected_midi_name: str | None = None
        self.selected_serial_name: str | None = None
        self._midi_active = False
        self._serial_buf = b""
        self._stop_event = threading.Event()
        self._dedupe_lock = threading.Lock()
        self._serial_write_lock = threading.Lock()
        self._last_hit_signature: str | None = None
        self._last_hit_source: str | None = None
        self._last_hit_timestamp: float = 0.0

    def start(self) -> None:
        self._open_midi()
        self._open_serial()

    def close(self) -> None:
        self._stop_event.set()
        if self.midi_port is not None:
            try:
                self.midi_port.close()
            except Exception:
                pass
            self.midi_port = None
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None
        if self.serial_thread is not None and self.serial_thread.is_alive():
            self.serial_thread.join(timeout=0.3)
        self.serial_thread = None

    def send_serial_json(self, payload: dict) -> bool:
        if self.serial_port is None:
            return False
        try:
            raw = (json.dumps(payload, ensure_ascii=True) + "\n").encode("ascii")
            with self._serial_write_lock:
                self.serial_port.write(raw)
                self.serial_port.flush()
            return True
        except Exception as exc:
            self._emit_status(f"WARN: No se pudo escribir serial: {exc}")
            return False

    def request_calibration_state(self) -> bool:
        return self.send_serial_json({"REQ": "CFG"})

    def send_calibration_config(self, config: dict) -> bool:
        return self.send_serial_json({"CFG": config})

    def _emit_status(self, text: str) -> None:
        self.status_changed.emit(text)

    def _score_midi_name(self, name: str) -> int:
        lowered = name.lower()
        score = 0
        for keyword in PREFERRED_MIDI_KEYWORDS:
            if keyword in lowered:
                score += 100
        for keyword in LOW_PRIORITY_MIDI_KEYWORDS:
            if keyword in lowered:
                score -= 100
        return score

    def _open_midi(self) -> None:
        try:
            inputs = list(mido.get_input_names())
        except Exception as exc:
            self._emit_status(f"WARN: No se pudieron listar puertos MIDI: {exc}")
            return

        if not inputs:
            self._emit_status("WARN: No hay puertos MIDI disponibles.")
            return

        ordered = sorted(inputs, key=self._score_midi_name, reverse=True)
        self.selected_midi_name = ordered[0]
        self._emit_status(f"INFO: Puertos MIDI detectados: {inputs}")
        try:
            self.midi_port = mido.open_input(
                self.selected_midi_name,
                callback=self._on_midi_message,
            )
            self._midi_active = True
            self._emit_status(f"INFO: Escuchando MIDI en {self.selected_midi_name}")
        except Exception as exc:
            self._emit_status(
                f"WARN: No se pudo abrir MIDI {self.selected_midi_name}: {exc}"
            )
            self.midi_port = None
            self._midi_active = False

    def _open_serial(self) -> None:
        if serial is None:
            self._emit_status("WARN: pyserial no disponible; se omite serial.")
            return
        ports = list_serial_ports()
        if not ports:
            self._emit_status("INFO: No se detectaron puertos seriales.")
            return
        best = pick_best_serial_port()
        if best is None:
            self._emit_status("INFO: No se encontro un puerto serial con perfil Arduino.")
            return

        try:
            self.serial_port = serial.Serial(best.device, self.serial_baud, timeout=0.01)
            self.selected_serial_name = best.device
            self.serial_thread = threading.Thread(
                target=self._serial_loop,
                name="timbal-serial-loop",
                daemon=True,
            )
            self.serial_thread.start()
            self._emit_status(
                f"INFO: Escuchando serial en {best.device} @ {self.serial_baud}"
            )
        except Exception as exc:
            self._emit_status(f"WARN: No se pudo abrir serial {best.device}: {exc}")
            self.serial_port = None

    def _signature_for_hit(self, hit: TimbalHit) -> str:
        if hit.pad_idx is not None:
            return f"pad:{hit.pad_idx}"
        if hit.note is not None:
            return f"note:{hit.note}"
        return f"vel:{hit.velocity}"

    def _is_duplicate_hit(self, hit: TimbalHit) -> bool:
        signature = self._signature_for_hit(hit)
        with self._dedupe_lock:
            is_duplicate = (
                self._last_hit_signature == signature
                and self._last_hit_source != hit.source
                and (hit.timestamp - self._last_hit_timestamp) <= DEDUP_WINDOW_SECONDS
            )
            if not is_duplicate:
                self._last_hit_signature = signature
                self._last_hit_source = hit.source
                self._last_hit_timestamp = hit.timestamp
            return is_duplicate

    def _on_midi_message(self, message) -> None:
        typ = getattr(message, "type", "")
        velocity = int(getattr(message, "velocity", 0) or 0)
        note = _safe_int(getattr(message, "note", None))
        now = time.perf_counter()

        if typ == "note_on" and velocity > 0:
            if self.serial_port is not None and not self.prefer_midi_hits:
                return
            hit = TimbalHit(
                source="midi",
                timestamp=now,
                note=note,
                velocity=velocity,
            )
            if not self._is_duplicate_hit(hit):
                self.hit_received.emit(hit)
            return

        self.midi_message_received.emit(message)

    def _serial_loop(self) -> None:
        while not self._stop_event.is_set() and self.serial_port is not None:
            try:
                waiting = self.serial_port.in_waiting
                chunk = self.serial_port.read(waiting or 1)
            except Exception as exc:
                self._emit_status(f"WARN: Serial detenido: {exc}")
                break

            if not chunk:
                continue

            self._serial_buf += chunk
            if b"\n" not in self._serial_buf:
                continue

            parts = self._serial_buf.split(b"\n")
            self._serial_buf = parts[-1]
            for raw in parts[:-1]:
                line = raw.decode(errors="ignore").strip()
                if not line:
                    continue
                self._handle_serial_line(line)

    def _handle_serial_line(self, line: str) -> None:
        try:
            data = json.loads(line)
        except Exception:
            return
        if not isinstance(data, dict):
            return

        now = time.perf_counter()
        if "HIT" in data:
            if self._midi_active and self.prefer_midi_hits:
                return
            hit_data = data.get("HIT", {})
            hit = TimbalHit(
                source="serial",
                timestamp=now,
                note=_safe_int(hit_data.get("note")),
                velocity=_safe_int(hit_data.get("vel")) or 110,
                pad_idx=_safe_int(hit_data.get("ch")),
            )
            if not self._is_duplicate_hit(hit):
                self.hit_received.emit(hit)

        if "MUTE" in data:
            mute_data = data.get("MUTE", {})
            mute = TimbalMute(
                source="serial",
                timestamp=now,
                pad_idx=_safe_int(mute_data.get("ch")),
                note=_safe_int(mute_data.get("note")),
                state=_safe_int(mute_data.get("state")) or 0,
            )
            self.mute_received.emit(mute)

        if "PADSTATE" in data:
            state_data = data.get("PADSTATE", {})
            pad_idx = _safe_int(state_data.get("ch"))
            if pad_idx is None:
                return

            raw_connected = state_data.get("conn")
            if raw_connected is None:
                connected = None
            else:
                connected = bool(_safe_int(raw_connected) if not isinstance(raw_connected, bool) else raw_connected)

            state = TimbalPadState(
                source="serial",
                timestamp=now,
                pad_idx=pad_idx,
                connected=connected,
                noise=_safe_int(state_data.get("noise")),
                value=_safe_int(state_data.get("value")),
                peak=_safe_int(state_data.get("peak")),
            )
            self.pad_state_received.emit(state)

        if "CFGSTATE" in data:
            cfg_data = data.get("CFGSTATE", {})
            cfg = TimbalCalibrationState(
                source="serial",
                timestamp=now,
                min_hit=_safe_int(cfg_data.get("min_hit")),
                quiet=_safe_int(cfg_data.get("quiet")),
                presence_noise=_safe_int(cfg_data.get("presence_noise")),
                refractory=_safe_int(cfg_data.get("refractory")),
                keep_connected=_safe_int(cfg_data.get("keep_connected")),
            )
            self.calibration_state_received.emit(cfg)
