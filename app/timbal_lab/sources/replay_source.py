"""Replay source for previously recorded timbal lab sessions."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from app.host_analog.stream import AnalogHit, AnalogSample
from app.timbal_lab.eval.session_loader import SessionData, load_session_dir
from app.timbal_lab.sources.analog_raw_source import SourceAvailability


@dataclass(frozen=True)
class ReplaySession:
    session_dir: Path
    manifest: dict[str, object]
    samples: list[AnalogSample]
    hits: list[AnalogHit]


class ReplaySource(QObject):
    availability_changed = pyqtSignal(object)
    status_changed = pyqtSignal(str)
    samples_received = pyqtSignal(object)
    hit_detected = pyqtSignal(object)
    running_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._session: ReplaySession | None = None
        self._sample_index = 0
        self._hit_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._tick)
        self.chunk_size = 48

    @property
    def source_name(self) -> str:
        return "replay"

    def is_running(self) -> bool:
        return self._running

    def current_session_dir(self) -> Path | None:
        return None if self._session is None else self._session.session_dir

    def refresh_availability(self) -> SourceAvailability:
        if self._session is None:
            info = SourceAvailability(
                available=False,
                detail="No hay sesion cargada para replay",
                port_name=None,
            )
        else:
            info = SourceAvailability(
                available=True,
                detail=f"Replay listo: {self._session.session_dir.name}",
                port_name=self._session.session_dir.name,
            )
        self.availability_changed.emit(info)
        return info

    def load_session(self, session_dir: Path) -> bool:
        try:
            loaded: SessionData = load_session_dir(session_dir)
        except Exception as exc:
            self.status_changed.emit(f"WARN: No se pudo cargar replay: {exc}")
            return False

        self._session = ReplaySession(
            session_dir=session_dir,
            manifest=loaded.manifest,
            samples=loaded.samples,
            hits=loaded.hits,
        )
        self._sample_index = 0
        self._hit_index = 0
        self.status_changed.emit(
            f"INFO: Replay cargado {session_dir.name} | samples={len(loaded.samples)} hits={len(loaded.hits)}"
        )
        self.refresh_availability()
        return True

    def start(self) -> bool:
        if self._session is None:
            self.status_changed.emit("WARN: No hay sesion cargada para replay.")
            return False
        if self._running:
            return True
        self._sample_index = 0
        self._hit_index = 0
        self._set_running(True)
        self.status_changed.emit(f"INFO: Replay iniciado {self._session.session_dir.name}")
        self._timer.start()
        return True

    def close(self) -> None:
        self._timer.stop()
        self._set_running(False)

    def _tick(self) -> None:
        if self._session is None:
            self.close()
            return
        if self._sample_index >= len(self._session.samples):
            self.status_changed.emit(f"INFO: Replay finalizado {self._session.session_dir.name}")
            self.close()
            return

        batch = self._session.samples[self._sample_index : self._sample_index + self.chunk_size]
        self._sample_index += len(batch)
        self.samples_received.emit(batch)

        last_device_us = batch[-1].device_us if batch else -1
        while self._hit_index < len(self._session.hits):
            hit = self._session.hits[self._hit_index]
            if hit.device_us > last_device_us:
                break
            self.hit_detected.emit(hit)
            self._hit_index += 1

    def _set_running(self, running: bool) -> None:
        running = bool(running)
        if self._running == running:
            return
        self._running = running
        self.running_changed.emit(self._running)
