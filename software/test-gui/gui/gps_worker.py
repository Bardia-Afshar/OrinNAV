

import threading
import time

import serial
from PySide6.QtCore import QObject, QTimer, Signal

import config
from sensors.nmea import NMEAParser

# receiver sends a batch per second, so several missed means the link is down
LINK_TIMEOUT_S = 5.0

# RTCM is a few KB/s; if this much backs up the port isn't draining and the
# data is stale anyway
MAX_OUTBOUND_BYTES = 64 * 1024


class GPSWorker(QObject):
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._serial = None
        self._timer = None
        self._parser = NMEAParser()
        self._lock = threading.Lock()
        self._latest = None
        self._buffer = b""
        self._bytes_total = 0
        self._last_valid_time = None
        self._last_status = None
        self._outbound = bytearray()
        self._last_gga = None

    def start(self):
        try:
            self._serial = serial.Serial(
                config.GPS_PORT,
                config.GPS_BAUD,
                timeout=0,
            )
        except Exception as exc:
            self.error.emit(f"GPS open failed ({config.GPS_PORT}): {exc}")
            return

        self._emit_status(f"Opened {config.GPS_PORT} @ {config.GPS_BAUD}, waiting for data...")

        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(config.GPS_POLL_INTERVAL_MS)

    def _poll(self):
        with self._lock:
            pending, self._outbound = bytes(self._outbound), bytearray()
        try:
            if pending:
                self._serial.write(pending)
            waiting = self._serial.in_waiting
            chunk = self._serial.read(waiting) if waiting else b""
        except Exception as exc:
            if self._timer is not None:
                self._timer.stop()
            self.error.emit(f"GPS serial I/O failed: {exc}")
            return

        if chunk:
            self._bytes_total += len(chunk)
            self._buffer += chunk
            # max sentence is 82 bytes; a line this long is garbage
            if len(self._buffer) > 4096:
                self._buffer = self._buffer[-512:]
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                text = line.decode("ascii", "replace").strip()
                if text and self._parser.feed(text):
                    self._last_valid_time = time.monotonic()
                    if text[3:6] == "GGA":
                        with self._lock:
                            self._last_gga = text

        snapshot = self._parser.snapshot()
        with self._lock:
            self._latest = (snapshot, self._link_info())
        self._emit_status(self._status_text())

    def _link_info(self):
        age = None
        if self._last_valid_time is not None:
            age = time.monotonic() - self._last_valid_time
        return {
            "port": config.GPS_PORT,
            "baud": config.GPS_BAUD,
            "bytes": self._bytes_total,
            "sentences": self._parser.sentences_parsed,
            "checksum_failures": self._parser.checksum_failures,
            "seconds_since_valid": age,
            "stale": age is None or age > LINK_TIMEOUT_S,
        }

    def _status_text(self):
        info = self._link_info()
        if info["bytes"] == 0:
            return f"No data on {info['port']} @ {info['baud']}. Check wiring and power"
        if info["sentences"] == 0:
            return (
                f"Receiving bytes on {info['port']} but no valid NMEA "
                f"({info['bytes']} B, {info['checksum_failures']} bad checksums). "
                f"Check baud rate ({info['baud']}) and RX wiring"
            )
        if info["stale"]:
            return f"NMEA stopped, last valid sentence {info['seconds_since_valid']:.0f}s ago"
        return f"Connected: {info['sentences']} sentences, {info['checksum_failures']} bad checksums"

    def _emit_status(self, text):
        if text != self._last_status:
            self._last_status = text
            self.status_changed.emit(text)

    def take_latest(self):
        with self._lock:
            latest, self._latest = self._latest, None
        return latest

    def send_to_receiver(self, data):
        # any thread; the actual write happens in _poll
        with self._lock:
            if len(self._outbound) + len(data) > MAX_OUTBOUND_BYTES:
                self._outbound.clear()
            self._outbound += data

    def latest_gga(self):
        with self._lock:
            return self._last_gga

    def stop(self):
        if self._timer is not None:
            self._timer.stop()
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
