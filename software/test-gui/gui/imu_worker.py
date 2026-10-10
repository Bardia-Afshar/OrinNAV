

import threading

from PySide6.QtCore import QObject, QTimer, Signal

import config
from sensors.lsm6dsv16x import LSM6DSV16X


class IMUWorker(QObject):
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._imu = None
        self._timer = None
        self._lock = threading.Lock()
        self._latest_reading = None

    def start(self):
        try:
            self._imu = LSM6DSV16X(
                bus=config.SPI_BUS,
                device=config.SPI_DEVICE,
                speed_hz=config.SPI_SPEED_HZ,
                mode=config.SPI_MODE,
            )
            self._imu.initialize()
        except Exception as exc:
            self.error.emit(f"IMU init failed: {exc}")
            return

        self.status_changed.emit(f"Connected: {self._imu.part_name}")

        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(config.POLL_INTERVAL_MS)

    def _poll(self):
        try:
            ax, ay, az, gx, gy, gz = self._imu.read_accel_gyro()
            reading = {"accel": (ax, ay, az), "gyro": (gx, gy, gz)}
            with self._lock:
                self._latest_reading = reading
        except Exception as exc:
            if self._timer is not None:
                self._timer.stop()
            self.error.emit(f"IMU read failed: {exc}")

    def take_latest(self):
        with self._lock:
            reading, self._latest_reading = self._latest_reading, None
        return reading

    def stop(self):
        if self._timer is not None:
            self._timer.stop()
        if self._imu is not None:
            self._imu.close()
