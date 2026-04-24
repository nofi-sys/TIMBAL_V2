"""Reusable analog acquisition source for the timbal lab."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt5.QtCore import QObject, pyqtSignal

from app.host_analog.stream import AnalogStreamReader
from app.io.timbal_input import pick_best_serial_port, serial


@dataclass(frozen=True)
class SourceAvailability:
    available: bool
    detail: str
    port_name: str | None = None


class AnalogRawSource(QObject):
    """Thin wrapper around the existing host-side analog experiment reader."""

    availability_changed = pyqtSignal(object)
    status_changed = pyqtSignal(str)
    samples_received = pyqtSignal(object)
    hit_detected = pyqtSignal(object)
    running_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.reader = AnalogStreamReader(self)
        self._running = False

        self.reader.status_changed.connect(self._on_reader_status)
        self.reader.samples_received.connect(self.samples_received)
        self.reader.hit_detected.connect(self.hit_detected)

    @property
    def source_name(self) -> str:
        return "analog_raw"

    def is_running(self) -> bool:
        return self._running

    def refresh_availability(self) -> SourceAvailability:
        if serial is None:
            info = SourceAvailability(
                available=False,
                detail="pyserial no disponible",
                port_name=None,
            )
        else:
            port_info = pick_best_serial_port()
            if port_info is None:
                info = SourceAvailability(
                    available=False,
                    detail="No se detecto un Arduino serial compatible",
                    port_name=None,
                )
            else:
                info = SourceAvailability(
                    available=True,
                    detail=f"Puerto listo: {port_info.device}",
                    port_name=port_info.device,
                )

        self.availability_changed.emit(info)
        return info

    def configure_detector(
        self,
        *,
        threshold: int | None = None,
        delta: int | None = None,
        refractory_ms: int | None = None,
    ) -> dict[str, int]:
        current = self.reader.detector_config()
        next_threshold = current["hit_threshold"] if threshold is None else int(threshold)
        next_delta = current["delta_threshold"] if delta is None else int(delta)
        next_refractory = current["refractory_ms"] if refractory_ms is None else int(refractory_ms)
        self.reader.configure_detector(
            threshold=next_threshold,
            delta=next_delta,
            refractory_ms=next_refractory,
        )
        config = self.reader.detector_config()
        self.status_changed.emit(
            "INFO: Detector analogico"
            f" thr={config['hit_threshold']}"
            f" delta={config['delta_threshold']}"
            f" refr={config['refractory_ms']}ms"
        )
        return config

    def detector_config(self) -> dict[str, int]:
        return self.reader.detector_config()

    def start(self) -> bool:
        self.reader.start()
        self._set_running(self.reader.serial_port is not None)
        self.refresh_availability()
        return self._running

    def close(self) -> None:
        self.reader.close()
        self._set_running(False)
        self.refresh_availability()

    def _on_reader_status(self, text: str) -> None:
        self.status_changed.emit(text)
        if self.reader.serial_port is None:
            self._set_running(False)
        self.refresh_availability()

    def _set_running(self, running: bool) -> None:
        running = bool(running)
        if self._running == running:
            return
        self._running = running
        self.running_changed.emit(self._running)
