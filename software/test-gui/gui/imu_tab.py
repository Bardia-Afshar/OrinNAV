import time
from collections import deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

import config
from gui import theme
from gui.imu_worker import IMUWorker

PLOT_HISTORY_SAMPLES = 500

# sampling is 50 Hz but the Jetson can't redraw two plots that often
RENDER_INTERVAL_S = 1.0 / 30.0


class IMUTab(QWidget):
    # blocking-queued so stop() runs on the worker's thread
    _stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._start_time = time.monotonic()
        self._last_render_time = 0.0
        self._time_history = deque(maxlen=PLOT_HISTORY_SAMPLES)
        self._accel_history = {axis: deque(maxlen=PLOT_HISTORY_SAMPLES) for axis in "XYZ"}
        self._gyro_history = {axis: deque(maxlen=PLOT_HISTORY_SAMPLES) for axis in "XYZ"}

        self._build_ui()

        self._thread = QThread(self)
        self._worker = IMUWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.status_changed.connect(self._on_status)
        self._worker.error.connect(self._on_error)
        self._stop_requested.connect(self._worker.stop, Qt.BlockingQueuedConnection)
        self._thread.start()

        # see IMUWorker.take_latest()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_latest_reading)
        self._poll_timer.start(config.POLL_INTERVAL_MS)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.status_label = theme.status_label("Connecting to IMU...", "pending")
        layout.addWidget(self.status_label)

        self.accel_plot, self.accel_curves = self._build_plot("Acceleration", "g")
        self.gyro_plot, self.gyro_curves = self._build_plot("Gyroscope", "dps")

        cards = QHBoxLayout()
        cards.setSpacing(12)
        accel_card, self.accel_labels = self._build_card("Acceleration · g", self.accel_plot)
        gyro_card, self.gyro_labels = self._build_card("Gyroscope · dps", self.gyro_plot)
        cards.addWidget(accel_card, stretch=1)
        cards.addWidget(gyro_card, stretch=1)
        layout.addLayout(cards, stretch=1)

    @staticmethod
    def _build_card(title, plot):
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(10)

        readouts = QHBoxLayout()
        labels = {}
        for axis in "XYZ":
            tag = QLabel(axis)
            tag.setObjectName("axisTag")
            tag.setStyleSheet(f"color: {theme.AXIS_COLORS[axis]};")
            label = theme.value_label(big=True)
            readouts.addWidget(tag)
            readouts.addWidget(label, stretch=1)
            labels[axis] = label
        box_layout.addLayout(readouts)
        box_layout.addWidget(plot, stretch=1)
        return box, labels

    @staticmethod
    def _build_plot(title, unit):
        plot = pg.PlotWidget()
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.setLabel("bottom", "Time", units="s")
        plot.setLabel("left", title, units=unit)
        plot.addLegend(offset=(-10, 10))
        plot.enableAutoRange(x=False, y=False)
        curves = {
            axis: plot.plot(pen=pg.mkPen(theme.AXIS_COLORS[axis], width=2), name=axis)
            for axis in "XYZ"
        }
        return plot, curves

    @staticmethod
    def _update_plot_range(plot, time_array, value_arrays):
        if len(time_array) == 0:
            return
        plot.setXRange(time_array[0], time_array[-1], padding=0)
        combined = np.concatenate(list(value_arrays.values()))
        lo, hi = float(combined.min()), float(combined.max())
        pad = max((hi - lo) * 0.1, 0.05)
        plot.setYRange(lo - pad, hi + pad, padding=0)

    def _poll_latest_reading(self):
        reading = self._worker.take_latest()
        if reading is not None:
            self._on_reading(reading)

    def _on_status(self, text):
        theme.set_status(self.status_label, text, "ok")

    def _on_error(self, text):
        theme.set_status(self.status_label, text, "error")

    def _on_reading(self, reading):
        ax, ay, az = reading["accel"]
        gx, gy, gz = reading["gyro"]
        self.accel_labels["X"].setText(f"{ax:+.3f}")
        self.accel_labels["Y"].setText(f"{ay:+.3f}")
        self.accel_labels["Z"].setText(f"{az:+.3f}")
        self.gyro_labels["X"].setText(f"{gx:+.2f}")
        self.gyro_labels["Y"].setText(f"{gy:+.2f}")
        self.gyro_labels["Z"].setText(f"{gz:+.2f}")

        now = time.monotonic()
        self._time_history.append(now - self._start_time)
        for axis, value in zip("XYZ", (ax, ay, az)):
            self._accel_history[axis].append(value)
        for axis, value in zip("XYZ", (gx, gy, gz)):
            self._gyro_history[axis].append(value)

        if now - self._last_render_time < RENDER_INTERVAL_S:
            return
        self._last_render_time = now

        time_array = np.fromiter(self._time_history, dtype=float)
        accel_arrays = {axis: np.fromiter(self._accel_history[axis], dtype=float) for axis in "XYZ"}
        gyro_arrays = {axis: np.fromiter(self._gyro_history[axis], dtype=float) for axis in "XYZ"}
        for axis in "XYZ":
            self.accel_curves[axis].setData(time_array, accel_arrays[axis])
            self.gyro_curves[axis].setData(time_array, gyro_arrays[axis])
        self._update_plot_range(self.accel_plot, time_array, accel_arrays)
        self._update_plot_range(self.gyro_plot, time_array, gyro_arrays)

    def shutdown(self):
        self._poll_timer.stop()
        self._stop_requested.emit()
        self._thread.quit()
        self._thread.wait(2000)
