"""Persist dashboard connection/timing overrides (Multi-Channel Cellular Downlink Signal Power Monitor)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app import ec25_calibration

if TYPE_CHECKING:
    from app.settings import Settings

_CONFIG_NAME = "dashboard_config.json"

# Parsed from `mno_common_preset` in dashboard_config.json; None if key absent (use flows.json).
_mno_common_preset_dict: dict[str, Any] | None = None


def get_mno_common_preset_stored_dict() -> dict[str, Any] | None:
    return _mno_common_preset_dict


def set_mno_common_preset_stored_dict(d: dict[str, Any] | None) -> None:
    global _mno_common_preset_dict
    _mno_common_preset_dict = d


def config_path() -> Path:
    return Path(__file__).resolve().parent.parent / _CONFIG_NAME


def _apply_gauge_fields_from_raw(raw: dict[str, Any], runtime: Any) -> None:
    """Restore control-panel gauge scale from config (optional keys)."""
    for key in ("gauge_min", "gauge_max", "gauge_seg1", "gauge_seg2"):
        if key not in raw:
            continue
        val = raw[key]
        if val is None or val == "":
            setattr(runtime, key, None)
        else:
            try:
                setattr(runtime, key, float(val))
            except (TypeError, ValueError):
                pass


def apply_dashboard_config_file(s: Settings, runtime: Any | None = None) -> bool:
    """Merge JSON file into settings (if present). Optionally apply gauge + band atten to runtime."""
    path = config_path()
    if not path.is_file():
        return False
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    def _set_str(name: str) -> None:
        if name not in raw or not isinstance(raw[name], str):
            return
        v = raw[name].strip()
        if v:
            setattr(s, name, v)

    def _set_int(name: str) -> None:
        if name not in raw:
            return
        try:
            setattr(s, name, int(raw[name]))
        except (TypeError, ValueError):
            pass

    def _set_bool(name: str) -> None:
        if name not in raw:
            return
        setattr(s, name, bool(raw[name]))

    def _set_float(name: str) -> None:
        if name not in raw:
            return
        try:
            setattr(s, name, float(raw[name]))
        except (TypeError, ValueError):
            pass

    _set_str("serial_port")
    _set_int("baudrate")
    _set_bool("mock_modem")
    _set_float("scan_channel_delay_sec")
    _set_float("scan_round_delay_sec")
    _set_float("ws_push_hz")
    _set_int("rssi_smooth_samples")
    _set_int("composite_smooth_samples")
    if "mno_common_preset" in raw and isinstance(raw["mno_common_preset"], dict):
        set_mno_common_preset_stored_dict(raw["mno_common_preset"])
    if "band_attenuation_db" in raw and isinstance(raw["band_attenuation_db"], dict):
        ec25_calibration.configure_band_attenuation(raw["band_attenuation_db"])
    clamp_smooth_samples(s)
    if runtime is not None:
        _apply_gauge_fields_from_raw(raw, runtime)
    return True


def clamp_smooth_samples(s: Settings) -> None:
    """Keep smoothing windows in range when loading from JSON (manual setattr bypasses pydantic)."""
    try:
        s.rssi_smooth_samples = max(1, min(int(s.rssi_smooth_samples), 64))
    except (TypeError, ValueError):
        s.rssi_smooth_samples = 5
    try:
        s.composite_smooth_samples = max(1, min(int(s.composite_smooth_samples), 512))
    except (TypeError, ValueError):
        s.composite_smooth_samples = 10


def save_dashboard_config_file(s: Settings, runtime: Any | None = None) -> None:
    path = config_path()
    data = {
        "serial_port": s.serial_port,
        "baudrate": s.baudrate,
        "mock_modem": s.mock_modem,
        "scan_channel_delay_sec": s.scan_channel_delay_sec,
        "scan_round_delay_sec": s.scan_round_delay_sec,
        "ws_push_hz": s.ws_push_hz,
        "rssi_smooth_samples": s.rssi_smooth_samples,
        "composite_smooth_samples": s.composite_smooth_samples,
    }
    mno = get_mno_common_preset_stored_dict()
    if mno is not None:
        data["mno_common_preset"] = mno
    data["band_attenuation_db"] = ec25_calibration.export_band_attenuation_for_save()
    if runtime is not None:
        for key in ("gauge_min", "gauge_max", "gauge_seg1", "gauge_seg2"):
            v = getattr(runtime, key, None)
            data[key] = v
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
