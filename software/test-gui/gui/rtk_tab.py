

import time

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import config
from gui import theme
from gui.rtk_worker import RTKWorker
from sensors.nmea import FIX_QUALITY_NAMES, gga_fix_quality

PANEL_WIDTH = 400
STATS_INTERVAL_MS = 1000

SETTINGS_KEYS = ("caster", "port", "mountpoint", "username")

FIX_QUALITY_COLORS = {0: theme.DANGER, 4: theme.SUCCESS, 5: theme.WARNING}


class RTKTab(QWidget):
    _connect_requested = Signal(str, int, str, str, str)
    _disconnect_requested = Signal()
    _stop_requested = Signal()

    def __init__(self, gps_worker, parent=None):
        super().__init__(parent)

        self._gps_worker = gps_worker
        self._settings = QSettings("OrinNav", "TestGUI")
        self._last_rate_sample = None
        self._build_ui()
        self._load_settings()

        self._thread = QThread(self)
        self._worker = RTKWorker(gps_worker)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.status_changed.connect(self._on_status)
        self._worker.error.connect(self._on_error)
        self._worker.connection_changed.connect(self._on_connection_changed)
        self._connect_requested.connect(self._worker.connect_caster)
        self._disconnect_requested.connect(self._worker.disconnect_caster)
        self._stop_requested.connect(self._worker.stop, Qt.BlockingQueuedConnection)
        self._thread.start()

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(STATS_INTERVAL_MS)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.status_label = theme.status_label("Not connected", "idle")
        layout.addWidget(self.status_label)

        panel = QWidget()
        panel.setFixedWidth(PANEL_WIDTH)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(4)

        caster_box = QGroupBox("NTRIP caster")
        form = QFormLayout(caster_box)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)
        self.caster_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        # arrows don't style well in the dark QSS and aren't useful for a port
        self.port_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.mountpoint_edit = QLineEdit()
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Not saved between runs")
        form.addRow("Caster", self.caster_edit)
        form.addRow("Port", self.port_spin)
        form.addRow("Mountpoint", self.mountpoint_edit)
        form.addRow("Username", self.username_edit)
        form.addRow("Password", self.password_edit)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 6, 0, 0)
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("primary")
        self.connect_button.clicked.connect(self._on_connect_clicked)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("danger")
        self.disconnect_button.clicked.connect(self._disconnect_requested.emit)
        self.disconnect_button.setEnabled(False)
        buttons.addWidget(self.connect_button)
        buttons.addWidget(self.disconnect_button)
        form.addRow(buttons)
        panel_layout.addWidget(caster_box)

        stream_box = QGroupBox("Corrections")
        stream_form = QFormLayout(stream_box)
        stream_form.setVerticalSpacing(6)
        stream_form.setLabelAlignment(Qt.AlignLeft)
        self.stream_fields = {}
        for name in ("Receiver fix", "Data received", "Rate", "Last data", "Positions sent"):
            value = theme.value_label()
            stream_form.addRow(name, value)
            self.stream_fields[name] = value
        panel_layout.addWidget(stream_box)
        panel_layout.addStretch(1)

        body = QHBoxLayout()
        body.addWidget(panel)
        body.addStretch(1)
        layout.addLayout(body, stretch=1)

    def _load_settings(self):
        defaults = {
            "caster": config.RTK_DEFAULT_CASTER,
            "port": config.RTK_DEFAULT_PORT,
            "mountpoint": config.RTK_DEFAULT_MOUNTPOINT,
            "username": "",
        }
        values = {key: self._settings.value(f"rtk/{key}", defaults[key]) for key in SETTINGS_KEYS}
        self.caster_edit.setText(str(values["caster"]))
        self.port_spin.setValue(int(values["port"]))
        self.mountpoint_edit.setText(str(values["mountpoint"]))
        self.username_edit.setText(str(values["username"]))

    def _save_settings(self, caster, port, mountpoint, username):
        for key, value in zip(SETTINGS_KEYS, (caster, port, mountpoint, username)):
            self._settings.setValue(f"rtk/{key}", value)

    def _on_connect_clicked(self):
        caster = self.caster_edit.text().strip()
        port = self.port_spin.value()
        mountpoint = self.mountpoint_edit.text().strip().lstrip("/")
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not caster or not mountpoint:
            self._on_error("Caster and mountpoint are required")
            return

        self._save_settings(caster, port, mountpoint, username)
        self._set_inputs_enabled(False)
        self.connect_button.setEnabled(False)
        self._last_rate_sample = None
        self._connect_requested.emit(caster, port, mountpoint, username, password)

    def _on_connection_changed(self, connected):
        self._set_inputs_enabled(not connected)
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)

    def _set_inputs_enabled(self, enabled):
        for widget in (
            self.caster_edit,
            self.port_spin,
            self.mountpoint_edit,
            self.username_edit,
            self.password_edit,
        ):
            widget.setEnabled(enabled)

    def _on_status(self, text):
        theme.set_status(self.status_label, text, "ok" if text.startswith("Receiving") else "pending")

    def _on_error(self, text):
        theme.set_status(self.status_label, text, "error")

    def _update_stats(self):
        quality = gga_fix_quality(self._gps_worker.latest_gga())
        fix_label = self.stream_fields["Receiver fix"]
        fix_label.setText(
            "--" if quality is None else FIX_QUALITY_NAMES.get(quality, f"Unknown ({quality})")
        )
        fix_style = (
            f"color: {FIX_QUALITY_COLORS[quality]}; font-weight: bold;"
            if quality in FIX_QUALITY_COLORS
            else ""
        )
        # setStyleSheet re-polishes, only do it on change
        if fix_label.styleSheet() != fix_style:
            fix_label.setStyleSheet(fix_style)

        stats = self._worker.stats()
        now = time.monotonic()
        self.stream_fields["Data received"].setText(self._format_bytes(stats["bytes"]))
        self.stream_fields["Positions sent"].setText(str(stats["gga_sent"]))

        if stats["last_data_time"] is None:
            self.stream_fields["Last data"].setText("--")
        else:
            self.stream_fields["Last data"].setText(f"{now - stats['last_data_time']:.0f} s ago")

        if not stats["connected"]:
            self.stream_fields["Rate"].setText("--")
            self._last_rate_sample = None
            return
        if self._last_rate_sample is not None:
            prev_time, prev_bytes = self._last_rate_sample
            rate = (stats["bytes"] - prev_bytes) / max(now - prev_time, 1e-3)
            self.stream_fields["Rate"].setText(f"{rate:.0f} B/s")
        self._last_rate_sample = (now, stats["bytes"])

    @staticmethod
    def _format_bytes(count):
        if count < 1024:
            return f"{count} B"
        if count < 1024 * 1024:
            return f"{count / 1024:.1f} KB"
        return f"{count / (1024 * 1024):.2f} MB"

    def shutdown(self):
        self._stats_timer.stop()
        self._stop_requested.emit()
        self._thread.quit()
        self._thread.wait(2000)
