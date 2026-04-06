from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.ec25_calibration import atten_db_for_band
from app.flows_inventory import CHANNEL_COUNT, MnoCommonPreset, channel_prefixes
from app.settings import settings
from app.quectel_maps import (
    build_qrxftm,
    bw_mhz_to_quectel,
    eutra_band_to_quectel,
    parse_qrxftm_rssi_line,
)


def _now() -> float:
    return time.time()


def _rssi_smooth_window() -> int:
    return max(1, min(int(settings.rssi_smooth_samples), 64))


def _composite_smooth_window() -> int:
    return max(1, min(int(settings.composite_smooth_samples), 512))


def _round_dbm_half(x: float) -> float:
    """Quantise dBm (or other dB-domain display values) to 0.5 dB steps (…, 1, 1.5, 2, …)."""
    if not math.isfinite(x):
        return float(x)
    sign = 1.0 if x >= 0.0 else -1.0
    ax = abs(float(x))
    q = sign * (math.floor(ax * 2.0 + 0.5) / 2.0)
    return round(q, 1)


def _round_dbm_series(pairs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(t, _round_dbm_half(v)) for (t, v) in pairs]


def format_uptime_dhms(total_seconds: int) -> str:
    """DD:HH:MM:SS since start (same style as Node-RED Seconds to DD:HH:MM:SS)."""
    total_seconds = max(0, int(total_seconds))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass
class ChannelRuntime:
    prefix: str  # ch0 … ch13
    channel_enabled: bool = True
    band_eutra: int = 20
    earfcn: int = 6400
    bw_mhz: int = 10
    mno: str = "EE"
    atten_db: float = 0.0
    measurement_count: int = 0
    rssi_dbm: float = -80.0
    chart_rssi_avg: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=3600))
    chart_rssi_sd: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=3600))
    rssi_history: deque[float] = field(default_factory=lambda: deque(maxlen=64))
    last_sample_at: float | None = None

    def rolling_mean_sd(self, window: int = 5) -> tuple[float, float]:
        if not self.rssi_history:
            return self.rssi_dbm, 0.0
        vals = list(self.rssi_history)[-window:]
        m = sum(vals) / len(vals)
        if len(vals) < 2:
            return m, 0.0
        var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
        return m, math.sqrt(var)

    def sync_atten_from_band_ec25(self) -> None:
        """Set atten_db from EC25 band calibration (unknown bands → 0)."""
        self.atten_db = atten_db_for_band(self.band_eutra)

    def clear_measurement_ui_state(self) -> None:
        """Reset charts, counters, and stored RSSI when the channel is turned off."""
        self.chart_rssi_avg.clear()
        self.chart_rssi_sd.clear()
        self.rssi_history.clear()
        self.measurement_count = 0
        self.rssi_dbm = -80.0
        self.last_sample_at = None

    def record_rssi_sample(self, rssi_dbm: float) -> None:
        """Apply one modem measurement (+QRXFTM second field, dBm); stored RSSI = raw + atten_db (positive atten)."""
        if not self.channel_enabled:
            return
        self.rssi_dbm = float(rssi_dbm) + self.atten_db
        self.rssi_history.append(self.rssi_dbm)
        t = _now()
        self.last_sample_at = t
        avg, sd = self.rolling_mean_sd(_rssi_smooth_window())
        self.chart_rssi_avg.append((t, avg))
        self.chart_rssi_sd.append((t, sd))
        self.measurement_count += 1

    def is_stale(self, max_age_sec: float) -> bool:
        if self.last_sample_at is None:
            return True
        return (_now() - self.last_sample_at) > max(0.2, float(max_age_sec))

    def tick_mock(self) -> None:
        if not self.channel_enabled:
            return
        t = _now()
        base = -75 + 8 * math.sin(t * 0.7 + hash(self.prefix) % 7)
        rssi = base + (hash(str(int(t * 10))) % 100) / 30 - 1.5
        self.record_rssi_sample(rssi)

    def apply_rf_command(self) -> str | None:
        """Return AT string or None if invalid."""
        bq = eutra_band_to_quectel(self.band_eutra)
        wq = bw_mhz_to_quectel(self.bw_mhz)
        if bq is None or wq is None:
            return None
        cmd = build_qrxftm(
            mode=1,
            band_quectel=bq,
            earfcn=int(self.earfcn),
            antenna=0,
            lna_state=1,
            bw_quectel=wq,
        )
        return cmd


def _mean_sd_last(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    if len(values) < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return m, math.sqrt(var)


def _default_channels() -> dict[str, ChannelRuntime]:
    return {f"ch{i}": ChannelRuntime(f"ch{i}") for i in range(CHANNEL_COUNT)}


@dataclass
class AppRuntime:
    channels: dict[str, ChannelRuntime] = field(default_factory=_default_channels)
    at_log: deque[str] = field(default_factory=lambda: deque(maxlen=200))
    serial_rx_log: deque[str] = field(default_factory=lambda: deque(maxlen=200))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    modem_hw: str | None = None
    modem_fw: str | None = None
    modem_ident_at: float | None = None
    last_modem_rx_at: float | None = None
    qrxftm_timeout_streak: int = 0
    ftm_restricted_streak: int = 0
    # One entry per AT+QRXFTM sent per channel step; +QRXFTM lines consume in order.
    qrxftm_expect: deque[str] = field(default_factory=lambda: deque(maxlen=256))
    # Composit Power (all CC): linear sum of mW from enabled carriers' RSSI (dBm).
    _composite_ring: deque[float] = field(default_factory=lambda: deque(maxlen=512))
    composite_dbm: float | None = None
    composite_mw: float = 0.0
    carrier_count: int = 0
    composite_avg_10: float = 0.0
    composite_sd_10: float = 0.0
    chart_composite_avg: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=3600))
    chart_composite_sd: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=3600))
    chart_all_cc_rssi: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=3600))
    # Control panel: bar-gauge scale for dBm-like metrics (defaults -30 … +25 dBm).
    gauge_min: float | None = -30.0
    gauge_max: float | None = 25.0
    # Process start (wall clock) for control-panel UpTime.
    started_at: float = 0.0
    # Full QRXFTM scan rounds since deploy (control panel).
    scan_count: int = 0
    # Which channel (ch0…ch13) is currently being visited in the AT+QRXFTM round-robin (None between steps/rounds).
    scan_active_channel: str | None = None
    # When PT_MODEM_QRXFTM_SCAN=false but the UI still runs synthetic RSSI, rotate this for LED feedback only.
    scan_led_synthetic: str | None = None
    _scan_led_synth_i: int = 0

    def clear_scan_led_synthetic(self) -> None:
        self.scan_led_synthetic = None
        self._scan_led_synth_i = 0

    def advance_scan_led_synthetic(self) -> None:
        keys = [p for p in channel_prefixes() if self.channels[p].channel_enabled]
        if not keys:
            self.clear_scan_led_synthetic()
            return
        i = self._scan_led_synth_i % len(keys)
        self.scan_led_synthetic = keys[i]
        self._scan_led_synth_i = i + 1

    def _scan_led_only_if_enabled(self, ch: str | None) -> str | None:
        """Never light the scan LED for a disabled channel (stale TX/expect or race with UI)."""
        if ch is None or ch not in self.channels:
            return None
        return ch if self.channels[ch].channel_enabled else None

    def uptime_display(self) -> str:
        if self.started_at <= 0:
            return "—"
        return format_uptime_dhms(int(_now() - self.started_at))

    def watchdog_display(self) -> str:
        """Alternate + / − each second (Node-RED watchdog heartbeat)."""
        if self.started_at <= 0:
            return "—"
        return "+" if int(_now()) % 2 == 0 else "-"

    def register_qrxftm_expect(self, channel: str, repeat: int = 1) -> None:
        """Expect `repeat` +QRXFTM URCs for this channel (one per AT sent)."""
        for _ in range(repeat):
            self.qrxftm_expect.append(channel)

    def process_modem_measurement_line(self, text: str, kind: str) -> None:
        """Handle a single RX line under lock. Maps +QRXFTM to the channel awaiting a response."""
        up = text.upper()
        if kind == "ERR" and self.qrxftm_expect:
            if "RESTRICTED" in up and "FTM" in up:
                self.note_ftm_restricted()
            self.qrxftm_expect.popleft()
            return
        if kind != "URC" or "+QRXFTM" not in up:
            return
        rssi = parse_qrxftm_rssi_line(text)
        if rssi is None or not self.qrxftm_expect:
            return
        ch = self.qrxftm_expect.popleft()
        if ch not in self.channels:
            return
        ch_obj = self.channels[ch]
        if ch_obj.channel_enabled:
            # Any valid +QRXFTM sample means modem is in working RF test context.
            self.clear_ftm_restricted()
            ch_obj.record_rssi_sample(rssi)

    def note_modem_rx(self) -> None:
        self.last_modem_rx_at = _now()

    def note_qrxftm_step_ok(self) -> None:
        self.qrxftm_timeout_streak = 0

    def note_qrxftm_timeout(self) -> None:
        self.qrxftm_timeout_streak += 1

    def note_ftm_restricted(self) -> None:
        self.ftm_restricted_streak += 1

    def clear_ftm_restricted(self) -> None:
        self.ftm_restricted_streak = 0

    def modem_health(self) -> tuple[str, str]:
        if settings.mock_modem:
            return "ok", "MOCK modem"
        age = None if self.last_modem_rx_at is None else (_now() - self.last_modem_rx_at)
        if self.qrxftm_timeout_streak >= int(settings.modem_offline_timeout_streak):
            return "offline", "No modem response (AT timeout streak)"
        if age is not None and age >= float(settings.modem_offline_sec):
            return "offline", f"No serial RX for {int(age)}s"
        if self.qrxftm_timeout_streak >= int(settings.modem_degraded_timeout_streak):
            return "degraded", "Intermittent modem response (timeouts)"
        if age is None:
            return "degraded", "Waiting for modem RX"
        if age >= float(settings.modem_degraded_sec):
            return "degraded", f"RX gap {age:.1f}s"
        return "ok", "Receiving modem responses"

    def update_composite(self) -> None:
        t = _now()
        carriers: list[float] = []
        for p in channel_prefixes():
            ch = self.channels[p]
            if ch.channel_enabled and not ch.is_stale(settings.channel_stale_sec):
                carriers.append(ch.rssi_dbm)
        if not carriers:
            self.composite_dbm = None
            self.composite_mw = 0.0
            self.carrier_count = 0
            self.composite_avg_10 = 0.0
            self.composite_sd_10 = 0.0
            return
        total_mw = sum(10 ** (p / 10.0) for p in carriers)
        self.composite_dbm = 10.0 * math.log10(total_mw)
        self.composite_mw = total_mw
        self.carrier_count = len(carriers)
        assert self.composite_dbm is not None
        self._composite_ring.append(self.composite_dbm)
        cw = _composite_smooth_window()
        window = list(self._composite_ring)[-cw:]
        self.composite_avg_10, self.composite_sd_10 = _mean_sd_last(window)
        self.chart_composite_avg.append((t, self.composite_avg_10))
        self.chart_composite_sd.append((t, self.composite_sd_10))
        avgs: list[float] = []
        for p in channel_prefixes():
            ch = self.channels[p]
            if ch.channel_enabled:
                a, _ = ch.rolling_mean_sd(_rssi_smooth_window())
                avgs.append(a)
        if avgs:
            self.chart_all_cc_rssi.append((t, sum(avgs) / len(avgs)))

    def clear_charts(self) -> None:
        for p in channel_prefixes():
            ch = self.channels[p]
            ch.chart_rssi_avg.clear()
            ch.chart_rssi_sd.clear()
            ch.rssi_history.clear()
        self.chart_composite_avg.clear()
        self.chart_composite_sd.clear()
        self.chart_all_cc_rssi.clear()
        self._composite_ring.clear()
        self.qrxftm_expect.clear()

    def zero_gauges(self) -> None:
        """Push gauges low (NR used -999; we use a floor dBm)."""
        floor_db = -96.0
        for p in channel_prefixes():
            ch = self.channels[p]
            ch.rssi_dbm = floor_db
            ch.rssi_history.clear()
        self.update_composite()

    def apply_mno_common_preset(self, preset: MnoCommonPreset) -> None:
        """Apply band / EARFCN / BW / MNO from Node-RED Pre-load MNO Common (None skips field)."""
        keys = channel_prefixes()
        for i in range(CHANNEL_COUNT):
            ch = self.channels[keys[i]]
            if preset.earfcn[i] is not None:
                ch.earfcn = preset.earfcn[i]  # type: ignore[assignment]
            if preset.band_eutra[i] is not None:
                ch.band_eutra = preset.band_eutra[i]  # type: ignore[assignment]
            if preset.bw_mhz[i] is not None:
                ch.bw_mhz = preset.bw_mhz[i]  # type: ignore[assignment]
            if preset.mno[i] is not None:
                ch.mno = preset.mno[i]  # type: ignore[assignment]
        for p in keys:
            self.channels[p].sync_atten_from_band_ec25()

    def snapshot(self) -> dict[str, Any]:
        def pack_ch(ch: ChannelRuntime) -> dict[str, Any]:
            if not ch.channel_enabled:
                return {
                    "channel_enabled": ch.channel_enabled,
                    "band_eutra": ch.band_eutra,
                    "earfcn": ch.earfcn,
                    "bw_mhz": ch.bw_mhz,
                    "mno": ch.mno,
                    "atten_db": ch.atten_db,
                    "measurement_count": ch.measurement_count,
                    "rssi_dbm": None,
                    "rssi_avg": None,
                    "rssi_sd": None,
                    "chart_rssi_avg": [],
                    "chart_rssi_sd": [],
                    "stale": False,
                }
            stale = ch.is_stale(settings.channel_stale_sec)
            avg, sd = ch.rolling_mean_sd(_rssi_smooth_window())
            return {
                "channel_enabled": ch.channel_enabled,
                "band_eutra": ch.band_eutra,
                "earfcn": ch.earfcn,
                "bw_mhz": ch.bw_mhz,
                "mno": ch.mno,
                "atten_db": ch.atten_db,
                "measurement_count": ch.measurement_count,
                "rssi_dbm": None if stale else _round_dbm_half(ch.rssi_dbm),
                "rssi_avg": None if stale else _round_dbm_half(avg),
                "rssi_sd": None if stale else _round_dbm_half(sd),
                "chart_rssi_avg": _round_dbm_series(list(ch.chart_rssi_avg)[-400:]),
                "chart_rssi_sd": _round_dbm_series(list(ch.chart_rssi_sd)[-400:]),
                "stale": stale,
            }

        comp: dict[str, Any] = {
            "carrier_count": self.carrier_count,
            "composite_mw": round(self.composite_mw, 4),
            "composite_avg_10": _round_dbm_half(self.composite_avg_10),
            "composite_sd_10": _round_dbm_half(self.composite_sd_10),
            "chart_composite_avg": _round_dbm_series(list(self.chart_composite_avg)[-400:]),
            "chart_composite_sd": _round_dbm_series(list(self.chart_composite_sd)[-400:]),
            "chart_all_cc_rssi": _round_dbm_series(list(self.chart_all_cc_rssi)[-400:]),
        }
        if self.composite_dbm is not None:
            comp["composite_dbm"] = _round_dbm_half(self.composite_dbm)
        else:
            comp["composite_dbm"] = None

        keys = channel_prefixes()
        en = [self.channels[p].channel_enabled for p in keys]
        out: dict[str, Any] = {p: pack_ch(self.channels[p]) for p in keys}
        out["composite"] = comp
        out["at_log"] = list(self.at_log)[-50:]
        # LED: prefer channel awaiting +QRXFTM (HW); else scan loop's current ch; else synthetic spinner when scan is off.
        scan_led_channel: str | None = (
            self.qrxftm_expect[0] if self.qrxftm_expect else self.scan_active_channel
        )
        if scan_led_channel is None and not settings.modem_qrxftm_scan:
            scan_led_channel = self.scan_led_synthetic
        scan_led_channel = self._scan_led_only_if_enabled(scan_led_channel)
        out["controls"] = {
            "all_channels_on": bool(en) and all(en),
            "any_channel_on": any(en),
            "channels_enabled_count": sum(1 for x in en if x),
            "gauge_min": self.gauge_min,
            "gauge_max": self.gauge_max,
            "uptime": self.uptime_display(),
            "watchdog": self.watchdog_display(),
            "scan_count": self.scan_count,
            "modem_qrxftm_scan": settings.modem_qrxftm_scan,
            "scan_active_channel": scan_led_channel,
        }
        out["modem"] = {
            "hw": self.modem_hw,
            "fw": self.modem_fw,
            "identified": self.modem_ident_at,
            "last_rx_at": self.last_modem_rx_at,
            "timeout_streak": self.qrxftm_timeout_streak,
            "ftm_restricted_streak": self.ftm_restricted_streak,
        }
        state, status = self.modem_health()
        out["modem"]["state"] = state
        out["modem"]["status"] = status
        return out
