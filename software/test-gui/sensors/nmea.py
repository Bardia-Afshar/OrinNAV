"""NMEA 0183 parsing (GGA, GSA, GSV, RMC, VTG). """

import dataclasses
import time
from dataclasses import dataclass, field

# GGA field 6
FIX_QUALITY_NAMES = {
    0: "No fix",
    1: "GPS (SPS)",
    2: "DGPS",
    3: "PPS",
    4: "RTK fixed",
    5: "RTK float",
    6: "Dead reckoning",
    7: "Manual",
}

FIX_TYPE_NAMES = {1: "No fix", 2: "2D", 3: "3D"}

CONSTELLATION_NAMES = {
    "GP": "GPS",
    "GL": "GLONASS",
    "GA": "Galileo",
    "GB": "BeiDou",
    "BD": "BeiDou",
    "GQ": "QZSS",
    "GI": "NavIC",
    "GN": "Combined",
}

# GSA field 18 (4.11), only way to tell whose PRNs a $GNGSA lists
SYSTEM_ID_NAMES = {
    1: "GPS",
    2: "GLONASS",
    3: "Galileo",
    4: "BeiDou",
    5: "QZSS",
    6: "NavIC",
}

# drop a constellation's GSV list if it hasn't been refreshed in this long
SATELLITE_STALE_S = 10.0

# sentences closer together than this are from the same 1 Hz batch
BATCH_WINDOW_S = 1.5


@dataclass(frozen=True)
class Satellite:
    # snr: C/N0 dB-Hz, None = in view but not tracked
    # used is from GSA, filled in by snapshot()
    prn: int
    constellation: str
    elevation: float | None = None
    azimuth: float | None = None
    snr: float | None = None
    used: bool = False


@dataclass
class GNSSState:
    latitude: float | None = None
    longitude: float | None = None
    altitude_m: float | None = None
    geoid_separation_m: float | None = None
    utc_time: str | None = None
    utc_date: str | None = None

    fix_quality: int | None = None
    fix_type: int | None = None
    satellites_used: int | None = None
    satellites_in_view: int = 0
    satellites_with_signal: int = 0
    hdop: float | None = None
    pdop: float | None = None
    vdop: float | None = None
    snr_mean: float | None = None
    snr_max: float | None = None

    speed_kmh: float | None = None
    course_deg: float | None = None

    satellites: list[Satellite] = field(default_factory=list)

    @property
    def fix_quality_text(self):
        if self.fix_quality is None:
            return "--"
        return FIX_QUALITY_NAMES.get(self.fix_quality, f"Unknown ({self.fix_quality})")

    @property
    def fix_type_text(self):
        if self.fix_type is None:
            return "--"
        return FIX_TYPE_NAMES.get(self.fix_type, f"Unknown ({self.fix_type})")

    @property
    def has_fix(self):
        return bool(self.fix_quality) and self.latitude is not None

    @property
    def accuracy_text(self):
        if self.hdop is None:
            return "--"
        h = self.hdop
        if h < 1:
            label = "Ideal"
        elif h < 2:
            label = "Excellent"
        elif h < 5:
            label = "Good"
        elif h < 10:
            label = "Moderate"
        elif h < 20:
            label = "Fair"
        else:
            label = "Poor"
        return f"{label} (HDOP {h:.2f})"


def checksum_ok(sentence):
    if not sentence.startswith("$") or "*" not in sentence:
        return False
    body, _, given = sentence[1:].rpartition("*")
    if len(given) < 2:
        return False
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    try:
        return cs == int(given[:2], 16)
    except ValueError:
        return False


def gga_fix_quality(sentence):
    if not sentence:
        return None
    fields = sentence.split(",")
    return _i(fields[6]) if len(fields) > 6 else None


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _degrees(value, hemisphere):
    # ddmm.mmmm / dddmm.mmmm
    raw = _f(value)
    if raw is None or not hemisphere:
        return None
    degrees = int(raw // 100)
    minutes = raw - degrees * 100
    result = degrees + minutes / 60.0
    if hemisphere in ("S", "W"):
        result = -result
    return result


class NMEAParser:
    def __init__(self):
        self._state = GNSSState()
        # GSV comes as a numbered group per constellation (and per signal on
        # 4.11); only publish a group once its last message lands
        self._gsv_partial = {}
        self._gsv_done = {}
        # key -> (timestamp, constellation or None if unscoped, PRNs)
        self._used_by_system = {}
        self.sentences_parsed = 0
        self.checksum_failures = 0

    def feed(self, sentence):
        sentence = sentence.strip()
        if not sentence.startswith("$"):
            return False
        if not checksum_ok(sentence):
            self.checksum_failures += 1
            return False

        body = sentence[1:].rpartition("*")[0]
        fields = body.split(",")
        tag = fields[0]
        if len(tag) < 5:
            return False
        talker, kind = tag[:2], tag[2:5]
        parse = {
            "GGA": self._gga,
            "GSA": self._gsa,
            "GSV": self._gsv,
            "RMC": self._rmc,
            "VTG": self._vtg,
        }.get(kind)
        if parse is None:
            return False
        parse(talker, fields)
        self.sentences_parsed += 1
        return True

    def _gga(self, talker, f):
        if len(f) < 10:
            return
        s = self._state
        s.utc_time = self._format_time(f[1])
        lat = _degrees(f[2], f[3])
        lon = _degrees(f[4], f[5])
        s.fix_quality = _i(f[6])
        s.satellites_used = _i(f[7])
        s.hdop = _f(f[8])
        s.altitude_m = _f(f[9])
        if len(f) > 11:
            s.geoid_separation_m = _f(f[11])
        if s.fix_quality and lat is not None and lon is not None:
            s.latitude = lat
            s.longitude = lon

    def _gsa(self, talker, f):
        if len(f) < 18:
            return
        s = self._state
        s.fix_type = _i(f[2])
        s.pdop = _f(f[15])
        hdop = _f(f[16])
        if hdop is not None:
            s.hdop = hdop
        s.vdop = _f(f[17])

        # one GSA per constellation, so keep a set per constellation instead of
        # overwriting a shared one
        system_id = _i(f[18]) if len(f) > 18 else None
        constellation = SYSTEM_ID_NAMES.get(system_id) if system_id else None
        if constellation is None:
            name = CONSTELLATION_NAMES.get(talker)
            # GN without a system ID can't be scoped; match on PRN alone
            constellation = name if name and name != "Combined" else None
        prns = {prn for prn in (_i(v) for v in f[3:15]) if prn}
        now = time.monotonic()
        if constellation is not None:
            self._used_by_system[constellation] = (now, constellation, prns)
            return

        # unscoped $GNGSA: merge within a batch, reset on the next or dropped
        # sats linger
        previous = self._used_by_system.get("")
        if previous is not None and now - previous[0] < BATCH_WINDOW_S:
            prns = prns | previous[2]
        self._used_by_system[""] = (now, None, prns)

    def _gsv(self, talker, f):
        if len(f) < 4:
            return
        total_msgs = _i(f[1])
        msg_num = _i(f[2])
        if total_msgs is None or msg_num is None:
            return

        # 4.11 appends a signal ID; key on it too so L1 and L5 groups don't
        # clobber each other
        blocks = f[4:]
        signal_id = ""
        if len(blocks) % 4 == 1:
            signal_id = blocks[-1]
            blocks = blocks[:-1]
        key = f"{talker}:{signal_id}"

        if msg_num == 1:
            self._gsv_partial[key] = []
        batch = self._gsv_partial.setdefault(key, [])
        name = CONSTELLATION_NAMES.get(talker, talker)
        for i in range(0, len(blocks) - 3, 4):
            prn = _i(blocks[i])
            if prn is None:
                continue
            batch.append(
                Satellite(
                    prn=prn,
                    constellation=name,
                    elevation=_f(blocks[i + 1]),
                    azimuth=_f(blocks[i + 2]),
                    snr=_f(blocks[i + 3]),
                )
            )

        if msg_num >= total_msgs:
            self._gsv_done[key] = (time.monotonic(), batch)
            self._gsv_partial.pop(key, None)

    def _rmc(self, talker, f):
        if len(f) < 10:
            return
        s = self._state
        s.utc_time = self._format_time(f[1])
        if f[9] and len(f[9]) == 6:
            d, m, y = f[9][0:2], f[9][2:4], f[9][4:6]
            s.utc_date = f"20{y}-{m}-{d}"
        knots = _f(f[7])
        if knots is not None:
            s.speed_kmh = knots * 1.852
        course = _f(f[8])
        if course is not None:
            s.course_deg = course
        if f[2] == "A":
            lat = _degrees(f[3], f[4])
            lon = _degrees(f[5], f[6])
            if lat is not None and lon is not None:
                s.latitude = lat
                s.longitude = lon

    def _vtg(self, talker, f):
        if len(f) < 8:
            return
        s = self._state
        course = _f(f[1])
        if course is not None:
            s.course_deg = course
        knots = _f(f[5])
        kmh = _f(f[7])
        if kmh is not None:
            s.speed_kmh = kmh
        elif knots is not None:
            s.speed_kmh = knots * 1.852

    @staticmethod
    def _format_time(value):
        if not value or len(value) < 6:
            return None
        return f"{value[0:2]}:{value[2:4]}:{value[4:6]}"

    def snapshot(self):
        # copy, caller's on another thread and would see torn fields otherwise.
        # sat list is rebuilt not mutated so shallow is fine
        s = self._state
        now = time.monotonic()

        # same sat can show up in L1 and L5 groups, keep the strongest
        best = {}
        for stamped, batch in self._gsv_done.values():
            if now - stamped > SATELLITE_STALE_S:
                continue
            for sat in batch:
                k = (sat.constellation, sat.prn)
                prev = best.get(k)
                if prev is None or (sat.snr or -1) > (prev.snr or -1):
                    best[k] = sat

        used_pairs = set()
        used_any = set()
        for stamped, constellation, prns in self._used_by_system.values():
            if now - stamped > SATELLITE_STALE_S:
                continue
            if constellation is None:
                used_any |= prns
            else:
                used_pairs |= {(constellation, prn) for prn in prns}

        sats = []
        for (constellation, prn), sat in best.items():
            used = (constellation, prn) in used_pairs or prn in used_any
            sats.append(
                Satellite(
                    prn=sat.prn,
                    constellation=sat.constellation,
                    elevation=sat.elevation,
                    azimuth=sat.azimuth,
                    snr=sat.snr,
                    used=used,
                )
            )
        sats.sort(key=lambda x: (-(x.snr or -1), x.constellation, x.prn))

        snrs = [x.snr for x in sats if x.snr]
        s.satellites = sats
        s.satellites_in_view = len(sats)
        s.satellites_with_signal = len(snrs)
        s.snr_mean = sum(snrs) / len(snrs) if snrs else None
        s.snr_max = max(snrs) if snrs else None
        return dataclasses.replace(s)
