from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import config
from gui import theme
from gui.gps_worker import GPSWorker
from gui.satellite_map_view import SatelliteMapView

PANEL_WIDTH = 340
FIX_ZOOM = 17

# C/N0 dB-Hz: <20 barely there, 40+ clean open sky
SNR_STRONG = 40.0
SNR_OK = 30.0
SNR_WEAK = 20.0

SATELLITE_COLUMNS = ["PRN", "System", "Elev°", "Azim°", "C/N0", "Used"]


def _snr_band(snr):
    if snr is None or snr <= 0:
        return "poor"
    if snr >= SNR_STRONG:
        return "strong"
    if snr >= SNR_OK:
        return "ok"
    if snr >= SNR_WEAK:
        return "weak"
    return "poor"


class GPSTab(QWidget):
    # same as IMUTab._stop_requested
    _stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._centred_once = False
        self._build_ui()

        self._thread = QThread(self)
        self._worker = GPSWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.status_changed.connect(self._on_status)
        self._worker.error.connect(self._on_error)
        self._stop_requested.connect(self._worker.stop, Qt.BlockingQueuedConnection)
        self._thread.start()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_latest)
        self._poll_timer.start(config.GPS_POLL_INTERVAL_MS)

    @property
    def worker(self):
        return self._worker

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.status_label = theme.status_label("Connecting to GPS...", "pending")
        layout.addWidget(self.status_label)

        self.map_view = SatelliteMapView()

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._build_panel(), stretch=0)
        body.addWidget(self.map_view, stretch=1)
        layout.addLayout(body, stretch=1)

    def _build_panel(self):
        panel = QWidget()
        panel.setFixedWidth(PANEL_WIDTH)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(4)

        self.fix_fields = self._add_group(
            panel_layout, "Fix", ["Quality", "Mode", "Satellites used", "Accuracy", "PDOP", "VDOP"]
        )
        self.signal_fields = self._add_group(
            panel_layout,
            "Signal",
            ["In view", "Tracked", "Mean C/N0", "Best C/N0"],
        )
        self.position_fields = self._add_group(
            panel_layout,
            "Position",
            ["Latitude", "Longitude", "Altitude", "Geoid sep.", "Speed", "Course", "UTC"],
        )

        self.follow_checkbox = QCheckBox("Centre map on fix")
        self.follow_checkbox.setChecked(True)
        panel_layout.addWidget(self.follow_checkbox)

        sat_box = QGroupBox("Satellites")
        sat_layout = QVBoxLayout(sat_box)
        sat_layout.setContentsMargins(0, 4, 0, 0)
        self.satellite_table = QTableWidget(0, len(SATELLITE_COLUMNS))
        self.satellite_table.setHorizontalHeaderLabels(SATELLITE_COLUMNS)
        self.satellite_table.verticalHeader().setVisible(False)
        self.satellite_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.satellite_table.setSelectionMode(QTableWidget.NoSelection)
        self.satellite_table.setAlternatingRowColors(True)
        self.satellite_table.setShowGrid(False)
        self.satellite_table.setFocusPolicy(Qt.NoFocus)
        self.satellite_table.verticalHeader().setDefaultSectionSize(24)
        header = self.satellite_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        sat_layout.addWidget(self.satellite_table)
        panel_layout.addWidget(sat_box, stretch=1)

        return panel

    @staticmethod
    def _add_group(parent_layout, title, field_names):
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setContentsMargins(4, 4, 4, 4)
        form.setVerticalSpacing(3)
        form.setLabelAlignment(Qt.AlignLeft)
        fields = {}
        for name in field_names:
            value = theme.value_label()
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(name, value)
            fields[name] = value
        parent_layout.addWidget(box)
        return fields

    def _poll_latest(self):
        latest = self._worker.take_latest()
        if latest is not None:
            state, link = latest
            self._update_readouts(state, link)

    def _on_status(self, text):
        theme.set_status(self.status_label, text, "ok" if text.startswith("Connected") else "pending")

    def _on_error(self, text):
        theme.set_status(self.status_label, text, "error")

    def _update_readouts(self, state, link):
        stale = link["stale"]

        self.fix_fields["Quality"].setText(state.fix_quality_text)
        self.fix_fields["Mode"].setText(state.fix_type_text)
        self.fix_fields["Satellites used"].setText(
            "--" if state.satellites_used is None else str(state.satellites_used)
        )
        self.fix_fields["Accuracy"].setText(state.accuracy_text)
        self.fix_fields["PDOP"].setText(self._num(state.pdop, 2))
        self.fix_fields["VDOP"].setText(self._num(state.vdop, 2))

        self.signal_fields["In view"].setText(str(state.satellites_in_view))
        self.signal_fields["Tracked"].setText(str(state.satellites_with_signal))
        self.signal_fields["Mean C/N0"].setText(self._num(state.snr_mean, 1, " dB-Hz"))
        self.signal_fields["Best C/N0"].setText(self._num(state.snr_max, 1, " dB-Hz"))

        self.position_fields["Latitude"].setText(self._num(state.latitude, 6, "°"))
        self.position_fields["Longitude"].setText(self._num(state.longitude, 6, "°"))
        self.position_fields["Altitude"].setText(self._num(state.altitude_m, 1, " m"))
        self.position_fields["Geoid sep."].setText(self._num(state.geoid_separation_m, 1, " m"))
        self.position_fields["Speed"].setText(self._num(state.speed_kmh, 2, " km/h"))
        self.position_fields["Course"].setText(self._num(state.course_deg, 1, "°"))
        timestamp = " ".join(x for x in (state.utc_date, state.utc_time) if x)
        self.position_fields["UTC"].setText(timestamp or "--")

        self._update_satellite_table(state.satellites)

        if state.latitude is not None and state.longitude is not None:
            self.map_view.set_marker(state.latitude, state.longitude)

        if state.has_fix and not stale and self.follow_checkbox.isChecked():
            # only zoom on the first fix so we don't fight the user's wheel
            zoom = None if self._centred_once else FIX_ZOOM
            self.map_view.set_center(state.latitude, state.longitude, zoom)
            self._centred_once = True

    def _update_satellite_table(self, satellites):
        table = self.satellite_table
        table.setRowCount(len(satellites))
        for row, sat in enumerate(satellites):
            band = _snr_band(sat.snr)
            values = [
                str(sat.prn),
                sat.constellation,
                self._num(sat.elevation, 0),
                self._num(sat.azimuth, 0),
                "--" if not sat.snr else f"{sat.snr:.0f}",
                "●" if sat.used else "",
            ]
            for col, text in enumerate(values):
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, col, item)
                item.setText(text)
                if col == 4:
                    item.setForeground(theme.SNR_COLORS[band])
                elif col == 5:
                    item.setForeground(theme.SNR_COLORS["strong"])

    @staticmethod
    def _num(value, decimals, suffix=""):
        if value is None:
            return "--"
        return f"{value:.{decimals}f}{suffix}"

    def shutdown(self):
        self._poll_timer.stop()
        self._stop_requested.emit()
        self._thread.quit()
        self._thread.wait(2000)
