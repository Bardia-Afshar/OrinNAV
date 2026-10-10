# LSM6DSV16X
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED_HZ = 1_000_000
SPI_MODE = 0b11  # CPOL=1, CPHA=1

POLL_INTERVAL_MS = 20

# Quectel LC29HEA, 460800 rate
GPS_PORT = "/dev/ttyTHS1"
GPS_BAUD = 460800

# only needs to keep the UART FIFO from overflowing, data is 1 Hz
GPS_POLL_INTERVAL_MS = 100

# Point One TrueRTK EU, creds go in the RTK tab
RTK_DEFAULT_CASTER = "truertk-eu.pointonenav.com"
RTK_DEFAULT_PORT = 2101
RTK_DEFAULT_MOUNTPOINT = "AUTO"

RTK_POLL_INTERVAL_MS = 100

# Polaris picks the correction source from our GGA, so keep sending it
RTK_GGA_INTERVAL_S = 10

RTK_CONNECT_TIMEOUT_S = 5
