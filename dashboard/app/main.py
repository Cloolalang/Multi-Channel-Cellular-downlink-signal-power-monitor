from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.flows_inventory import (
    CHANNEL_COUNT,
    MnoCommonPreset,
    VALID_CHANNEL_PREFIXES,
    channel_prefixes,
    load_composite_widgets,
    load_controls_widgets,
    load_phase1_widgets,
    parse_mno_common_preset,
    widgets_by_channels,
)
from app.dashboard_config import (
    apply_dashboard_config_file,
    config_path,
    save_dashboard_config_file,
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
    gauge_seg1: float | None = None
    gauge_seg2: float | None = None


class DashboardConfigBody(BaseModel):
    """Saved to dashboard_config.json; connection fields trigger serial reopen."""

    serial_port: str
    baudrate: int = 115200
    mock_modem: bool = False
    scan_channel_delay_sec: float = 1.0
    scan_round_delay_sec: float = 0.0
    ws_push_hz: float = 4.0


def _connection_public() -> dict[str, Any]:
    sw = serial_worker
    serial_open = False
    if sw is not None:
        if sw.mock:
            serial_open = True
        else:
            serial_open = sw.ser is not None
    return {
        "serial_port": settings.serial_port,
        "baudrate": settings.baudrate,
        "mock_modem": settings.mock_modem,
        "serial_open": serial_open,
    }


def _snapshot() -> dict[str, Any]:
    snap = runtime.snapshot()
    snap["connection"] = _connection_public()
    return snap


def _apply_dashboard_settings(body: DashboardConfigBody) -> None:
    settings.serial_port = body.serial_port.strip() or settings.serial_port
    settings.baudrate = max(300, int(body.baudrate))
    settings.mock_modem = bool(body.mock_modem)
    settings.scan_channel_delay_sec = max(0.0, float(body.scan_channel_delay_sec))
    settings.scan_round_delay_sec = max(0.0, float(body.scan_round_delay_sec))
    settings.ws_push_hz = max(0.1, float(body.ws_push_hz))


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
        runtime.at_log.append(
            f"[mc-dspm] Reconnected — port {settings.serial_port} @ {settings.baudrate} baud, "
            f"MOCK={settings.mock_modem}."
        )
        if not settings.mock_modem and serial_worker.ser is None:
            runtime.at_log.append(
                "[mc-dspm] Serial open failed — UI uses synthetic RSSI until the port is available."
            )
    if not settings.mock_modem and serial_worker.ser is not None:
        await _modem_qrftestmode_prep()
        _reader_task = asyncio.create_task(serial_worker.reader_loop())


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
            any_sent = False
            for p in channel_prefixes():
                async with runtime.lock:
                    if not runtime.channels[p].channel_enabled:
                        continue
                ok, _ = await _enqueue_qrxftm(p, f"scan {p}")
                if ok:
                    any_sent = True
                    # Pace TX so the modem can return +QRXFTM/OK before the next channel (avoids queue desync).
                    if (
                        not settings.mock_modem
                        and sw.ser is not None
                        and settings.scan_channel_delay_sec > 0
                    ):
                        await asyncio.sleep(settings.scan_channel_delay_sec)
            async with runtime.lock:
                runtime.scan_count += 1
            await _broadcast()
            if any_sent:
                await asyncio.sleep(max(0.0, settings.scan_round_delay_sec))
            else:
                await asyncio.sleep(0.5)
        except Exception as e:
            async with runtime.lock:
                runtime.at_log.append(f"[mc-dspm] scan loop error: {e!r}")
            await asyncio.sleep(1.0)


async def _startup_rf() -> None:
    """QRFTESTMODE once on real modem, then start background QRXFTM round-robin (one TX per channel per pass)."""
    if not settings.mock_modem and serial_worker is not None and serial_worker.ser is not None:
        await _modem_qrftestmode_prep()
    asyncio.create_task(_channel_measurement_loop())


def _use_synthetic_rssi() -> bool:
    """Simulated RSSI only when mock mode or serial port did not open."""
    return (
        settings.mock_modem
        or serial_worker is None
        or serial_worker.ser is None
    )


async def _tick_loop() -> None:
    interval = max(0.05, 1.0 / settings.ws_push_hz)
    while True:
        await asyncio.sleep(interval)
        async with runtime.lock:
            if _use_synthetic_rssi():
                for p in channel_prefixes():
                    runtime.channels[p].tick_mock()
            runtime.update_composite()
        await _broadcast()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global serial_worker, _reader_task, _widgets_channels, _widgets_composite, _widgets_controls, _mno_common_preset
    apply_dashboard_config_file(settings)
    runtime.started_at = time.time()
    if settings.flows_json.is_file():
        all_w = load_phase1_widgets(settings.flows_json)
        _widgets_channels = widgets_by_channels(all_w)
        _widgets_composite = load_composite_widgets(settings.flows_json)
        _widgets_controls = load_controls_widgets(settings.flows_json)
        _mno_common_preset = parse_mno_common_preset(settings.flows_json)
    else:
        _widgets_channels = [[] for _ in range(CHANNEL_COUNT)]
        _widgets_composite = []
        _widgets_controls = []
        _mno_common_preset = None

    async with runtime.lock:
        for p in channel_prefixes():
            runtime.channels[p].channel_enabled = True
        if _mno_common_preset is not None:
            runtime.apply_mno_common_preset(_mno_common_preset)
            runtime.at_log.append("[mc-dspm] MNO Common preset applied from flows.json (startup).")
        else:
            for p in channel_prefixes():
                runtime.channels[p].sync_atten_from_band_ec25()

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
                " Serial open failed — UI uses synthetic RSSI until the port is available."
            )
        runtime.at_log.append(
            f"[mc-dspm] Ready — port {settings.serial_port} @ {settings.baudrate} baud, "
            f"MOCK={settings.mock_modem}.{rx_note}"
        )
    yield
    if serial_worker and serial_worker.ser:
        serial_worker.ser.close()


app = FastAPI(
    title="Multi-Channel Cellular Downlink Signal Power Monitor",
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
            "dashboard_config_path": str(config_path()),
        },
    )


@app.get("/api/config/dashboard")
async def get_dashboard_config() -> dict[str, Any]:
    return {
        "ok": True,
        "serial_port": settings.serial_port,
        "baudrate": settings.baudrate,
        "mock_modem": settings.mock_modem,
        "scan_channel_delay_sec": settings.scan_channel_delay_sec,
        "scan_round_delay_sec": settings.scan_round_delay_sec,
        "ws_push_hz": settings.ws_push_hz,
        "config_path": str(config_path()),
    }


@app.post("/api/config/dashboard")
async def post_dashboard_config(body: DashboardConfigBody) -> dict[str, Any]:
    prev = (settings.serial_port, settings.baudrate, settings.mock_modem)
    _apply_dashboard_settings(body)
    save_dashboard_config_file(settings)
    conn_changed = prev != (settings.serial_port, settings.baudrate, settings.mock_modem)
    if conn_changed:
        await _reconnect_serial()
    await _broadcast()
    return {"ok": True, **_snapshot()}


def _patch_channel(prefix: str, p: ChannelPatch) -> None:
    ch = runtime.channels[prefix]
    if p.channel_enabled is not None:
        ch.channel_enabled = p.channel_enabled
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
        if "gauge_seg1" in data:
            runtime.gauge_seg1 = data["gauge_seg1"]
        if "gauge_seg2" in data:
            runtime.gauge_seg2 = data["gauge_seg2"]
        snap = _snapshot()
    await _broadcast()
    return {"ok": True, **snap}


@app.patch("/api/runtime/{channel}")
async def patch_runtime(channel: str, body: ChannelPatch) -> dict[str, Any]:
    if channel not in VALID_CHANNEL_PREFIXES:
        return {"ok": False, "error": "bad channel"}
    async with runtime.lock:
        _patch_channel(channel, body)
        snap = _snapshot()
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
        snap = _snapshot()
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
        return {"ok": False, "error": "MNO Common preset not available (check flows.json)"}
    async with runtime.lock:
        runtime.apply_mno_common_preset(_mno_common_preset)
        snap = _snapshot()
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
