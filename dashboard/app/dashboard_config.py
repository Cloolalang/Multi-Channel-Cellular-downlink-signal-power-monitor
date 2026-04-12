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

# Per-channel dashboard state loaded from file; consumed once at app startup after MNO preset.
_channels_state_from_file: dict[str, Any] | None = None


def get_mno_common_preset_stored_dict() -> dict[str, Any] | None:
    return _mno_common_preset_dict


def set_mno_common_preset_stored_dict(d: dict[str, Any] | None) -> None:
    global _mno_common_preset_dict
    _mno_common_preset_dict = d


def config_path() -> Path:
    return Path(__file__).resolve().parent.parent / _CONFIG_NAME


def consume_channels_state_from_file() -> dict[str, Any] | None:
    """Return channels blob from last config load, then clear (startup runs once)."""
    global _channels_state_from_file
    s = _channels_state_from_file
    _channels_state_from_file = None
    return s


def pack_channels_state(runtime: Any) -> dict[str, Any]:
    """Serialize per-channel enable + RF fields for dashboard_config.json."""
    out: dict[str, Any] = {}
    for prefix, ch in runtime.channels.items():
        out[prefix] = {
            "channel_enabled": bool(ch.channel_enabled),
            "band_eutra": int(ch.band_eutra),
            "earfcn": int(ch.earfcn),
            "bw_mhz": float(ch.bw_mhz),
            "mno": str(ch.mno),
            "atten_db": float(ch.atten_db),
        }
    return out


def apply_saved_channel_state(runtime: Any, data: dict[str, Any]) -> None:
    """Restore per-channel UI/RF state after MNO baseline (or on top of defaults)."""
    for prefix, d in data.items():
        if prefix not in getattr(runtime, "channels", {}) or not isinstance(d, dict):
            continue
        ch = runtime.channels[prefix]
        if "channel_enabled" in d:
            ch.channel_enabled = bool(d["channel_enabled"])
        if "band_eutra" in d:
            try:
                ch.band_eutra = int(d["band_eutra"])
            except (TypeError, ValueError):
                pass
        if "earfcn" in d:
            try:
                ch.earfcn = int(d["earfcn"])
            except (TypeError, ValueError):
                pass
        if "bw_mhz" in d:
            try:
                ch.bw_mhz = float(d["bw_mhz"])
            except (TypeError, ValueError):
                pass
        if "mno" in d and d["mno"] is not None:
            ch.mno = str(d["mno"])
        if "atten_db" in d:
            try:
                ch.atten_db = float(d["atten_db"])
            except (TypeError, ValueError):
                pass
        elif "band_eutra" in d:
            ch.sync_atten_from_band_ec25()


def _apply_gauge_fields_from_raw(raw: dict[str, Any], runtime: Any) -> None:
    """Restore control-panel gauge scale from config (optional keys)."""
    for key in ("gauge_min", "gauge_max"):
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

    def _set_float(name: str) -> None:
        if name not in raw:
            return
        try:
            setattr(s, name, float(raw[name]))
        except (TypeError, ValueError):
            pass

    _set_str("serial_port")
    _set_int("baudrate")
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
    global _channels_state_from_file
    ch = raw.get("channels")
    if isinstance(ch, dict) and ch:
        _channels_state_from_file = ch
    else:
        _channels_state_from_file = None
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
    raw_prev: dict[str, Any] = {}
    if path.is_file():
        try:
            raw_prev = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw_prev = {}
    mno = get_mno_common_preset_stored_dict()
    if mno is None:
        prev = raw_prev.get("mno_common_preset")
        if isinstance(prev, dict):
            set_mno_common_preset_stored_dict(json.loads(json.dumps(prev)))
            mno = get_mno_common_preset_stored_dict()
    data = {
        "serial_port": s.serial_port,
        "baudrate": s.baudrate,
        "scan_channel_delay_sec": s.scan_channel_delay_sec,
        "scan_round_delay_sec": s.scan_round_delay_sec,
        "ws_push_hz": s.ws_push_hz,
        "rssi_smooth_samples": s.rssi_smooth_samples,
        "composite_smooth_samples": s.composite_smooth_samples,
    }
    if mno is not None:
        data["mno_common_preset"] = mno
    data["band_attenuation_db"] = ec25_calibration.export_band_attenuation_for_save()
    if runtime is not None:
        for key in ("gauge_min", "gauge_max"):
            v = getattr(runtime, key, None)
            data[key] = v
        data["channels"] = pack_channels_state(runtime)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
