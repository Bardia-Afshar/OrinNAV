# OrinNav

![Status](https://img.shields.io/badge/status-prototype-orange) ![Revision](https://img.shields.io/badge/rev-0.0.1-blue)

OrinNav is a navigation HAT for the NVIDIA Jetson Orin Nano. It sits on the 40-pin header and adds an RTK-capable dual-band GNSS receiver, a 6-axis IMU and a CAN FD port. The idea is to put the basic navigation hardware on one board instead of having a GNSS module, IMU breakout and CAN adapter wired together separately. A big goal is to keep it cheap, so RTK-grade positioning is within reach of hobbyists and small robotics projects.

> **Early prototype.** Feedback, ideas and collaboration are very welcome, see [Contributing](#contributing).

**This is a hardware repo.** It has the schematic, layout and manufacturing files. There is no robot or navigation software. The software here is just a test GUI I wrote to bring the board up and check that everything works.

```
hardware/
  OrinNav_v0.0.1_schematic.pdf
  OrinNav_v0.0.1_layout.pdf
  manufacturing/
    OrinNav_v0.0.1_BOM.csv         with LCSC part numbers
    OrinNav_v0.0.1_CPL.csv         pick-and-place
    OrinNav_v0.0.1_gerbers.zip
software/
  test-gui/                        bring-up GUI, runs on the Jetson
```
<img width="1077" height="1008" alt="3D" src="https://github.com/user-attachments/assets/8306b057-70dc-4b4d-87ac-152bfddcf67b" />

<img width="2794" height="2429" alt="Jetson_1" src="https://github.com/user-attachments/assets/e7c0bcad-405b-4b14-9f78-bb3bae491670" />

<img width="3388" height="2432" alt="Jetson_2" src="https://github.com/user-attachments/assets/0a36252d-92ff-4066-937d-0b9e002b6542" />



## Hardware

4-layer board, L-shaped so it runs along the 40-pin header. The repo has the schematic and layout as PDFs, plus gerbers, BOM and pick-and-place files, which are enough to get it made at a fab/assembly house.

| Ref | Part | What it does |
|:---:|:----:|:------------:|
| U6 | Quectel LC29HEAMD | GNSS (GPS/GLONASS/Galileo/BDS/QZSS, L1+L5), RTK, NMEA out / RTCM in over UART |
| U4 | ST LSM6DSV16X | IMU, on SPI |
| U9 | NXP TJA1462 | CAN FD transceiver |
| U5 | WCH CH340C | USB-serial, for talking to the GNSS module from a PC |
| U7, U8 | TI TXU0202 | 3.3 V / 2.8 V UART level shifting |
| U1, U2 | TI TPS7A2033 | 3.3 V LDOs, one for the logic, one only for GNSS |
| U3 | TI LP5907-2.8 | 2.8 V LDO for the shifters |
| BT1 | CR2032 | GNSS backup battery, needs a cell fitted for GPS to work |
| J2 | SMA | GNSS antenna, biased for an active antenna |

For the antenna I'm using Quectel's YEGB001Q1A active antenna on the SMA connector.

Power comes from the Jetson's 5 V (header pins 2 and 4). Two green LEDs show 5 V and 3.3 V are up.

A few things on the board you need to know about:

- **P1 `UART_SEL` jumper (ORIN / GNSS / USB).** Selects whether the GNSS UART goes to the Jetson (`/dev/ttyTHS1`, pins 8/10) or to the mini-USB port J1 ("GNSS DEBUG") through the CH340C. For the test GUI it has to be on the Jetson side. The USB side is for using Quectel's QGNSS tool on a PC.
- **SW1 "GNSS RESET"** resets the GNSS module.
- **J3** is a 4-pin XH cable to the Orin Nano's own CAN header. **J4** is the CAN_H / CAN_L screw terminal. Termination is always fitted (split, 2 x 62 ohm) and the transceiver is always on.
- IMU interrupt pins go to the header (29, 31).

### 40-pin header

| Pin | Signal |
|-----|--------|
| 2, 4 | 5 V in |
| 8 | UART1 TXD (Jetson to GNSS) |
| 10 | UART1 RXD (GNSS to Jetson) |
| 19 / 21 / 23 / 24 | IMU MOSI / MISO / SCLK / CS |
| 29 / 31 | IMU INT1 / INT2 |

Full BOM is in `hardware/manufacturing/OrinNav_v0.0.1_BOM.csv`. It has LCSC part numbers for every part, so for JLCPCB assembly you can drop the gerbers zip, BOM and CPL straight into their order page and the parts get matched automatically.

### Mounting

To mount the board, remove the 3 screws from the Jetson Orin Nano developer kit and put a 19 mm M2 standoff in each place. Then sit the board on the header and screw it down onto the standoffs.

You need:

- 3 x M2 standoff, 19 mm
- 3 x M2 screw, 3 mm

## Test GUI

`software/test-gui` is a PySide6 app that runs on the Jetson. It's a bench tool, not navigation software. It has three tabs, one per thing I needed to verify. CAN isn't in the GUI, see [Checking CAN](#checking-can).

### IMU

Reads accel and gyro over SPI every 20 ms (sensor set to 120 Hz, ±2 g, ±500 dps) and plots them live.

What you should see: with the board sitting still, one accel axis reads about ±1 g and the other two near 0. Gyro stays close to 0 and jumps when you move the board.

<img width="1851" height="1054" alt="IMU_TAB" src="https://github.com/user-attachments/assets/67458a8f-be73-4daa-bf3a-4a5a51ba1189" />



### GPS

Reads NMEA from the LC29HEA on `/dev/ttyTHS1` at 460800 baud. Shows fix type, DOP, satellites in view and in use with C/N0, position, altitude, speed, course, UTC time, a per-satellite table and a satellite-imagery map with your position on it.

The status line at the top is the first thing to look at. It tells you which of three states you're in:

- `No data on /dev/ttyTHS1` : nothing arriving at all
- `Receiving bytes ... but no valid NMEA` : something arrives but it's garbage
- `Connected: N sentences` : link is fine

What you should see: the satellite count goes up within a few seconds if the antenna can see the sky. A first fix can take a minute or so from cold. Indoors you'll likely see satellites but no fix.

Map tiles come from Esri World Imagery and get cached in `~/.cache/orinnav/satellite_tiles`, so the Jetson needs internet the first time it shows an area.

<img width="1851" height="1053" alt="GPS_TAB" src="https://github.com/user-attachments/assets/c57b7f2e-f2a8-4881-98cd-93ff0a619c18" />



### RTK

An NTRIP v1 client. You put in caster, port, mountpoint, username and password, and it streams RTCM corrections into the receiver over the same UART. It also sends the receiver's GGA to the caster every 10 s, because VRS casters (like Point One Polaris) send nothing until they know where you are.

Default is Point One TrueRTK EU (`truertk-eu.pointonenav.com:2101`, mountpoint `AUTO`). I tested RTK with Point One on their free trial. You need your own account, either theirs or any other NTRIP v1 caster. Settings except the password are saved between runs.

What you should see: "Receiver fix" goes from GPS to RTK float, then RTK fixed. That's the real test that the whole chain works. RTK fixed needs open sky. Next to a building or under trees it can sit in float.

<img width="1851" height="1053" alt="RTK_TAB" src="https://github.com/user-attachments/assets/c4ba3e05-b518-4ede-9629-8edecb636870" />


## Checking CAN

The GUI doesn't cover CAN, but you can test it with SocketCAN and `can-utils`. Plug J3 into the Orin Nano's CAN header first.

```bash
sudo apt-get install busybox can-utils

# pinmux for can0 (lost on reboot, run again after)
sudo busybox devmem 0x0c303018 w 0xc458   # can0_din
sudo busybox devmem 0x0c303010 w 0xc400   # can0_dout

sudo modprobe can
sudo modprobe can_raw
sudo modprobe mttcan

sudo ip link set can0 up type can bitrate 500000 dbitrate 1000000 berr-reporting on fd on
```

Then put another CAN node on J4 (a USB-CAN adapter on a PC works) at the same bitrate and run:

```bash
candump -x any &
cansend can0 123#abcdabcd       # classic CAN frame
cansend can0 123##1abcdabcd     # CAN FD frame
```

You should see the frames on the other node, and anything it sends shows up in `candump`. If nothing else is on the bus, a sent frame gets no ACK and `ip -details -statistics link show can0` shows error counters going up. That still tells you the controller and transceiver are working. The board already has termination on it, so on a short bench cable you don't need to add any.

## Running the GUI

You need a Jetson Orin Nano with the board on it, JetPack 6, Python 3.10+, a monitor (or a desktop session), an active GNSS antenna on J2 (I use the Quectel YEGB001Q1A) and a CR2032 in BT1. GPS won't work without the backup battery.

**1. Enable SPI on the header.** Run `sudo /opt/nvidia/jetson-io/jetson-io.py`, enable SPI1 on the 40-pin header, save and reboot.

**2. Fix the JetPack 6 UART bug.** Without this the GPS tab won't work. See [Known issue: JetPack 6 UART](#known-issue-jetpack-6-uart) below.

**3. Clone and run:**

```bash
git clone https://github.com/Bardia-Afshar/OrinNAV.git
cd OrinNAV/software/test-gui
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The window opens maximized with the three tabs. Each sensor runs in its own thread, so if one part isn't working the other tabs still do.

If your wiring or setup is different, the SPI bus/mode/speed, UART port, baud rate and NTRIP defaults are all in `config.py`.

## Problems you might hit

**`IMU init failed: ... WHO_AM_I reads=['0x00', ...]` or `0xFF`**
The IMU isn't answering at all. Usually SPI isn't enabled in jetson-io (step 1), or you didn't reboot after. Check `/dev/spidev0.0` exists.

**`IMU init failed: ... WHO_AM_I reads=` something close to `0x70` but not quite**
It's talking, but the bits are getting sampled wrong. Lower `SPI_SPEED_HZ` in `config.py` or try `SPI_MODE = 0`.

**`IMU init failed: [Errno 13] Permission denied` / `GPS open failed: ... Permission denied`**
Your user can't open the device. `ls -l /dev/spidev0.0 /dev/ttyTHS1` to see the group, add yourself to it (normally `gpio` for SPI and `dialout` for the UART), then log out and back in.

**`No data on /dev/ttyTHS1`**
Check the `UART_SEL` jumper is on the Jetson side, not USB, and that there's a CR2032 in BT1. Then check the 3.3 V LED and that the GNSS module isn't held in reset.

**`Receiving bytes ... but no valid NMEA` with lots of bad checksums**
On JetPack 6 this is almost always the UART DMA bug below. If you've already applied the fix, check the baud in `config.py` is 460800 (the only rate the module gave clean data at).

**Satellites in view but no fix**
Antenna problem or no sky view. The SMA input expects an active antenna. Take it outside.

**RTK: `Caster rejected the username/password (401 Unauthorized)` / `Mountpoint '...' not found`**
Wrong credentials or mountpoint for that caster. Note the Point One default is the EU caster. Use the one for your region.

**RTK: connected, data is flowing, but fix stays at GPS**
The receiver needs a valid position before corrections do anything, and the caster needs a GGA from it. Wait for a normal GPS fix first.

**Satellite map is blank**
No internet on the Jetson. Everything else on the tab works without it.

**`Could not load the Qt platform plugin "xcb"`**
`sudo apt install libxcb-cursor0`. If you're starting it over SSH, run it with `DISPLAY=:0` so it opens on the Jetson's screen.

## Known issue: JetPack 6 UART

On JetPack 6, `/dev/ttyTHS1` returns mostly `0x00` bytes. It's a bug in the `serial-tegra` driver in DMA mode, not the board. The fix is a device-tree overlay that puts the UART in PIO mode:

```bash
git clone https://github.com/jetsonhacks/jetson-orin-uart.git
cd jetson-orin-uart
sudo bash install.sh
sudo reboot
```

Check it worked with `sudo dmesg | grep -i 3100000`. You should see `RX in PIO mode`. Re-flashing or upgrading JetPack undoes this, so run it again after.


## Contributing

This is an early prototype, so feedback and collaboration are very welcome. If you have ideas for the next revision, want to share your own test results, or have any suggestions, open an [issue](../../issues) or send a pull request.
