(function () {
  "use strict";

  // LTE Band 7 (2600 MHz) FDD
  const BAND7 = {
    band: 7,
    type: "FDD",
    dl: [2620, 2690],
    ul: [2500, 2570],
    dlEarfcn: [2750, 3449],
    ulEarfcn: [20750, 21449]
  };
  const PAGE_BAND = 7;

  const svg = document.getElementById("viz");
  if (!svg) return;

  const MARGIN = { right: 24, left: 164 };
  const BAR_H = 12;
  const CHART_H = 264;
  const CHART_GAP = 34;
  const CHART_START = 20;
  const WIDTH = 1400;

  const CHARTS = [
    {
      title: "Band 7 (L2600) Downlink (DL)",
      laneLabel: "DL",
      freqRange: BAND7.dl,
      earfcnRange: BAND7.dlEarfcn,
      cls: "bar-dl"
    },
    {
      title: "Band 7 (L2600) Uplink (UL)",
      laneLabel: "UL",
      freqRange: BAND7.ul,
      earfcnRange: BAND7.ulEarfcn,
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

  // User-specified carriers
  drawCarrierSymbol({
    lane: "DL",
    label: "Vodafone 20 MHz (EARFCN 2850)",
    centerEarfcn: 2850,
    bandwidthMhz: 20,
    lineColor: "#ff4d4d",
    markerFill: "#ff4d4d",
    markerStroke: "#ffb0b0"
  });
  drawCarrierSymbol({
    lane: "DL",
    label: "EE 20 MHz (EARFCN 3179)",
    centerEarfcn: 3179,
    bandwidthMhz: 20,
    lineColor: "#22c55e",
    markerFill: "#22c55e",
    markerStroke: "#86efac"
  });
  drawCarrierSymbol({
    lane: "DL",
    label: "EE 20 MHz (EARFCN 3350)",
    centerEarfcn: 3350,
    bandwidthMhz: 20,
    lineColor: "#22c55e",
    markerFill: "#22c55e",
    markerStroke: "#86efac"
  });

  // UL paired carriers (DL + 18000)
  drawCarrierSymbol({
    lane: "UL",
    label: "Vodafone 20 MHz (EARFCN 20850)",
    centerEarfcn: 20850,
    bandwidthMhz: 20,
    lineColor: "#ff4d4d",
    markerFill: "#ff4d4d",
    markerStroke: "#ffb0b0"
  });
  drawCarrierSymbol({
    lane: "UL",
    label: "EE 20 MHz (EARFCN 21179)",
    centerEarfcn: 21179,
    bandwidthMhz: 20,
    lineColor: "#22c55e",
    markerFill: "#22c55e",
    markerStroke: "#86efac"
  });
  drawCarrierSymbol({
    lane: "UL",
    label: "EE 20 MHz (EARFCN 21350)",
    centerEarfcn: 21350,
    bandwidthMhz: 20,
    lineColor: "#22c55e",
    markerFill: "#22c55e",
    markerStroke: "#86efac"
  });

  svg.appendChild(overlayLayer);
  svg.appendChild(runtimeLayer);

  function toX(freqMhz, freqMin, freqMax) {
    const innerW = WIDTH - MARGIN.left - MARGIN.right;
    const span = Math.max(0.0001, freqMax - freqMin);
    return MARGIN.left + ((freqMhz - freqMin) / span) * innerW;
  }

  function freqToChartEarfcn(freqMhz, chart) {
    const [f0, f1] = chart.freqRange;
    const [e0, e1] = chart.earfcnRange;
    const frac = (freqMhz - f0) / Math.max(0.0001, f1 - f0);
    return e0 + frac * (e1 - e0);
  }

  function chartEarfcnToFreq(earfcn, chart) {
    const [f0, f1] = chart.freqRange;
    const [e0, e1] = chart.earfcnRange;
    const frac = (earfcn - e0) / Math.max(0.0001, e1 - e0);
    return f0 + frac * (f1 - f0);
  }

  function drawSingleChart(chart, chartIndex) {
    const [freqMin, freqMax] = chart.freqRange;
    const top = CHART_START + chartIndex * (CHART_H + CHART_GAP);
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
    const rightLabel = `${freqTxt} | EARFCN ${opts.earfcnRange[0]}-${opts.earfcnRange[1]}`;
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

    const lo = centerFreq - halfBw;
    const hi = centerFreq + halfBw;
    const x0 = toX(lo, chart.freqRange[0], chart.freqRange[1]);
    const x1 = toX(hi, chart.freqRange[0], chart.freqRange[1]);
    const x = Math.min(x0, x1);
    const w = Math.abs(x1 - x0);

    const markerY = layout.barY - 12;
    const amplitude = 24;
    const shoulderW = Math.max(10, w * 0.12);
    const flatL = x + shoulderW;
    const flatR = x + w - shoulderW;

    const path = node("path");
    const d = `M${x.toFixed(2)},${markerY.toFixed(2)} ` +
      `L${flatL.toFixed(2)},${(markerY - amplitude).toFixed(2)} ` +
      `L${flatR.toFixed(2)},${(markerY - amplitude).toFixed(2)} ` +
      `L${(x + w).toFixed(2)},${markerY.toFixed(2)}`;
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", cfg.lineColor);
    path.setAttribute("stroke-width", "3");
    path.setAttribute("stroke-linejoin", "round");
    path.setAttribute("stroke-linecap", "round");
    targetLayer.appendChild(path);

    const cx = x + w / 2;
    const cy = markerY - amplitude * 0.35;
    const r = 10;
    const rhombus = node("polygon");
    rhombus.setAttribute("points", `${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}`);
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
})();
