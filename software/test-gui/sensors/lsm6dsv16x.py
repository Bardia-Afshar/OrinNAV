"""SPI driver for the ST LSM6DSV16X / LSM6DSV16BX IMU."""

import time

import spidev


class LSM6DSV16X:
    WHO_AM_I = 0x0F
    WHO_AM_I_LSM6DSV16X = 0x70
    WHO_AM_I_LSM6DSV16BX = 0x71
    WHO_AM_I_ACCEPTED = (WHO_AM_I_LSM6DSV16X, WHO_AM_I_LSM6DSV16BX)

    CTRL1 = 0x10  # accel ODR / mode
    CTRL2 = 0x11  # gyro ODR / mode
    CTRL3 = 0x12
    CTRL6 = 0x15  # gyro FS
    CTRL8 = 0x17  # accel FS
    OUTX_L_G = 0x22  # 12 bytes: gyro XYZ then accel XYZ

    def __init__(self, bus=0, device=0, speed_hz=1_000_000, mode=0b11):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = mode
        self.spi.bits_per_word = 8

        # first transfer after open is sometimes garbled, throw one away
        time.sleep(0.01)
        try:
            self.read_reg(self.WHO_AM_I)
        except OSError:
            pass

        self.who_am_i = None

        # datasheet sensitivity at +/-2 g and +/-500 dps
        self.accel_scale_g = 0.000061
        self.gyro_scale_dps = 0.0175

    def close(self):
        self.spi.close()

    def read_reg(self, reg):
        return self.spi.xfer2([reg | 0x80, 0x00])[1]

    def write_reg(self, reg, value):
        self.spi.xfer2([reg & 0x7F, value & 0xFF])

    def read_bytes(self, start_reg, length):
        # needs IF_INC set in CTRL3
        return self.spi.xfer2([start_reg | 0x80] + [0x00] * length)[1:]

    @staticmethod
    def _int16_from_lh(low, high):
        value = (high << 8) | low
        if value & 0x8000:
            value -= 65536
        return value

    def read_who_am_i(self):
        return self.read_reg(self.WHO_AM_I)

    def check_who_am_i(self, retries=5):
        # bus can be noisy right after power-up; a missing part reads bad every time
        seen = []
        for _ in range(retries):
            who = self.read_who_am_i()
            seen.append(who)
            if who in self.WHO_AM_I_ACCEPTED:
                self.who_am_i = who
                return who
            time.sleep(0.005)
        accepted = ", ".join(f"0x{v:02X}" for v in self.WHO_AM_I_ACCEPTED)
        raise RuntimeError(
            f"LSM6DSV16X/BX not detected (WHO_AM_I reads={[f'0x{v:02X}' for v in seen]}, "
            f"expected one of {accepted}). A bit or two off usually means SPI sampling: "
            "lower the SPI speed or try mode 0 vs 3."
        )

    @property
    def part_name(self):
        return {
            self.WHO_AM_I_LSM6DSV16X: "LSM6DSV16X",
            self.WHO_AM_I_LSM6DSV16BX: "LSM6DSV16BX",
        }.get(self.who_am_i, "unknown")

    def initialize(self):
        self.check_who_am_i()

        # BDU=1 so low/high bytes don't tear, IF_INC=1 for burst reads
        self.write_reg(self.CTRL3, 0x44)
        # high-performance, 120 Hz
        self.write_reg(self.CTRL1, 0x06)
        self.write_reg(self.CTRL2, 0x06)
        self.write_reg(self.CTRL8, 0x00)  # +/-2 g
        self.write_reg(self.CTRL6, 0x02)  # +/-500 dps

        time.sleep(0.1)

    def _read_raw_block(self):
        data = self.read_bytes(self.OUTX_L_G, 12)
        gyro_raw = (
            self._int16_from_lh(data[0], data[1]),
            self._int16_from_lh(data[2], data[3]),
            self._int16_from_lh(data[4], data[5]),
        )
        accel_raw = (
            self._int16_from_lh(data[6], data[7]),
            self._int16_from_lh(data[8], data[9]),
            self._int16_from_lh(data[10], data[11]),
        )
        return accel_raw, gyro_raw

    def read_accel_gyro(self):
        accel_raw, gyro_raw = self._read_raw_block()
        ax, ay, az = (v * self.accel_scale_g for v in accel_raw)
        gx, gy, gz = (v * self.gyro_scale_dps for v in gyro_raw)
        return ax, ay, az, gx, gy, gz
