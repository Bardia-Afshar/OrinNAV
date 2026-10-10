

import base64
import socket
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

import config
from sensors.nmea import gga_fix_quality

RECV_CHUNK = 4096
MAX_HEADER_BYTES = 8192

# corrections come ~1/s, so this long with nothing means the stream stalled
DATA_TIMEOUT_S = 10.0


class NTRIPError(Exception):
    pass


class RTKWorker(QObject):
    status_changed = Signal(str)
    error = Signal(str)
    connection_changed = Signal(bool)

    def __init__(self, gps_worker):
        super().__init__()
        self._gps = gps_worker
        self._sock = None
        self._timer = None
        self._lock = threading.Lock()
        self._last_status = None
        self._reset_stats()

    def start(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)

    @Slot(str, int, str, str, str)
    def connect_caster(self, host, port, mountpoint, username, password):
        self._close()
        self._reset_stats()
        self._last_status = None
        self._emit_status(f"Connecting to {host}:{port}/{mountpoint}...")

        sock = None
        try:
            sock = socket.create_connection((host, port), timeout=config.RTK_CONNECT_TIMEOUT_S)
            sock.sendall(self._request(host, port, mountpoint, username, password))
            leftover = self._read_response(sock, mountpoint)
        except (OSError, NTRIPError) as exc:
            if sock is not None:
                sock.close()
            msg = str(exc) if isinstance(exc, NTRIPError) else f"Connection to {host}:{port} failed: {exc}"
            self._fail(msg)
            return

        sock.setblocking(False)
        self._sock = sock
        with self._lock:
            self._stats["connected"] = True
        self.connection_changed.emit(True)
        if leftover:
            self._forward(leftover)
        self._timer.start(config.RTK_POLL_INTERVAL_MS)
        self._poll()

    @Slot()
    def disconnect_caster(self):
        self._close()
        self.connection_changed.emit(False)
        self._emit_status("Disconnected")

    @staticmethod
    def _request(host, port, mountpoint, username, password):
        # v1: every caster takes it and the body is raw RTCM (v2 may be chunked)
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        return (
            f"GET /{mountpoint} HTTP/1.0\r\n"
            f"Host: {host}:{port}\r\n"
            "User-Agent: NTRIP OrinNav/1.0\r\n"
            f"Authorization: Basic {credentials}\r\n"
            "\r\n"
        ).encode()

    @staticmethod
    def _read_response(sock, mountpoint):
        # returns any stream bytes that came in with the header
        buf = b""
        while b"\r\n" not in buf:
            chunk = sock.recv(RECV_CHUNK)
            if not chunk:
                raise NTRIPError("Caster closed the connection without replying")
            buf += chunk
            if len(buf) > MAX_HEADER_BYTES:
                raise NTRIPError("Caster sent an unrecognisable reply")
        status_line, rest = buf.split(b"\r\n", 1)
        status = status_line.decode("ascii", "replace").strip()

        if status.startswith("ICY 200"):
            if b"\r\n\r\n" in rest[:512]:
                rest = rest.split(b"\r\n\r\n", 1)[1]
            return rest.lstrip(b"\r\n")
        if status.startswith("SOURCETABLE"):
            raise NTRIPError(f"Mountpoint '{mountpoint}' not found (caster sent its source table)")
        if " 401" in status:
            raise NTRIPError("Caster rejected the username/password (401 Unauthorized)")
        if status.startswith("HTTP/") and " 200" in status:
            while b"\r\n\r\n" not in buf:
                chunk = sock.recv(RECV_CHUNK)
                if not chunk or len(buf) > MAX_HEADER_BYTES:
                    raise NTRIPError("Caster sent an incomplete reply header")
                buf += chunk
            header, body = buf.split(b"\r\n\r\n", 1)
            if b"chunked" in header.lower():
                raise NTRIPError("Chunked (NTRIP v2) stream not supported")
            return body
        raise NTRIPError(f"Caster refused the request: {status}")

    def _close(self):
        if self._timer is not None:
            self._timer.stop()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        with self._lock:
            self._stats["connected"] = False

    def _fail(self, message):
        self._close()
        self.connection_changed.emit(False)
        self.error.emit(message)

    def _poll(self):
        if self._sock is None:
            return
        try:
            while True:
                chunk = self._sock.recv(RECV_CHUNK)
                if not chunk:
                    self._fail("Caster closed the connection")
                    return
                self._forward(chunk)
        except BlockingIOError:
            pass
        except OSError as exc:
            self._fail(f"Connection to caster lost: {exc}")
            return

        now = time.monotonic()
        last_gga = self._stats["last_gga_time"]
        if last_gga is None or now - last_gga >= config.RTK_GGA_INTERVAL_S:
            try:
                self._send_gga(now)
            except OSError as exc:
                self._fail(f"Sending position to caster failed: {exc}")
                return

        self._emit_status(self._status_text(now))

    def _forward(self, data):
        self._gps.send_to_receiver(data)
        with self._lock:
            self._stats["bytes"] += len(data)
            self._stats["last_data_time"] = time.monotonic()

    def _send_gga(self, now):
        gga = self._gps.latest_gga()
        if not gga_fix_quality(gga):
            return
        self._sock.sendall((gga + "\r\n").encode("ascii"))
        with self._lock:
            self._stats["gga_sent"] += 1
            self._stats["last_gga_time"] = now

    def _status_text(self, now):
        stats = self._stats
        if stats["gga_sent"] == 0:
            return "Connected, waiting for a GPS fix to send our position to the caster"
        if stats["bytes"] == 0:
            return "Connected, position sent, waiting for corrections..."
        silent = now - stats["last_data_time"]
        if silent > DATA_TIMEOUT_S:
            return f"Corrections stalled: no data for {silent:.0f}s"
        return "Receiving corrections"

    def _reset_stats(self):
        with self._lock:
            self._stats = {
                "connected": False,
                "bytes": 0,
                "last_data_time": None,
                "gga_sent": 0,
                "last_gga_time": None,
            }

    def stats(self):
        with self._lock:
            return dict(self._stats)

    def _emit_status(self, text):
        if text != self._last_status:
            self._last_status = text
            self.status_changed.emit(text)

    def stop(self):
        self._close()
