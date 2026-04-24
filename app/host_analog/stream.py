"""Binary analog stream reader for the host-side experiment."""
from __future__ import annotations

import struct
import threading
import time
from collections import deque
from dataclasses import dataclass

from PyQt5.QtCore import QObject, pyqtSignal

from app.io.timbal_input import pick_best_serial_port, serial

PACKET_HEADER = 0xA1
PACKET_STRUCT = struct.Struct("<BBIH")
PACKET_SIZE = PACKET_STRUCT.size
DEFAULT_ANALOG_BAUD = 2_000_000


@dataclass(frozen=True)
class AnalogSample:
    channel: int
    device_us: int
    value: int
    host_time: float


@dataclass(frozen=True)
class AnalogHit:
    channel: int
    value: int
    device_us: int
    host_time: float
    lag_ms: float | None


class HostAnalogDetector:
    def __init__(self, *, threshold: int = 80, delta: int = 25, refractory_ms: int = 70):
        self.threshold = threshold
        self.delta = delta
        self.refractory_ms = refractory_ms
        self.prev_value: dict[int, int] = {}
        self.last_hit_host_time: dict[int, float] = {}
        self.anchors: dict[int, tuple[int, float]] = {}

    def update_params(self, *, threshold: int, delta: int, refractory_ms: int) -> None:
        self.threshold = int(threshold)
        self.delta = int(delta)
        self.refractory_ms = int(refractory_ms)

    def as_dict(self) -> dict[str, int]:
        return {
            "hit_threshold": int(self.threshold),
            "delta_threshold": int(self.delta),
            "refractory_ms": int(self.refractory_ms),
        }

    def process_sample(self, sample: AnalogSample) -> AnalogHit | None:
        channel = sample.channel
        prev = self.prev_value.get(channel, sample.value)
        self.prev_value[channel] = sample.value

        anchor = self.anchors.get(channel)
        if anchor is None:
            self.anchors[channel] = (sample.device_us, sample.host_time)
            anchor = self.anchors[channel]

        last_hit = self.last_hit_host_time.get(channel, 0.0)
        if (sample.host_time - last_hit) * 1000.0 < self.refractory_ms:
            return None

        slope = sample.value - prev
        if sample.value < self.threshold or slope < self.delta:
            return None

        self.last_hit_host_time[channel] = sample.host_time
        base_device_us, base_host_time = anchor
        device_elapsed = (sample.device_us - base_device_us) / 1_000_000.0
        host_elapsed = sample.host_time - base_host_time
        lag_ms = max(0.0, (host_elapsed - device_elapsed) * 1000.0)
        return AnalogHit(
            channel=channel,
            value=sample.value,
            device_us=sample.device_us,
            host_time=sample.host_time,
            lag_ms=lag_ms,
        )


class AnalogStreamReader(QObject):
    status_changed = pyqtSignal(str)
    samples_received = pyqtSignal(object)
    hit_detected = pyqtSignal(object)

    def __init__(self, parent=None, *, baud_rate: int = DEFAULT_ANALOG_BAUD) -> None:
        super().__init__(parent)
        self.baud_rate = baud_rate
        self.serial_port = None
        self.serial_info = None
        self.reader_thread = None
        self._stop_event = threading.Event()
        self._buffer = bytearray()
        self._detector = HostAnalogDetector()
        self._pending_samples = deque()
        self._last_emit_time = 0.0

    def configure_detector(self, *, threshold: int, delta: int, refractory_ms: int) -> None:
        self._detector.update_params(
            threshold=threshold,
            delta=delta,
            refractory_ms=refractory_ms,
        )

    def detector_config(self) -> dict[str, int]:
        return self._detector.as_dict()

    def start(self) -> None:
        if self.reader_thread is not None and self.reader_thread.is_alive():
            return
        self._stop_event.clear()
        self._buffer.clear()
        self._pending_samples.clear()
        self._last_emit_time = 0.0
        if serial is None:
            self.status_changed.emit("WARN: pyserial no disponible.")
            return
        port_info = pick_best_serial_port()
        if port_info is None:
            self.status_changed.emit("WARN: No se encontró un Arduino serial para el experimento.")
            return
        try:
            self.serial_port = serial.Serial(port_info.device, self.baud_rate, timeout=0.02)
        except Exception as exc:
            self.status_changed.emit(f"WARN: No se pudo abrir {port_info.device}: {exc}")
            return
        self.serial_info = port_info
        self.status_changed.emit(
            f"INFO: Analog stream en {port_info.device} @ {self.baud_rate}"
        )
        self.reader_thread = threading.Thread(
            target=self._reader_loop,
            name="host-analog-reader",
            daemon=True,
        )
        self.reader_thread.start()

    def close(self) -> None:
        self._stop_event.set()
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None
        if self.reader_thread is not None and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=0.3)
        self.reader_thread = None

    def _emit_pending_samples(self, *, force: bool = False) -> None:
        if not self._pending_samples:
            return
        now = time.perf_counter()
        if not force and len(self._pending_samples) < 24 and (now - self._last_emit_time) < 0.025:
            return
        batch = list(self._pending_samples)
        self._pending_samples.clear()
        self._last_emit_time = now
        self.samples_received.emit(batch)

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set() and self.serial_port is not None:
            try:
                chunk = self.serial_port.read(self.serial_port.in_waiting or PACKET_SIZE)
            except Exception as exc:
                self.status_changed.emit(f"WARN: Stream analógico detenido: {exc}")
                break

            if not chunk:
                self._emit_pending_samples()
                continue

            self._buffer.extend(chunk)
            self._parse_buffer()
            self._emit_pending_samples()

        self._emit_pending_samples(force=True)

    def _parse_buffer(self) -> None:
        while len(self._buffer) >= PACKET_SIZE:
            if self._buffer[0] != PACKET_HEADER:
                try:
                    next_header = self._buffer.index(PACKET_HEADER)
                    del self._buffer[:next_header]
                except ValueError:
                    self._buffer.clear()
                    return
                if len(self._buffer) < PACKET_SIZE:
                    return

            header, channel, device_us, value = PACKET_STRUCT.unpack(
                self._buffer[:PACKET_SIZE]
            )
            del self._buffer[:PACKET_SIZE]
            if header != PACKET_HEADER:
                continue

            sample = AnalogSample(
                channel=int(channel),
                device_us=int(device_us),
                value=int(value),
                host_time=time.perf_counter(),
            )
            self._pending_samples.append(sample)
            hit = self._detector.process_sample(sample)
            if hit is not None:
                self.hit_detected.emit(hit)
