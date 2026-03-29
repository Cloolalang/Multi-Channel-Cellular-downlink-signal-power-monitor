"""Persist dashboard connection/timing overrides in powertest_dashboard/dashboard_config.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.settings import Settings

_CONFIG_NAME = "dashboard_config.json"


def config_path() -> Path:
    return Path(__file__).resolve().parent.parent / _CONFIG_NAME


def apply_dashboard_config_file(s: Settings) -> bool:
    """Merge JSON file into settings (if present). Returns True if file was read."""
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
    return True


def save_dashboard_config_file(s: Settings) -> None:
    path = config_path()
    data = {
        "serial_port": s.serial_port,
        "baudrate": s.baudrate,
        "mock_modem": s.mock_modem,
        "scan_channel_delay_sec": s.scan_channel_delay_sec,
        "scan_round_delay_sec": s.scan_round_delay_sec,
        "ws_push_hz": s.ws_push_hz,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
