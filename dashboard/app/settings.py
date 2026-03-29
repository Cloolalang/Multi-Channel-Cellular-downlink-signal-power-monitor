from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PT_", env_file=".env", extra="ignore")

    flows_json: Path = Path(__file__).resolve().parents[2] / "flows.json"
    serial_port: str = "COM40"
    baudrate: int = 115200
    # Set PT_MOCK_MODEM=true for UI dev without hardware (synthetic RSSI + fake OK on TX).
    mock_modem: bool = False
    ws_push_hz: float = 4.0
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


settings = Settings()
