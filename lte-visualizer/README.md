# Bands & Channels visualiser

Standalone HTML LTE channel visualization tool.

Current development scope is intentionally limited to:

- UK LTE **Band 1 (L2100)** only

## What it does

- Renders Band 1 (L2100) in an SVG timeline.
- Draws two lanes:
  - DL range bar (2110-2170 MHz, EARFCN 0-599)
  - UL range bar (1920-1980 MHz, EARFCN 18000-18599)
- Uses a shared MHz axis with a secondary linear EARFCN reference axis.

## EARFCN handling

Two EARFCN concepts are intentionally shown:

- **Band table EARFCN labels** on each bar:
  - These are the per-band LTE EARFCN ranges from the catalog.
- **Top linear EARFCN axis**:
  - A quick estimation axis using `0.2 MHz per EARFCN step`.
  - This follows the requested visualization assumption for simple overlap reasoning.

## Files

- `index.html` - page structure and sections
- `style.css` - visualization styles
- `app.js` - LTE band data + SVG drawing + future overlay hook

## Next step (interactive overlap)

The script already exposes:

- `window.LteVisualizer.drawChannelOverlay({ centerEarfcn, bandwidthMhz })`
- `window.LteVisualizer.clearOverlays()`

Planned controls can call this API to draw adjustable channel blocks and show overlap.

When you are ready to expand beyond Band 1, switch the dataset selector in `app.js`
from the current `ACTIVE_BANDS` filter to a broader band set.

## Run

Open `index.html` directly in a browser, or serve the folder with any static file server.
