(function () {
  "use strict";

  // LTE band catalog (MHz + EARFCN ranges).
  // EARFCN entries are table references per band, used for labels.
  const LTE_BANDS = [
    { band: 1, type: "FDD", dl: [2110, 2170], ul: [1920, 1980], dlEarfcn: [0, 599], ulEarfcn: [18000, 18599] },
    { band: 2, type: "FDD", dl: [1930, 1990], ul: [1850, 1910], dlEarfcn: [600, 1199], ulEarfcn: [18600, 19199] },
    { band: 3, type: "FDD", dl: [1805, 1880], ul: [1710, 1785], dlEarfcn: [1200, 1949], ulEarfcn: [19200, 19949] },
    { band: 4, type: "FDD", dl: [2110, 2155], ul: [1710, 1755], dlEarfcn: [1950, 2399], ulEarfcn: [19950, 20399] },
    { band: 5, type: "FDD", dl: [869, 894], ul: [824, 849], dlEarfcn: [2400, 2649], ulEarfcn: [20400, 20649] },
    { band: 7, type: "FDD", dl: [2620, 2690], ul: [2500, 2570], dlEarfcn: [2750, 3449], ulEarfcn: [20750, 21449] },
    { band: 8, type: "FDD", dl: [925, 960], ul: [880, 915], dlEarfcn: [3450, 3799], ulEarfcn: [21450, 21799] },
    { band: 12, type: "FDD", dl: [729, 746], ul: [699, 716], dlEarfcn: [5010, 5179], ulEarfcn: [23010, 23179] },
    { band: 13, type: "FDD", dl: [746, 756], ul: [777, 787], dlEarfcn: [5180, 5279], ulEarfcn: [23180, 23279] },
    { band: 14, type: "FDD", dl: [758, 768], ul: [788, 798], dlEarfcn: [5280, 5379], ulEarfcn: [23280, 23379] },
    { band: 17, type: "FDD", dl: [734, 746], ul: [704, 716], dlEarfcn: [5730, 5849], ulEarfcn: [23730, 23849] },
    { band: 18, type: "FDD", dl: [860, 875], ul: [815, 830], dlEarfcn: [5850, 5999], ulEarfcn: [23850, 23999] },
    { band: 19, type: "FDD", dl: [875, 890], ul: [830, 845], dlEarfcn: [6000, 6149], ulEarfcn: [24000, 24149] },
    { band: 20, type: "FDD", dl: [791, 821], ul: [832, 862], dlEarfcn: [6150, 6449], ulEarfcn: [24150, 24449] },
    { band: 25, type: "FDD", dl: [1930, 1995], ul: [1850, 1915], dlEarfcn: [8040, 8689], ulEarfcn: [26040, 26689] },
    { band: 26, type: "FDD", dl: [859, 894], ul: [814, 849], dlEarfcn: [8690, 9039], ulEarfcn: [26690, 27039] },
    { band: 28, type: "FDD", dl: [758, 803], ul: [703, 748], dlEarfcn: [9210, 9659], ulEarfcn: [27210, 27659] },
    { band: 30, type: "FDD", dl: [2350, 2360], ul: [2305, 2315], dlEarfcn: [9770, 9869], ulEarfcn: [27660, 27759] },
    { band: 32, type: "SDL", dl: [1452, 1496], ul: null, dlEarfcn: [9920, 10359], ulEarfcn: null },
    { band: 34, type: "TDD", dl: [2010, 2025], ul: [2010, 2025], dlEarfcn: [36200, 36349], ulEarfcn: [36200, 36349] },
    { band: 38, type: "TDD", dl: [2570, 2620], ul: [2570, 2620], dlEarfcn: [37750, 38249], ulEarfcn: [37750, 38249] },
    { band: 39, type: "TDD", dl: [1880, 1920], ul: [1880, 1920], dlEarfcn: [38250, 38649], ulEarfcn: [38250, 38649] },
    { band: 40, type: "TDD", dl: [2300, 2400], ul: [2300, 2400], dlEarfcn: [38650, 39649], ulEarfcn: [38650, 39649] },
    { band: 41, type: "TDD", dl: [2496, 2690], ul: [2496, 2690], dlEarfcn: [39650, 41589], ulEarfcn: [39650, 41589] },
    { band: 42, type: "TDD", dl: [3400, 3600], ul: [3400, 3600], dlEarfcn: [41590, 43589], ulEarfcn: [41590, 43589] },
    { band: 43, type: "TDD", dl: [3600, 3800], ul: [3600, 3800], dlEarfcn: [43590, 45589], ulEarfcn: [43590, 45589] },
    { band: 46, type: "TDD", dl: [5150, 5925], ul: [5150, 5925], dlEarfcn: [46790, 54539], ulEarfcn: [46790, 54539] },
    { band: 48, type: "TDD", dl: [3550, 3700], ul: [3550, 3700], dlEarfcn: [55240, 56739], ulEarfcn: [55240, 56739] },
    { band: 66, type: "FDD", dl: [2110, 2200], ul: [1710, 1780], dlEarfcn: [66436, 67335], ulEarfcn: [131972, 132671] },
    { band: 71, type: "FDD", dl: [617, 652], ul: [663, 698], dlEarfcn: [68586, 68935], ulEarfcn: [133122, 133471] },
    { band: 75, type: "SDL", dl: [1432, 1517], ul: null, dlEarfcn: [69466, 70315], ulEarfcn: null },
    { band: 76, type: "SDL", dl: [1427, 1432], ul: null, dlEarfcn: [70316, 70365], ulEarfcn: null }
  ];

  // Development scope for now: UK LTE Band 1 (L2100) only.
  const ACTIVE_BANDS = LTE_BANDS.filter((b) => b.band === 1);
  const PAGE_BAND = 1;

  const svg = document.getElementById("viz");
  if (!svg) return;

  const MARGIN = { right: 24, left: 164 };
  const BAR_H = 12;
  const CHART_H = 264;
  const CHART_GAP = 34;
  const CHART_START = 20;
  const WIDTH = 1400;
  const baseBand = ACTIVE_BANDS[0];
  if (!baseBand) return;
  const CHARTS = [
    {
      title: "Band 1 (L2100) Downlink (DL)",
      laneLabel: "DL",
      freqRange: baseBand.dl,
      earfcnRange: baseBand.dlEarfcn,
      cls: "bar-dl"
    },
    {
      title: "Band 1 (L2100) Uplink (UL)",
      laneLabel: "UL",
      freqRange: baseBand.ul,
      earfcnRange: baseBand.ulEarfcn,
      cls: "bar-ul"
    }
  ];
  const height = CHART_START + CHARTS.length * CHART_H + (CHARTS.length - 1) * CHART_GAP + 24;
  const chartByLane = Object.fromEntries(CHARTS.map((c) => [c.laneLabel, c]));
  const chartLayoutByLane = {};

  svg.setAttribute("viewBox", `0 0 ${WIDTH} ${height}`);
  svg.setAttribute("height", String(height));

  const overlayLayer = node("g");
  overlayLayer.setAttribute("id", "overlay-layer");
  const runtimeLayer = node("g");
  runtimeLayer.setAttribute("id", "runtime-layer");

  CHARTS.forEach((chart, i) => drawSingleChart(chart, i));
  drawCarrierSymbol({
    lane: "DL",
    label: "Vodafone 15 MHz (EARFCN 223)",
    centerEarfcn: 223,
    bandwidthMhz: 15,
    lineColor: "#ff4d4d",
    markerFill: "#ff4d4d",
    markerStroke: "#ffb0b0",
    baselineColor: "#ff6b6b"
  });
  drawCarrierSymbol({
    lane: "DL",
    label: "VMO2 10 MHz (EARFCN 347)",
    centerEarfcn: 347,
    bandwidthMhz: 10,
    lineColor: "#3b82f6",
    markerFill: "#3b82f6",
    markerStroke: "#a9c8ff",
    baselineColor: "#60a5fa"
  });
  drawCarrierSymbol({
    lane: "DL",
    label: "THREE 15 MHz (EARFCN 76)",
    centerEarfcn: 76,
    bandwidthMhz: 15,
    lineColor: "#facc15",
    markerFill: "#facc15",
    markerStroke: "#fde68a",
    baselineColor: "#fbbf24"
  });
  drawCarrierSymbol({
    lane: "DL",
    label: "EE 20 MHz (EARFCN 497)",
    centerEarfcn: 497,
    bandwidthMhz: 20,
    lineColor: "#22c55e",
    markerFill: "#22c55e",
    markerStroke: "#86efac",
    baselineColor: "#4ade80"
  });
  // Matching UL carriers for Band 1 FDD pairings (DL EARFCN + 18000).
  drawCarrierSymbol({
    lane: "UL",
    label: "Vodafone 15 MHz (EARFCN 18223)",
    centerEarfcn: 18223,
    bandwidthMhz: 15,
    lineColor: "#ff4d4d",
    markerFill: "#ff4d4d",
    markerStroke: "#ffb0b0",
    baselineColor: "#ff6b6b"
  });
  drawCarrierSymbol({
    lane: "UL",
    label: "VMO2 10 MHz (EARFCN 18347)",
    centerEarfcn: 18347,
    bandwidthMhz: 10,
    lineColor: "#3b82f6",
    markerFill: "#3b82f6",
    markerStroke: "#a9c8ff",
    baselineColor: "#60a5fa"
  });
  drawCarrierSymbol({
    lane: "UL",
    label: "THREE 15 MHz (EARFCN 18076)",
    centerEarfcn: 18076,
    bandwidthMhz: 15,
    lineColor: "#facc15",
    markerFill: "#facc15",
    markerStroke: "#fde68a",
    baselineColor: "#fbbf24"
  });
  drawCarrierSymbol({
    lane: "UL",
    label: "EE 20 MHz (EARFCN 18497)",
    centerEarfcn: 18497,
    bandwidthMhz: 20,
    lineColor: "#22c55e",
    markerFill: "#22c55e",
    markerStroke: "#86efac",
    baselineColor: "#4ade80"
  });
  svg.appendChild(overlayLayer);
  svg.appendChild(runtimeLayer);

  function toX(freqMhz, freqMin, freqMax) {
    const innerW = WIDTH - MARGIN.left - MARGIN.right;
    const span = Math.max(0.0001, freqMax - freqMin);
    return MARGIN.left + ((freqMhz - freqMin) / span) * innerW;
  }

  function freqToChartEarfcn(freqMhz, chart) {
    if (!chart.earfcnRange) return null;
    const [f0, f1] = chart.freqRange;
    const [e0, e1] = chart.earfcnRange;
    const frac = (freqMhz - f0) / Math.max(0.0001, f1 - f0);
    return e0 + frac * (e1 - e0);
  }

  function chartEarfcnToFreq(earfcn, chart) {
    if (!chart.earfcnRange) return null;
    const [f0, f1] = chart.freqRange;
    const [e0, e1] = chart.earfcnRange;
    const frac = (earfcn - e0) / Math.max(0.0001, e1 - e0);
    return f0 + frac * (f1 - f0);
  }

  function drawSingleChart(chart, chartIndex) {
    const [freqMin, freqMax] = chart.freqRange;
    const top = CHART_START + chartIndex * (CHART_H + CHART_GAP);
    // Place scales beneath the carrier/band visualization.
    const barY = top + 92;
    const axisY1 = top + 148;
    const axisY2 = top + 178;
    chartLayoutByLane[chart.laneLabel] = { top, axisY1, axisY2, barY };

    const title = text(MARGIN.left, top + 10, chart.title, "axis-label");
    title.setAttribute("font-weight", "700");
    svg.appendChild(title);

    const line1 = line(MARGIN.left, axisY1, WIDTH - MARGIN.right, axisY1, "axis-line");
    const line2 = line(MARGIN.left, axisY2, WIDTH - MARGIN.right, axisY2, "axis-line");
    svg.appendChild(line1);
    svg.appendChild(line2);

    const mhzTicks = buildMhzTicks(freqMin, freqMax);
    for (const mhz of mhzTicks) {
      const x = toX(mhz, freqMin, freqMax);
      svg.appendChild(line(x, axisY1 - 5, x, axisY2 + 5, "tick-line"));

      const t1 = text(x, axisY1 - 7, `${mhz.toFixed(0)} MHz`, "tick-label");
      t1.setAttribute("text-anchor", "middle");
      svg.appendChild(t1);

      const e = Math.round(freqToChartEarfcn(mhz, chart));
      const t2 = text(x, axisY2 + 14, `${e}`, "subtle-label");
      t2.setAttribute("text-anchor", "middle");
      svg.appendChild(t2);
    }

    const a1 = text(8, axisY1 - 7, "MHz", "subtle-label");
    const a2 = text(8, axisY2 + 14, "EARFCN*", "subtle-label");
    svg.appendChild(a1);
    svg.appendChild(a2);
    drawRangeBar({
      y: barY,
      freqRange: chart.freqRange,
      cls: chart.cls,
      laneLabel: chart.laneLabel,
      earfcnRange: chart.earfcnRange
    });
  }

  function drawRangeBar(opts) {
    const x0 = toX(opts.freqRange[0], opts.freqRange[0], opts.freqRange[1]);
    const x1 = toX(opts.freqRange[1], opts.freqRange[0], opts.freqRange[1]);
    const w = Math.max(1.5, x1 - x0);
    const r = node("rect");
    r.setAttribute("x", String(x0));
    r.setAttribute("y", String(opts.y));
    r.setAttribute("width", String(w));
    r.setAttribute("height", String(BAR_H));
    r.setAttribute("rx", "2");
    r.setAttribute("class", opts.cls);
    svg.appendChild(r);

    const laneTxt = text(x0 + 4, opts.y + BAR_H - 2, opts.laneLabel, "bar-label");
    svg.appendChild(laneTxt);

    const freqTxt = `${opts.freqRange[0].toFixed(1)}-${opts.freqRange[1].toFixed(1)} MHz`;
    const rightLabel = opts.earfcnRange
      ? `${freqTxt} | EARFCN ${opts.earfcnRange[0]}-${opts.earfcnRange[1]}`
      : freqTxt;
    const t = text(Math.min(WIDTH - MARGIN.right - 6, x1 + 6), opts.y + BAR_H - 2, rightLabel, "subtle-label");
    svg.appendChild(t);
  }

  function buildMhzTicks(freqMin, freqMax) {
    const span = freqMax - freqMin;
    let step = 10;
    if (span <= 20) step = 2;
    else if (span <= 40) step = 5;
    else if (span <= 100) step = 10;
    else if (span <= 200) step = 20;
    else step = 50;
    const ticks = [freqMin];
    let t = Math.ceil(freqMin / step) * step;
    while (t < freqMax) {
      if (t > freqMin) ticks.push(t);
      t += step;
    }
    if (ticks[ticks.length - 1] !== freqMax) ticks.push(freqMax);
    return ticks;
  }

  function line(x1, y1, x2, y2, cls) {
    const el = node("line");
    el.setAttribute("x1", String(x1));
    el.setAttribute("y1", String(y1));
    el.setAttribute("x2", String(x2));
    el.setAttribute("y2", String(y2));
    el.setAttribute("class", cls);
    return el;
  }

  function text(x, y, value, cls) {
    const el = node("text");
    el.setAttribute("x", String(x));
    el.setAttribute("y", String(y));
    el.setAttribute("class", cls);
    el.textContent = value;
    return el;
  }

  function node(name) {
    return document.createElementNS("http://www.w3.org/2000/svg", name);
  }

  /**
   * Future overlay hook for interactive mode.
   * Draws a channel block around center EARFCN using linear 0.2 MHz/step assumption.
   */
  function drawChannelOverlay(input) {
    if (!input || typeof input.centerEarfcn !== "number" || typeof input.bandwidthMhz !== "number") {
      return;
    }
    const chart = chartByLane.DL;
    if (!chart) return;
    const half = Math.max(0, input.bandwidthMhz / 2);
    const centerFreq = chartEarfcnToFreq(input.centerEarfcn, chart);
    if (centerFreq == null) return;
    const lo = centerFreq - half;
    const hi = centerFreq + half;
    const x0 = toX(lo, chart.freqRange[0], chart.freqRange[1]);
    const x1 = toX(hi, chart.freqRange[0], chart.freqRange[1]);
    const rect = node("rect");
    rect.setAttribute("x", String(Math.min(x0, x1)));
    rect.setAttribute("y", String(CHART_START));
    rect.setAttribute("width", String(Math.abs(x1 - x0)));
    rect.setAttribute("height", String(CHARTS.length * CHART_H + (CHARTS.length - 1) * CHART_GAP - 24));
    rect.setAttribute("class", "overlay-box");
    overlayLayer.appendChild(rect);
  }

  function drawCarrierSymbol(cfg) {
    const targetLayer = cfg.targetLayer || overlayLayer;
    const lane = cfg.lane || "DL";
    const chart = chartByLane[lane];
    const layout = chartLayoutByLane[lane];
    if (!chart || !layout) return;

    const centerEarfcn = Number(cfg.centerEarfcn);
    const bandwidthMhz = Number(cfg.bandwidthMhz);
    const halfBw = bandwidthMhz / 2;
    const centerFreq = chartEarfcnToFreq(centerEarfcn, chart);
    if (centerFreq == null) return;

    const lo = centerFreq - halfBw;
    const hi = centerFreq + halfBw;
    const x0 = toX(lo, chart.freqRange[0], chart.freqRange[1]);
    const x1 = toX(hi, chart.freqRange[0], chart.freqRange[1]);
    const x = Math.min(x0, x1);
    const w = Math.abs(x1 - x0);

    // Table-mountain spectral shape: straight symmetric angled sides + flat top.
    const markerY = layout.barY - 12;
    const amplitude = 24;
    const shoulderW = Math.max(10, w * 0.12);
    const flatL = x + shoulderW;
    const flatR = x + w - shoulderW;
    const pts = [];

    // Left slope (bottom -> top), top plateau, right slope (top -> bottom).
    pts.push([x, markerY]);
    pts.push([flatL, markerY - amplitude]);
    pts.push([flatR, markerY - amplitude]);
    pts.push([x + w, markerY]);

    const path = node("path");
    let d = "";
    pts.forEach((p, idx) => {
      d += `${idx === 0 ? "M" : "L"}${p[0].toFixed(2)},${p[1].toFixed(2)} `;
    });
    path.setAttribute("d", d.trim());
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", cfg.lineColor);
    path.setAttribute("stroke-width", "3");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("stroke-linecap", "round");
    targetLayer.appendChild(path);

    // Center rhombus marker in the middle of the carrier shape.
    const cx = x + w / 2;
    const cy = markerY - amplitude * 0.35;
    const r = 10;
    const rhombus = node("polygon");
    rhombus.setAttribute(
      "points",
      `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`
    );
    rhombus.setAttribute("fill", cfg.markerFill);
    rhombus.setAttribute("stroke", cfg.markerStroke);
    rhombus.setAttribute("stroke-width", "1");
    targetLayer.appendChild(rhombus);

    const flatTopY = markerY - amplitude;
    const label = text(cx, flatTopY - 24, cfg.label, "subtle-label");
    label.setAttribute("text-anchor", "middle");
    targetLayer.appendChild(label);

    const mhzLabel = text(cx, flatTopY - 10, `Center ${centerFreq.toFixed(1)} MHz`, "subtle-label");
    mhzLabel.setAttribute("text-anchor", "middle");
    targetLayer.appendChild(mhzLabel);
  }

  function ulPairOffset() {
    const dl = chartByLane.DL?.earfcnRange;
    const ul = chartByLane.UL?.earfcnRange;
    if (!dl || !ul) return 0;
    return ul[0] - dl[0];
  }

  function renderRuntimeChannels(channels) {
    runtimeLayer.innerHTML = "";
    const src = channels || {};
    const palette = [
      { fill: "#ff7ad9", stroke: "#ffc5ef" },
      { fill: "#67e8f9", stroke: "#bbf7ff" },
      { fill: "#facc15", stroke: "#fde68a" },
      { fill: "#22c55e", stroke: "#86efac" },
      { fill: "#fb7185", stroke: "#fecdd3" },
      { fill: "#a78bfa", stroke: "#ddd6fe" },
      { fill: "#34d399", stroke: "#a7f3d0" },
    ];
    const off = ulPairOffset();
    for (let i = 0; i < 14; i++) {
      const key = `ch${i}`;
      const c = src[key];
      if (!c || !c.channel_enabled) continue;
      if (Number(c.band_eutra) !== PAGE_BAND) continue;
      const earfcn = Number(c.earfcn);
      const bw = Number(c.bw_mhz);
      if (!Number.isFinite(earfcn) || !Number.isFinite(bw) || bw <= 0) continue;
      const p = palette[i % palette.length];
      drawRuntimeRect({
        lane: "DL",
        label: `CH${i}`,
        centerEarfcn: earfcn,
        bandwidthMhz: bw,
        lineColor: p.fill,
        markerFill: p.fill,
        markerStroke: p.stroke,
        slot: i,
      });
      drawRuntimeRect({
        lane: "UL",
        label: `CH${i}`,
        centerEarfcn: earfcn + off,
        bandwidthMhz: bw,
        lineColor: p.fill,
        markerFill: p.fill,
        markerStroke: p.stroke,
        slot: i,
      });
    }
  }

  function drawRuntimeRect(cfg) {
    const lane = cfg.lane || "DL";
    const chart = chartByLane[lane];
    const layout = chartLayoutByLane[lane];
    if (!chart || !layout) return;
    const centerEarfcn = Number(cfg.centerEarfcn);
    const bandwidthMhz = Number(cfg.bandwidthMhz);
    if (!Number.isFinite(centerEarfcn) || !Number.isFinite(bandwidthMhz) || bandwidthMhz <= 0) return;

    const centerFreq = chartEarfcnToFreq(centerEarfcn, chart);
    const halfBw = bandwidthMhz / 2;
    const lo = centerFreq - halfBw;
    const hi = centerFreq + halfBw;
    const x0 = toX(lo, chart.freqRange[0], chart.freqRange[1]);
    const x1 = toX(hi, chart.freqRange[0], chart.freqRange[1]);
    const x = Math.min(x0, x1);
    const w = Math.max(8, Math.abs(x1 - x0));
    const slot = Number.isFinite(Number(cfg.slot)) ? Number(cfg.slot) : 0;
    const y = layout.barY + 10 + slot * 16;
    const h = 12;

    const rect = node("rect");
    rect.setAttribute("x", String(x));
    rect.setAttribute("y", String(y));
    rect.setAttribute("width", String(w));
    rect.setAttribute("height", String(h));
    rect.setAttribute("rx", "2");
    rect.setAttribute("fill", cfg.markerFill || "#67e8f9");
    rect.setAttribute("fill-opacity", "0.55");
    rect.setAttribute("stroke", cfg.markerStroke || "#bbf7ff");
    rect.setAttribute("stroke-width", "1");
    runtimeLayer.appendChild(rect);

    const tx = text(x + w / 2, y + h - 2, cfg.label || "CH", "subtle-label");
    tx.setAttribute("text-anchor", "middle");
    tx.setAttribute("fill", "#ffffff");
    tx.setAttribute("font-size", "10");
    runtimeLayer.appendChild(tx);
  }

  window.addEventListener("message", (ev) => {
    if (ev.origin !== window.location.origin) return;
    const data = ev.data || {};
    if (data.type !== "lte-viz-runtime") return;
    renderRuntimeChannels(data.channels || {});
  });

  // Expose a small API for next iteration controls/debug.
  window.LteVisualizer = {
    drawChannelOverlay,
    clearOverlays: function () {
      overlayLayer.innerHTML = "";
    },
    freqToChartEarfcn: function (freqMhz, lane) {
      const c = chartByLane[lane || "DL"];
      return c ? freqToChartEarfcn(freqMhz, c) : null;
    },
    chartEarfcnToFreq: function (earfcn, lane) {
      const c = chartByLane[lane || "DL"];
      return c ? chartEarfcnToFreq(earfcn, c) : null;
    }
  };
})();
