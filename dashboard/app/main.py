from __future__ import annotations

import asyncio
import copy
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict

from app.flows_inventory import (
    BW_MHZ_OPTIONS,
    CHANNEL_COUNT,
    MNO_DROPDOWN_LABELS,
    MnoCommonPreset,
    VALID_CHANNEL_PREFIXES,
    channel_prefixes,
    load_composite_widgets,
    load_controls_widgets,
    load_phase1_widgets,
    mno_preset_from_stored_dict,
    parse_mno_common_preset,
    resolved_mno_common_form_dict,
    widgets_by_channels,
)
from app import ec25_calibration
from app.dashboard_config import (
    apply_dashboard_config_file,
    apply_saved_channel_state,
    clamp_smooth_samples,
    config_path,
    consume_channels_state_from_file,
    get_mno_common_preset_stored_dict,
    save_dashboard_config_file,
    set_mno_common_preset_stored_dict,
)
from app.runtime_state import AppRuntime
from app.serial_worker import SerialWorker
from app.settings import settings


BASE_DIR = Path(__file__).resolve().parent
runtime = AppRuntime()
serial_worker: SerialWorker | None = None
_reader_task: asyncio.Task | None = None
ws_clients: list[WebSocket] = []
_widgets_channels: list[list[dict[str, Any]]] = [[] for _ in range(CHANNEL_COUNT)]
_widgets_composite: list[dict[str, Any]] = []
_widgets_controls: list[dict[str, Any]] = []
_mno_common_preset: MnoCommonPreset | None = None
_last_serial_reopen_attempt_at: float = 0.0
_ftm_rearming: bool = False


class ChannelPatch(BaseModel):
    channel_enabled: bool | None = None
    band_eutra: int | None = None
    earfcn: int | None = None
    bw_mhz: int | None = None
    mno: str | None = None
    atten_db: float | None = None


class AllChannelsBody(BaseModel):
    channel_enabled: bool


class GaugeRangePatch(BaseModel):
    """Set or clear (null) control-panel gauge scale. Omitted fields are left unchanged."""

    gauge_min: float | None = None
    gauge_max: float | None = None


class DashboardConfigBody(BaseModel):
    """Saved to dashboard_config.json; connection fields trigger serial reopen."""

    model_config = ConfigDict(extra="ignore")

    serial_port: str
    baudrate: int = 115200
    scan_channel_delay_sec: float = 1.0
    scan_round_delay_sec: float = 0.0
    ws_push_hz: float = 4.0
    rssi_smooth_samples: int = 5
    composite_smooth_samples: int = 10
    # Parallel arrays: band_eutra, earfcn, bw_mhz, mno — length CHANNEL_COUNT; null/omit field = unchanged on apply.
    mno_common_preset: dict[str, Any] | None = None
    # E-UTRA band → external attenuation dB (positive); replaces built-in EC25 table for listed bands.
    band_attenuation_db: dict[str, Any] | None = None
    gauge_min: float | None = None
    gauge_max: float | None = None


def _connection_public() -> dict[str, Any]:
    sw = serial_worker
    serial_open = False
    if sw is not None:
        if sw.mock:
            serial_open = True
        else:
            serial_open = bool(sw.ser is not None and getattr(sw.ser, "is_open", True))
    return {
        "serial_port": settings.serial_port,
        "baudrate": settings.baudrate,
        "mock_modem": settings.mock_modem,
        "serial_open": serial_open,
    }


def _snapshot() -> dict[str, Any]:
    snap = runtime.snapshot()
    snap["connection"] = _connection_public()
    conn = snap["connection"]
    if (not conn.get("mock_modem")) and (not conn.get("serial_open")):
        modem = snap.get("modem") or {}
        modem["state"] = "offline"
        modem["status"] = "Serial port not open"
        snap["modem"] = modem
    return snap


def _apply_dashboard_settings(body: DashboardConfigBody, rt: AppRuntime) -> None:
    patches = body.model_dump(exclude_unset=True)
    settings.serial_port = body.serial_port.strip() or settings.serial_port
    settings.baudrate = max(300, int(body.baudrate))
    settings.scan_channel_delay_sec = max(0.0, float(body.scan_channel_delay_sec))
    settings.scan_round_delay_sec = max(0.0, float(body.scan_round_delay_sec))
    settings.ws_push_hz = max(0.1, float(body.ws_push_hz))
    settings.rssi_smooth_samples = int(body.rssi_smooth_samples)
    settings.composite_smooth_samples = int(body.composite_smooth_samples)
    clamp_smooth_samples(settings)
    if body.mno_common_preset is not None:
        set_mno_common_preset_stored_dict(copy.deepcopy(body.mno_common_preset))
    if "band_attenuation_db" in patches and body.band_attenuation_db is not None:
        ec25_calibration.configure_band_attenuation(body.band_attenuation_db)
    for k in ("gauge_min", "gauge_max"):
        if k in patches:
            setattr(rt, k, getattr(body, k))


async def _reconnect_serial() -> None:
    """Reopen serial after connection fields changed; restarts RX reader when applicable."""
    global _reader_task
    if serial_worker is None:
        return
    if _reader_task is not None and not _reader_task.done():
        _reader_task.cancel()
        try:
            await _reader_task
        except asyncio.CancelledError:
            pass
        _reader_task = None

    await serial_worker.reopen(
        settings.serial_port,
        settings.baudrate,
        settings.mock_modem,
    )
    async with runtime.lock:
        if not settings.mock_modem and serial_worker.ser is None:
            runtime.at_log.append(
                f"[mc-dspm] Reconnect failed — port {settings.serial_port} @ {settings.baudrate} baud. "
                "No live modem samples until the port is available."
            )
        else:
            runtime.at_log.append(
                f"[mc-dspm] Reconnected — port {settings.serial_port} @ {settings.baudrate} baud, "
                f"MOCK={settings.mock_modem}."
            )
    if not settings.mock_modem and serial_worker.ser is not None:
        await _modem_qrftestmode_prep()
        asyncio.create_task(_probe_modem_identity())
        _reader_task = asyncio.create_task(serial_worker.reader_loop())


async def _ensure_serial_connected() -> None:
    """Best-effort reconnect loop for HW mode when COM port is busy/unavailable."""
    global _last_serial_reopen_attempt_at
    if settings.mock_modem or serial_worker is None:
        return
    sw = serial_worker
    if sw.ser is not None and getattr(sw.ser, "is_open", True):
        return
    now = time.time()
    interval = max(0.5, float(settings.serial_reconnect_interval_sec))
    if (now - _last_serial_reopen_attempt_at) < interval:
        return
    _last_serial_reopen_attempt_at = now
    await _reconnect_serial()


def _line_indicates_ftm_restricted(text: str) -> bool:
    up = (text or "").strip().upper()
    return ("RESTRICTED" in up) and ("FTM" in up)


async def _try_rearm_ftm(reason: str) -> bool:
    """Attempt to restore modem FTM state after reconnect/resume and probe with AT+QRXFTM?."""
    global _ftm_rearming
    if _ftm_rearming:
        return False
    if settings.mock_modem or serial_worker is None or serial_worker.ser is None:
        return False
    _ftm_rearming = True
    try:
        async with runtime.lock:
            runtime.at_log.append(f"[mc-dspm] Re-arming FTM ({reason}) ...")
        await _modem_qrftestmode_prep()
        # Probe with lightweight command that should succeed in FTM context.
        probe = await _run_at_collect_lines("AT+QRXFTM?", timeout_sec=1.8)
        ok = any("QRXFTM" in (ln or "").upper() for ln in probe) and not any(
            _line_indicates_ftm_restricted(ln) for ln in probe
        )
        async with runtime.lock:
            if ok:
                runtime.clear_ftm_restricted()
                runtime.at_log.append("[mc-dspm] FTM re-armed successfully.")
            else:
                runtime.at_log.append("[mc-dspm] FTM re-arm did not confirm; will retry on next restricted response.")
        return ok
    except Exception as e:
        async with runtime.lock:
            runtime.at_log.append(f"[mc-dspm] FTM re-arm failed: {e!r}")
        return False
    finally:
        _ftm_rearming = False


async def _broadcast() -> None:
    dead: list[WebSocket] = []
    payload = json.dumps(_snapshot())
    for ws in ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in ws_clients:
            ws_clients.remove(ws)


async def _modem_qrftestmode_prep() -> None:
    """Match Node-RED: on deploy, AT+QRFTESTMODE=0 then after 2s AT+QRFTESTMODE=1 to serial."""
    if settings.mock_modem or serial_worker is None or serial_worker.ser is None:
        return
    if not settings.modem_prep_qrftestmode:
        return
    await asyncio.sleep(0.05)
    sw = serial_worker
    cmd0 = "AT+QRFTESTMODE=0"
    cmd1 = "AT+QRFTESTMODE=1"
    async with runtime.lock:
        runtime.at_log.append(f"> TX [modem-prep] {cmd0}")
    sw.enqueue(cmd0)
    await asyncio.sleep(max(0.0, settings.modem_prep_delay_sec))
    async with runtime.lock:
        runtime.at_log.append(f"> TX [modem-prep] {cmd1}")
    sw.enqueue(cmd1)


def _clean_modem_id_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for raw in lines:
        s = (raw or "").strip()
        if not s:
            continue
        up = s.upper()
        if up in ("OK", "ERROR"):
            continue
        if up.startswith("+CME ERROR") or up.startswith("+CMS ERROR"):
            continue
        out.append(s)
    return out


async def _await_new_rx_lines(start_len: int, timeout_sec: float) -> list[str]:
    """Wait for serial_rx_log to grow; return new raw lines."""
    deadline = time.time() + max(0.05, float(timeout_sec))
    while time.time() < deadline:
        async with runtime.lock:
            cur = list(runtime.serial_rx_log)
        if len(cur) > start_len:
            return cur[start_len:]
        await asyncio.sleep(0.05)
    return []


async def _run_at_collect_lines(cmd: str, timeout_sec: float = 1.5) -> list[str]:
    """Send AT and collect subsequent RX lines until OK/ERROR/CME or timeout."""
    sw = serial_worker
    if settings.mock_modem or sw is None or sw.ser is None:
        return []
    async with runtime.lock:
        start_len = len(runtime.serial_rx_log)
        runtime.at_log.append(f"> TX [id] {cmd}")
    sw.enqueue(cmd)
    collected: list[str] = []
    deadline = time.time() + max(0.2, float(timeout_sec))
    while time.time() < deadline:
        new_lines = await _await_new_rx_lines(start_len, timeout_sec=0.35)
        if new_lines:
            collected.extend(new_lines)
            start_len += len(new_lines)
            up = "\n".join(new_lines).upper()
            if "\nOK" in ("\n" + up) or "\nERROR" in ("\n" + up) or "CME ERROR" in up:
                break
        else:
            await asyncio.sleep(0.05)
    return collected


def _pick_hw_from_ati(lines: list[str]) -> str | None:
    cleaned = _clean_modem_id_lines(lines)
    if not cleaned:
        return None
    for s in cleaned:
        up = s.upper()
        if "EC25" in up or "QUECTEL" in up:
            return s
    return cleaned[0]


def _pick_fw_from_cgmr(lines: list[str]) -> str | None:
    cleaned = _clean_modem_id_lines(lines)
    if not cleaned:
        return None
    return cleaned[0]


async def _probe_modem_identity() -> None:
    """Query modem HW/FW once and publish to runtime snapshot."""
    if settings.mock_modem or serial_worker is None or serial_worker.ser is None:
        async with runtime.lock:
            runtime.modem_hw = "MOCK modem"
            runtime.modem_fw = None
            runtime.modem_ident_at = time.time()
        return
    ati_lines = await _run_at_collect_lines("ATI", timeout_sec=2.0)
    cgmr_lines = await _run_at_collect_lines("AT+CGMR", timeout_sec=2.0)
    hw = _pick_hw_from_ati(ati_lines)
    fw = _pick_fw_from_cgmr(cgmr_lines)
    async with runtime.lock:
        runtime.modem_hw = hw
        runtime.modem_fw = fw
        runtime.modem_ident_at = time.time()
        if hw or fw:
            runtime.at_log.append(f"[mc-dspm] Modem identity: hw={hw or '—'}, fw={fw or '—'}.")


async def _enqueue_qrxftm(channel: str, log_tag: str) -> tuple[bool, str | None]:
    """Build AT+QRXFTM from channel state; send once (one measurement step per channel visit)."""
    async with runtime.lock:
        cmd = runtime.channels[channel].apply_rf_command()
        if not cmd:
            return False, None
        tx = cmd.strip().replace("\r", " ").replace("\n", " ").strip()
        runtime.at_log.append(f"> TX [{log_tag}] {tx}")
        cmd_stripped = cmd.strip()
        if (
            not settings.mock_modem
            and serial_worker is not None
            and serial_worker.ser is not None
        ):
            runtime.register_qrxftm_expect(channel, 1)
    assert serial_worker is not None
    serial_worker.enqueue(cmd)
    return True, cmd_stripped


async def _await_qrxftm_consumed(channel: str, timeout_sec: float) -> bool:
    """
    Wait until the next expected +QRXFTM entry for `channel` is consumed.

    Prevents cross-channel RSSI "bleed" when URCs are delayed/missing and the expect queue desynchronises.
    Returns True if consumed; False on timeout (and drops one pending expect to re-sync).
    """
    deadline = time.time() + max(0.05, float(timeout_sec))
    while time.time() < deadline:
        async with runtime.lock:
            head = runtime.qrxftm_expect[0] if runtime.qrxftm_expect else None
            if head != channel:
                runtime.note_qrxftm_step_ok()
                return True
        await asyncio.sleep(0.02)
    # Timed out: drop one pending expect if it is still this channel so later URCs don't get mis-attributed.
    async with runtime.lock:
        head = runtime.qrxftm_expect[0] if runtime.qrxftm_expect else None
        if head == channel:
            runtime.qrxftm_expect.popleft()
            runtime.note_qrxftm_timeout()
            runtime.at_log.append(
                f"[mc-dspm] +QRXFTM timeout for {channel}; dropped one pending expect to avoid cross-channel bleed."
            )
    return False


async def _channel_measurement_loop() -> None:
    """Round-robin: one AT+QRXFTM per enabled channel per pass (ch0 → ch1 → …), then repeat."""
    if not settings.modem_qrxftm_scan:
        return
    async with runtime.lock:
        runtime.at_log.append(
            "[mc-dspm] AT+QRXFTM round-robin: one command per enabled channel per pass; "
            f"PT_SCAN_CHANNEL_DELAY_SEC={settings.scan_channel_delay_sec}s between channels."
        )
    while True:
        try:
            sw = serial_worker
            if sw is None:
                await asyncio.sleep(0.5)
                continue
            # No modem connected and not in mock mode: back off to avoid busy-spinning.
            if not settings.mock_modem and sw.ser is None:
                await _ensure_serial_connected()
                await asyncio.sleep(2.0)
                continue
            any_sent = False
            for p in channel_prefixes():
                async with runtime.lock:
                    if not runtime.channels[p].channel_enabled:
                        continue
                    runtime.scan_active_channel = p
                await _broadcast()
                ok, _ = await _enqueue_qrxftm(p, f"scan {p}")
                if ok:
                    any_sent = True
                    # On real modem: wait for +QRXFTM to be consumed (or timeout) before advancing.
                    if (not settings.mock_modem) and sw.ser is not None:
                        got_consumed = await _await_qrxftm_consumed(
                            p,
                            timeout_sec=max(0.2, float(settings.scan_channel_delay_sec or 0.0) + 0.8),
                        )
                        if not got_consumed:
                            ftm_restricted = False
                            async with runtime.lock:
                                recent = list(runtime.serial_rx_log)[-8:]
                                ftm_restricted = any(_line_indicates_ftm_restricted(x) for x in recent)
                                if ftm_restricted:
                                    runtime.note_ftm_restricted()
                                    runtime.at_log.append(
                                        "[mc-dspm] Modem reported FTM restriction; attempting QRFTESTMODE re-arm."
                                    )
                            if ftm_restricted:
                                await _try_rearm_ftm("restricted to FTM")
                        else:
                            # Restricted-to-FTM can consume the expected slot quickly (no timeout), so
                            # also trigger re-arm from the streak counter set in runtime RX processing.
                            need_rearm = False
                            async with runtime.lock:
                                if runtime.ftm_restricted_streak > 0:
                                    need_rearm = True
                                    runtime.at_log.append(
                                        "[mc-dspm] FTM restriction detected on modem response; attempting QRFTESTMODE re-arm."
                                    )
                            if need_rearm:
                                await _try_rearm_ftm("restricted to FTM")
                        # Optional extra pacing after consumption (keeps modem calm on some FW).
                        if settings.scan_channel_delay_sec > 0:
                            await asyncio.sleep(settings.scan_channel_delay_sec)
            async with runtime.lock:
                runtime.scan_active_channel = None
                runtime.scan_count += 1
            await _broadcast()
            if any_sent:
                await asyncio.sleep(max(0.0, settings.scan_round_delay_sec))
            else:
                await asyncio.sleep(0.5)
        except Exception as e:
            async with runtime.lock:
                runtime.at_log.append(f"[mc-dspm] scan loop error: {e!r}")
                runtime.scan_active_channel = None
            await asyncio.sleep(1.0)


async def _startup_rf() -> None:
    """QRFTESTMODE once on real modem, then start background QRXFTM round-robin (one TX per channel per pass)."""
    if not settings.mock_modem and serial_worker is not None and serial_worker.ser is not None:
        await _modem_qrftestmode_prep()
    asyncio.create_task(_channel_measurement_loop())


def _use_synthetic_rssi() -> bool:
    """Simulated RSSI only in explicit mock mode (PT_MOCK_MODEM=true)."""
    return settings.mock_modem


async def _tick_loop() -> None:
    interval = max(0.05, 1.0 / settings.ws_push_hz)
    while True:
        await asyncio.sleep(interval)
        await _ensure_serial_connected()
        async with runtime.lock:
            if settings.modem_qrxftm_scan:
                runtime.clear_scan_led_synthetic()
            elif _use_synthetic_rssi():
                runtime.advance_scan_led_synthetic()
            else:
                runtime.clear_scan_led_synthetic()
            if _use_synthetic_rssi():
                for p in channel_prefixes():
                    runtime.channels[p].tick_mock()
            runtime.update_composite()
        await _broadcast()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global serial_worker, _reader_task, _widgets_channels, _widgets_composite, _widgets_controls, _mno_common_preset
    apply_dashboard_config_file(settings, runtime)
    runtime.started_at = time.time()
    if settings.flows_json.is_file():
        all_w = load_phase1_widgets(settings.flows_json)
        _widgets_channels = widgets_by_channels(all_w)
        _widgets_composite = load_composite_widgets(settings.flows_json)
        _widgets_controls = load_controls_widgets(settings.flows_json)
        flows_mno = parse_mno_common_preset(settings.flows_json)
    else:
        _widgets_channels = [[] for _ in range(CHANNEL_COUNT)]
        _widgets_composite = []
        _widgets_controls = []
        flows_mno = None

    stored_mno = get_mno_common_preset_stored_dict()
    if stored_mno is not None:
        _mno_common_preset = mno_preset_from_stored_dict(stored_mno)
    else:
        _mno_common_preset = flows_mno

    async with runtime.lock:
        for p in channel_prefixes():
            runtime.channels[p].channel_enabled = True
        if _mno_common_preset is not None:
            runtime.apply_mno_common_preset(_mno_common_preset)
            if stored_mno is not None:
                runtime.at_log.append("[mc-dspm] MNO Common preset applied from dashboard config (startup).")
            else:
                runtime.at_log.append("[mc-dspm] MNO Common preset applied from flows.json (startup).")
        else:
            for p in channel_prefixes():
                runtime.channels[p].sync_atten_from_band_ec25()
        saved_ch = consume_channels_state_from_file()
        if saved_ch:
            apply_saved_channel_state(runtime, saved_ch)
            runtime.at_log.append(
                "[mc-dspm] Per-channel enable/RF state restored from dashboard_config.json (`channels`)."
            )

    serial_worker = SerialWorker(
        runtime,
        settings.serial_port,
        settings.baudrate,
        settings.mock_modem,
    )
    await serial_worker.start()
    asyncio.create_task(serial_worker.writer_loop())
    if not settings.mock_modem and serial_worker.ser is not None:
        _reader_task = asyncio.create_task(serial_worker.reader_loop())
    asyncio.create_task(_probe_modem_identity())
    asyncio.create_task(_startup_rf())
    asyncio.create_task(_tick_loop())
    async with runtime.lock:
        if settings.mock_modem:
            rx_note = " Synthetic RSSI in UI tick; TX gets mock OK."
        elif serial_worker.ser is not None:
            rx_note = (
                " RSSI from +QRXFTM lines (2nd field, dBm); synthetic RSSI off."
            )
        else:
            rx_note = (
                " Serial open failed — no live modem samples until the port is available."
            )
        runtime.at_log.append(
            f"[mc-dspm] Ready — port {settings.serial_port} @ {settings.baudrate} baud, "
            f"MOCK={settings.mock_modem}.{rx_note}"
        )
    yield
    if serial_worker and serial_worker.ser:
        serial_worker.ser.close()


app = FastAPI(
    title="Multi-Channel LTE (4G) Downlink Signal Power Monitor",
    version="1.0-beta",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    async with runtime.lock:
        snap = _snapshot()
    channel_panels = [
        {
            "prefix": f"ch{i}",
            "title": f"Channel {i}",
            "widgets": _widgets_channels[i],
        }
        for i in range(CHANNEL_COUNT)
    ]
    mno_form = resolved_mno_common_form_dict(
        get_mno_common_preset_stored_dict(),
        settings.flows_json,
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "channel_panels": channel_panels,
            "composite_widgets": _widgets_composite,
            "controls_widgets": _widgets_controls,
            "snap": snap,
            "snap_json": json.dumps(snap),
            "settings": settings,
            "channel_prefixes": channel_prefixes(),
            "channel_indices": list(range(CHANNEL_COUNT)),
            "mno_common_form": mno_form,
            "mno_options": MNO_DROPDOWN_LABELS,
            "bw_mhz_options": BW_MHZ_OPTIONS,
            "band_atten_rows": ec25_calibration.band_atten_rows_for_ui(),
            "dashboard_config_path": str(config_path()),
        },
    )


@app.get("/api/config/dashboard")
async def get_dashboard_config() -> dict[str, Any]:
    async with runtime.lock:
        gm, gx = (runtime.gauge_min, runtime.gauge_max)
    return {
        "ok": True,
        "serial_port": settings.serial_port,
        "baudrate": settings.baudrate,
        "mock_modem": settings.mock_modem,
        "scan_channel_delay_sec": settings.scan_channel_delay_sec,
        "scan_round_delay_sec": settings.scan_round_delay_sec,
        "ws_push_hz": settings.ws_push_hz,
        "rssi_smooth_samples": settings.rssi_smooth_samples,
        "composite_smooth_samples": settings.composite_smooth_samples,
        "mno_common_preset": resolved_mno_common_form_dict(
            get_mno_common_preset_stored_dict(),
            settings.flows_json,
        ),
        "band_attenuation_db": ec25_calibration.band_atten_dict_for_api(),
        "gauge_min": gm,
        "gauge_max": gx,
        "config_path": str(config_path()),
    }


@app.post("/api/config/dashboard")
async def post_dashboard_config(body: DashboardConfigBody) -> dict[str, Any]:
    global _mno_common_preset
    prev = (settings.serial_port, settings.baudrate)
    async with runtime.lock:
        _apply_dashboard_settings(body, runtime)
        applied_mno_runtime = False
        if body.mno_common_preset is not None:
            _mno_common_preset = mno_preset_from_stored_dict(
                copy.deepcopy(body.mno_common_preset)
            )
            if _mno_common_preset is not None:
                runtime.apply_mno_common_preset(_mno_common_preset)
                applied_mno_runtime = True
                runtime.at_log.append(
                    "[mc-dspm] MNO Common preset applied to runtime from Settings save."
                )
        if not applied_mno_runtime:
            for p in channel_prefixes():
                runtime.channels[p].sync_atten_from_band_ec25()
    save_dashboard_config_file(settings, runtime)
    conn_changed = prev != (settings.serial_port, settings.baudrate)
    if conn_changed:
        await _reconnect_serial()
    await _broadcast()
    return {"ok": True, **_snapshot()}


def _patch_channel(prefix: str, p: ChannelPatch) -> None:
    ch = runtime.channels[prefix]
    if p.channel_enabled is not None:
        ch.channel_enabled = p.channel_enabled
        if not ch.channel_enabled:
            ch.clear_measurement_ui_state()
            if runtime.scan_active_channel == prefix:
                runtime.scan_active_channel = None
    if p.band_eutra is not None:
        ch.band_eutra = int(p.band_eutra)
        ch.sync_atten_from_band_ec25()
    if p.earfcn is not None:
        ch.earfcn = int(p.earfcn)
    if p.bw_mhz is not None:
        ch.bw_mhz = int(p.bw_mhz)
    if p.mno is not None:
        ch.mno = p.mno
    if p.atten_db is not None:
        ch.atten_db = float(p.atten_db)


@app.patch("/api/runtime/gauge-ranges")
async def patch_gauge_ranges(body: GaugeRangePatch) -> dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    async with runtime.lock:
        if "gauge_min" in data:
            runtime.gauge_min = data["gauge_min"]
        if "gauge_max" in data:
            runtime.gauge_max = data["gauge_max"]
        snap = _snapshot()
    save_dashboard_config_file(settings, runtime)
    await _broadcast()
    return {"ok": True, **snap}


@app.patch("/api/runtime/{channel}")
async def patch_runtime(channel: str, body: ChannelPatch) -> dict[str, Any]:
    if channel not in VALID_CHANNEL_PREFIXES:
        return {"ok": False, "error": "bad channel"}
    async with runtime.lock:
        _patch_channel(channel, body)
        snap = _snapshot()
    save_dashboard_config_file(settings, runtime)
    await _broadcast()
    return {"ok": True, **snap}


@app.post("/api/runtime/{channel}/apply-at")
async def apply_at(channel: str) -> dict[str, Any]:
    """Optional manual trigger; normal operation uses automatic scan loop."""
    if channel not in VALID_CHANNEL_PREFIXES:
        return {"ok": False}
    ok, cmd_s = await _enqueue_qrxftm(channel, channel)
    if not ok:
        return {"ok": False, "error": "invalid band or bandwidth mapping"}
    async with runtime.lock:
        snap = _snapshot()
    await _broadcast()
    return {"ok": True, "cmd": cmd_s or "", **snap}


@app.post("/api/runtime/all-channels")
async def all_channels(body: AllChannelsBody) -> dict[str, Any]:
    async with runtime.lock:
        for p in channel_prefixes():
            runtime.channels[p].channel_enabled = body.channel_enabled
        if not body.channel_enabled:
            for p in channel_prefixes():
                runtime.channels[p].clear_measurement_ui_state()
            runtime.scan_active_channel = None
            runtime.clear_scan_led_synthetic()
        snap = _snapshot()
    save_dashboard_config_file(settings, runtime)
    await _broadcast()
    return {"ok": True, **snap}


@app.post("/api/runtime/clear-charts")
async def clear_charts() -> dict[str, Any]:
    async with runtime.lock:
        runtime.clear_charts()
        snap = _snapshot()
    await _broadcast()
    return {"ok": True, **snap}


@app.post("/api/runtime/zero-gauges")
async def zero_gauges() -> dict[str, Any]:
    async with runtime.lock:
        runtime.zero_gauges()
        snap = _snapshot()
    await _broadcast()
    return {"ok": True, **snap}


@app.post("/api/runtime/preload-mno-common")
async def preload_mno_common() -> dict[str, Any]:
    if _mno_common_preset is None:
        return {
            "ok": False,
            "error": "MNO Common preset not configured (save a table in Settings or add flows.json).",
        }
    async with runtime.lock:
        runtime.apply_mno_common_preset(_mno_common_preset)
        snap = _snapshot()
    save_dashboard_config_file(settings, runtime)
    await _broadcast()
    return {"ok": True, **snap}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    ws_clients.append(ws)
    try:
        await ws.send_text(json.dumps(_snapshot()))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)
