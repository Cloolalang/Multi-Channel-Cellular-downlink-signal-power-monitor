from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PT_", env_file=".env", extra="ignore")

    flows_json: Path = Path(__file__).resolve().parents[2] / "flows.json"
    serial_port: str = "COM60"
    baudrate: int = 115200
    # Set PT_MOCK_MODEM=true for UI dev without hardware (synthetic RSSI + fake OK on TX).
    mock_modem: bool = False
    ws_push_hz: float = 4.0
    # Rolling mean / SD window for per-channel RSSI (gauges + charts). Max 64 matches rssi_history storage.
    rssi_smooth_samples: int = Field(default=5, ge=1, le=64)
    # Rolling window over composite dBm for composite avg/sd and composite charts.
    composite_smooth_samples: int = Field(default=10, ge=1, le=512)
    # Minimum pause after each AT+QRXFTM before the next channel (lets modem finish +URC).
    # Set PT_SCAN_CHANNEL_DELAY_SEC=0 to disable (may desync or miss RSSI if too fast).
    scan_channel_delay_sec: float = 1.0
    # After opening a real serial port, send AT+QRFTESTMODE=0, wait, then AT+QRFTESTMODE=1 (Sector 1 deploy inject).
    modem_prep_qrftestmode: bool = True
    modem_prep_delay_sec: float = 2.0
    # After QRFTESTMODE prep, continuously cycle channels: one AT+QRXFTM per enabled channel per pass, repeat.
    modem_qrxftm_scan: bool = True
    # Pause after finishing ch0..ch13 before starting the next full round (0 = back-to-back rounds).
    scan_round_delay_sec: float = 0.0
    # While in HW mode, retry opening the configured serial port this often when unavailable/busy.
    serial_reconnect_interval_sec: float = 2.0
    # If a channel has no fresh +QRXFTM sample for this long, treat displayed values as stale.
    channel_stale_sec: float = 6.0
    # Modem health thresholds (no serial RX age).
    modem_degraded_sec: float = 4.0
    modem_offline_sec: float = 10.0
    # Modem health thresholds (consecutive +QRXFTM step timeouts).
    modem_degraded_timeout_streak: int = 2
    modem_offline_timeout_streak: int = 5


settings = Settings()
