# Powertest

**GitHub:** [Cloolalang/Multi-Channel-Cellular-downlink-signal-power-monitor](https://github.com/Cloolalang/Multi-Channel-Cellular-downlink-signal-power-monitor)

This repository contains **Powertest**, a small stack for RF / modem bench work. The active web app is a **FastAPI** dashboard under `powertest_dashboard/` that talks to a Quectel modem over serial (or a mock for UI development), syncs layout from `flows.json`, and pushes live state over WebSockets.

There is also **Node-RED** related material (`flows.json`, `package.json`, `node_modules/`) used as reference or exported flows; day-to-day local development is usually the Python dashboard only.

## Prerequisites

- **Python 3.10+** (3.11+ recommended)
- A **serial port** and Quectel modem when not using mock mode (Windows: e.g. `COM40`)

## Setup

1. **Clone** this repo (or copy it) so the layout stays:

   ```bash
   git clone https://github.com/Cloolalang/Multi-Channel-Cellular-downlink-signal-power-monitor.git
   cd Multi-Channel-Cellular-downlink-signal-power-monitor
   ```

   - `flows.json` at the **repository root**
   - `powertest_dashboard/` next to it (the app resolves `flows.json` relative to that folder)

2. **Create a virtual environment** (recommended):

   ```powershell
   cd powertest_dashboard
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   On Linux or macOS:

   ```bash
   cd powertest_dashboard
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Optional — environment file**  
   Create `powertest_dashboard/.env` if you want to override defaults. All variables use the prefix **`PT_`** (see table below). Pydantic loads `.env` from the **current working directory** when you start the app, so run Uvicorn from `powertest_dashboard/` as shown below.

## Configuration (`PT_*`)

| Variable | Default | Notes |
|----------|---------|--------|
| `PT_SERIAL_PORT` | `COM40` | Serial device (e.g. `/dev/ttyUSB0` on Linux) |
| `PT_BAUDRATE` | `115200` | Modem baud rate |
| `PT_MOCK_MODEM` | `false` | Set `true` for UI work without hardware (synthetic RSSI, fake OK on TX) |
| `PT_WS_PUSH_HZ` | `4` | WebSocket snapshot cadence (Hz) |
| `PT_SCAN_CHANNEL_DELAY_SEC` | `1` | Delay between `AT+QRXFTM` per channel on real serial (0 = no pause; may miss RSSI) |
| `PT_SCAN_ROUND_DELAY_SEC` | `0` | Pause after each full channel round before the next |
| `PT_MODEM_PREP_QRFTESTMODE` | `true` | Run `AT+QRFTESTMODE` prep after opening the port |
| `PT_MODEM_PREP_DELAY_SEC` | `2` | Delay used in that prep sequence |
| `PT_MODEM_QRXFTM_SCAN` | `true` | Continuous round-robin `AT+QRXFTM` per enabled channel |
| `PT_FLOWS_JSON` | *(auto)* | Override path to `flows.json` if needed |

**Dashboard Settings tab:** Open the **Settings** tab in the UI to set the COM port, baud rate, mock mode, and timing (scan delays, WebSocket Hz). Values are saved to `powertest_dashboard/dashboard_config.json` and override the same options from the environment for that process. Changing the serial port or mock mode **reopens** the port without restarting Uvicorn.

## Run the dashboard

From **`powertest_dashboard/`**:

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000** in a browser.

For LAN access, bind explicitly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Quick start without hardware:**

```bash
set PT_MOCK_MODEM=true
uvicorn app.main:app --reload
```

(PowerShell: `$env:PT_MOCK_MODEM="true"`)

## Project layout (short)

| Path | Role |
|------|------|
| `powertest_dashboard/app/` | FastAPI app, templates, static assets, serial worker |
| `flows.json` | Widget / flow metadata consumed by the dashboard |

## TODO

- Add a **smoothing** control in the Settings tab (e.g. adjustable filtering for RSSI/gauges/charts so the UI can trade responsiveness vs. stability).
