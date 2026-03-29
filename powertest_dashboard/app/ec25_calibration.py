"""Quectel EC25 per-band calibration (dB), stored as positive attenuation values.

Stored RSSI = raw +QRXFTM value plus this value (same sense as Node-RED: payload + atten).
"""

# Band (E-UTRA) → attenuation dB (positive)
EC25_BAND_CALIBRATION_DB: dict[int, float] = {
    1: 72.0,
    3: 71.0,
    8: 65.0,  # same as B20
    20: 65.0,
}


def atten_db_for_band(band_eutra: int) -> float:
    return EC25_BAND_CALIBRATION_DB.get(int(band_eutra), 0.0)
