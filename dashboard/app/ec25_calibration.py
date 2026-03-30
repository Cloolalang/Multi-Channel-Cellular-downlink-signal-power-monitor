"""Quectel EC25 per-band calibration (dB), stored as positive attenuation values.

Stored RSSI = raw +QRXFTM value plus this value (same sense as Node-RED: payload + atten).

Dashboard Settings can override or extend bands via ``dashboard_config.json`` key
``band_attenuation_db``. For each band, the saved table wins over the built-ins below.
"""

from __future__ import annotations

from typing import Any

# Built-in defaults when a band is not listed in the saved dashboard table.
EC25_BAND_CALIBRATION_DB: dict[int, float] = {
    1: 72.0,
    3: 71.0,
    8: 65.0,  # same as B20
    20: 65.0,
}

_saved_band_atten: dict[int, float] = {}


def configure_band_attenuation(raw: dict[str, Any] | None) -> None:
    """Replace the persisted band→dB map (from JSON). Empty dict = use built-ins only."""
    global _saved_band_atten
    if not raw:
        _saved_band_atten = {}
        return
    out: dict[int, float] = {}
    for k, v in raw.items():
        try:
            b = int(k)
            out[b] = float(v)
        except (TypeError, ValueError):
            continue
    _saved_band_atten = out


def export_band_attenuation_for_save() -> dict[str, float]:
    """Shape for ``dashboard_config.json`` (string keys for JSON)."""
    return {str(b): float(v) for b, v in sorted(_saved_band_atten.items())}


def atten_db_for_band(band_eutra: int) -> float:
    b = int(band_eutra)
    if b in _saved_band_atten:
        return float(_saved_band_atten[b])
    return float(EC25_BAND_CALIBRATION_DB.get(b, 0.0))


def band_atten_rows_for_ui() -> list[dict[str, int | float]]:
    """Bands = union(built-in keys, saved keys); value is effective dB for that band."""
    bands = sorted(set(EC25_BAND_CALIBRATION_DB) | set(_saved_band_atten))
    return [{"band": b, "atten_db": atten_db_for_band(b)} for b in bands]


def band_atten_dict_for_api() -> dict[str, float]:
    """Flat map for Settings GET / form sync (string keys for JSON)."""
    rows = band_atten_rows_for_ui()
    return {str(int(r["band"])): float(r["atten_db"]) for r in rows}
