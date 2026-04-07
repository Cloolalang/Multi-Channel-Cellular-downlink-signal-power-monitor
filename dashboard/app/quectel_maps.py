"""E-UTRA band and BW mapping from Node-RED (Quectel RF test)."""

import re

BAND_EUTRA_TO_QUECTEL: dict[int, int] = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    7: 6,
    8: 7,
    9: 8,
    10: 9,
    11: 10,
    12: 11,
    13: 12,
    17: 13,
    18: 14,
    19: 15,
    20: 16,
    25: 17,
    26: 18,
    28: 19,
    34: 20,
    38: 21,
    39: 22,
    40: 23,
    41: 24,
    14: 25,
    66: 26,
    71: 27,
}

BW_MHZ_TO_QUECTEL: dict[float, int] = {
    1.4: 0,
    3.0: 1,
    5.0: 2,
    10.0: 3,
    15.0: 4,
    20.0: 5,
}


def eutra_band_to_quectel(band: int) -> int | None:
    return BAND_EUTRA_TO_QUECTEL.get(int(band))


def bw_mhz_to_quectel(mhz: float) -> int | None:
    try:
        val = round(float(mhz), 1)
    except (TypeError, ValueError):
        return None
    return BW_MHZ_TO_QUECTEL.get(val)


def build_qrxftm(
    *,
    mode: int,
    band_quectel: int,
    earfcn: int,
    antenna: int = 0,
    lna_state: int = 1,
    bw_quectel: int,
) -> str:
    return f"AT+QRXFTM={mode},{band_quectel},{earfcn},{antenna},{lna_state},{bw_quectel}\r\n"


# Node-RED: "+QRXFTM: -878, -87" — second field is RSSI (dBm).
_QRXFTM_RSSI_RE = re.compile(r"\+QRXFTM:\s*-?\d+\s*,\s*(-?\d+)", re.IGNORECASE)


def parse_qrxftm_rssi_line(line: str) -> float | None:
    m = _QRXFTM_RSSI_RE.search(line.strip())
    if not m:
        return None
    return float(m.group(1))
