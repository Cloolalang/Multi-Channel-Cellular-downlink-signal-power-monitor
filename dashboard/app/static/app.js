(function () {
  const charts = {};
  let lastSnap = null;

  function fmtTime(t) {
    const d = new Date(t * 1000);
    return d.toLocaleTimeString();
  }

  function ensureChart(canvas) {
    const id = canvas.id;
    if (charts[id]) return charts[id];
    const kind = canvas.dataset.chartKind || "line";
    const ctx = canvas.getContext("2d");
    charts[id] = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: kind,
            data: [],
            borderColor: "#1f77b4",
            tension: 0.2,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        animation: false,
        scales: {
          x: {
            ticks: {
              maxTicksLimit: 8,
              callback: function (v, i) {
                const lbl = this.getLabelForValue(v);
                return lbl;
              },
            },
          },
          y: {},
        },
        plugins: { legend: { display: false } },
      },
    });
    return charts[id];
  }

  function parseAxisBound(raw) {
    if (raw === undefined || raw === null) return NaN;
    const s = String(raw).trim();
    if (s === "") return NaN;
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : NaN;
  }

  /**
   * Node-RED ymin/ymax often reflect NR dashboard scaling, not raw dBm from this app.
   * If the series falls outside the configured range, expand the y-axis so the line is visible.
   */
  function pushSeries(chart, points, yminRaw, ymaxRaw) {
    const labels = points.map((p) => fmtTime(p[0]));
    const series = points.map((p) => p[1]);
    const finite = series.filter((v) => Number.isFinite(v));
    chart.data.labels = labels;
    chart.data.datasets[0].data = series;

    const cfgMin = parseAxisBound(yminRaw);
    const cfgMax = parseAxisBound(ymaxRaw);
    const hasCfg = Number.isFinite(cfgMin) && Number.isFinite(cfgMax) && cfgMin < cfgMax;

    if (finite.length === 0) {
      if (hasCfg) {
        chart.options.scales.y.min = cfgMin;
        chart.options.scales.y.max = cfgMax;
      } else {
        chart.options.scales.y.min = undefined;
        chart.options.scales.y.max = undefined;
      }
      chart.update();
      return;
    }

    const dmin = Math.min(...finite);
    const dmax = Math.max(...finite);
    const pad = Math.max((dmax - dmin) * 0.08, dmin === dmax ? 0.5 : 0);

    if (
      !hasCfg ||
      dmin < cfgMin ||
      dmax > cfgMax
    ) {
      chart.options.scales.y.min = dmin - pad;
      chart.options.scales.y.max = dmax + pad;
    } else {
      chart.options.scales.y.min = cfgMin;
      chart.options.scales.y.max = cfgMax;
    }
    chart.update();
  }

  const CHANNEL_KEYS =
    Array.isArray(window.__CHANNELS) && window.__CHANNELS.length
      ? window.__CHANNELS
      : Array.from({ length: 14 }, (_, i) => "ch" + i);

  // LTE EARFCN -> DL MHz (3GPP TS 36.101): F_DL = F_DL_low + 0.1 * (N_DL - N_offs_DL)
  const LTE_DL_EARFCN_MAP = {
    1: { fLow: 2110.0, nOffs: 0, nMin: 0, nMax: 599 },
    2: { fLow: 1930.0, nOffs: 600, nMin: 600, nMax: 1199 },
    3: { fLow: 1805.0, nOffs: 1200, nMin: 1200, nMax: 1949 },
    4: { fLow: 2110.0, nOffs: 1950, nMin: 1950, nMax: 2399 },
    5: { fLow: 869.0, nOffs: 2400, nMin: 2400, nMax: 2649 },
    7: { fLow: 2620.0, nOffs: 2750, nMin: 2750, nMax: 3449 },
    8: { fLow: 925.0, nOffs: 3450, nMin: 3450, nMax: 3799 },
    9: { fLow: 1844.9, nOffs: 3800, nMin: 3800, nMax: 4149 },
    10: { fLow: 2110.0, nOffs: 4150, nMin: 4150, nMax: 4749 },
    11: { fLow: 1475.9, nOffs: 4750, nMin: 4750, nMax: 4949 },
    12: { fLow: 729.0, nOffs: 5010, nMin: 5010, nMax: 5179 },
    13: { fLow: 746.0, nOffs: 5180, nMin: 5180, nMax: 5279 },
    14: { fLow: 758.0, nOffs: 5280, nMin: 5280, nMax: 5379 },
    17: { fLow: 734.0, nOffs: 5730, nMin: 5730, nMax: 5849 },
    18: { fLow: 860.0, nOffs: 5850, nMin: 5850, nMax: 5999 },
    19: { fLow: 875.0, nOffs: 6000, nMin: 6000, nMax: 6149 },
    20: { fLow: 791.0, nOffs: 6150, nMin: 6150, nMax: 6449 },
    25: { fLow: 1930.0, nOffs: 8040, nMin: 8040, nMax: 8689 },
    26: { fLow: 859.0, nOffs: 8690, nMin: 8690, nMax: 9039 },
    28: { fLow: 758.0, nOffs: 9210, nMin: 9210, nMax: 9659 },
    34: { fLow: 2010.0, nOffs: 36200, nMin: 36200, nMax: 36349 },
    38: { fLow: 2570.0, nOffs: 37750, nMin: 37750, nMax: 38249 },
    39: { fLow: 1880.0, nOffs: 38250, nMin: 38250, nMax: 38649 },
    40: { fLow: 2300.0, nOffs: 38650, nMin: 38650, nMax: 39649 },
    41: { fLow: 2496.0, nOffs: 39650, nMin: 39650, nMax: 41589 },
    66: { fLow: 2110.0, nOffs: 66436, nMin: 66436, nMax: 67335 },
    71: { fLow: 617.0, nOffs: 68586, nMin: 68586, nMax: 68935 },
  };

  function channelCount() {
    return CHANNEL_KEYS.length;
  }

  function lteDlFreqMhzFromBandEarfcn(band, earfcn) {
    const b = parseInt(String(band), 10);
    const n = parseInt(String(earfcn), 10);
    if (!Number.isFinite(b) || !Number.isFinite(n)) return null;
    const row = LTE_DL_EARFCN_MAP[b];
    if (!row) return null;
    if (n < row.nMin || n > row.nMax) return null;
    const f = row.fLow + 0.1 * (n - row.nOffs);
    return Number.isFinite(f) ? f : null;
  }

  function updateChannelCentreFreqDisplay(channel) {
    if (!channel) return;
    const host = document.querySelector(`.js-centre-freq[data-channel="${channel}"]`);
    if (!host) return;
    const bandEl = document.querySelector(`.js-ch[data-channel="${channel}"][data-field="band_eutra"]`);
    const earEl = document.querySelector(`.js-ch[data-channel="${channel}"][data-field="earfcn"]`);
    if (!bandEl || !earEl) {
      host.textContent = "Centre frequency: — MHz";
      return;
    }
    const f = lteDlFreqMhzFromBandEarfcn(bandEl.value, earEl.value);
    host.textContent = f == null ? "Centre frequency: — MHz" : `Centre frequency: ${f.toFixed(1)} MHz`;
  }

  function updateAllCentreFreqDisplays() {
    CHANNEL_KEYS.forEach((ch) => updateChannelCentreFreqDisplay(ch));
  }

  function applyMnoPresetToForm(p, rootEl) {
    if (!p) return;
    const root = rootEl && rootEl.querySelector ? rootEl : document;
    const bandEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="band_eutra"]'));
    const earEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="earfcn"]'));
    const bwEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="bw_mhz"]'));
    const mnoEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="mno"]'));
    const n = Math.max(bandEls.length, earEls.length, bwEls.length, mnoEls.length, channelCount());
    const band = p.band_eutra || [];
    const ear = p.earfcn || [];
    const bw = p.bw_mhz || [];
    const mno = p.mno || [];
    for (let i = 0; i < n; i++) {
      const b = bandEls[i] || null;
      if (b) b.value = band[i] == null || band[i] === "" ? "" : String(band[i]);
      const e = earEls[i] || null;
      if (e) e.value = ear[i] == null || ear[i] === "" ? "" : String(ear[i]);
      const bwEl = bwEls[i] || null;
      if (bwEl) bwEl.value = bw[i] == null || bw[i] === "" ? "" : String(bw[i]);
      const m = mnoEls[i] || null;
      if (m) m.value = mno[i] == null || mno[i] === "" ? "" : String(mno[i]);
    }
  }

  function collectMnoCommonPreset(formEl) {
    const root = formEl && formEl.querySelector ? formEl : document.getElementById("form-dashboard-config") || document;
    const bandEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="band_eutra"]'));
    const earEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="earfcn"]'));
    const bwEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="bw_mhz"]'));
    const mnoEls = Array.from(root.querySelectorAll('.js-mno-preset[data-field="mno"]'));
    const n = Math.max(bandEls.length, earEls.length, bwEls.length, mnoEls.length, channelCount());
    const band_eutra = [];
    const earfcn = [];
    const bw_mhz = [];
    const mno = [];
    for (let i = 0; i < n; i++) {
      const bel = bandEls[i] || null;
      const earEl = earEls[i] || null;
      const bwEl = bwEls[i] || null;
      const mnoEl = mnoEls[i] || null;
      const parseIntOrNull = (el) => {
        if (!el) return null;
        const s = String(el.value).trim();
        if (s === "") return null;
        const x = parseInt(s, 10);
        return Number.isFinite(x) ? x : null;
      };
      band_eutra.push(parseIntOrNull(bel));
      earfcn.push(parseIntOrNull(earEl));
      if (!bwEl || String(bwEl.value).trim() === "") bw_mhz.push(null);
      else {
        const x = parseFloat(String(bwEl.value));
        bw_mhz.push(Number.isFinite(x) ? x : null);
      }
      if (!mnoEl) {
        mno.push(null);
      } else {
        const val = String(mnoEl.value || "").trim();
        const opt = mnoEl.options && mnoEl.selectedIndex >= 0 ? mnoEl.options[mnoEl.selectedIndex] : null;
        const txt = opt ? String(opt.text || "").trim() : "";
        const chosen = val || (txt === "— leave" ? "" : txt);
        mno.push(chosen === "" ? null : chosen);
      }
    }
    return { band_eutra, earfcn, bw_mhz, mno };
  }

  function syncMnoSelectValues(formEl) {
    const root = formEl && formEl.querySelector ? formEl : document;
    const n = channelCount();
    for (let i = 0; i < n; i++) {
      const m = root.querySelector(`.js-mno-preset[data-field="mno"][data-ch="${i}"]`);
      if (!m) continue;
      // Force normalized current value to avoid stale/empty reads on quick tab switches.
      m.value = String(m.value || "").trim();
    }
  }

  function addBandAttenRow(tb, band, db) {
    if (!tb) return;
    const tr = document.createElement("tr");
    tr.className = "js-band-atten-row";
    const td1 = document.createElement("td");
    const inpB = document.createElement("input");
    inpB.type = "number";
    inpB.step = "1";
    inpB.className = "js-band-atten-band";
    if (band !== "" && band != null) inpB.value = String(band);
    td1.appendChild(inpB);
    const td2 = document.createElement("td");
    const inpD = document.createElement("input");
    inpD.type = "number";
    inpD.step = "any";
    inpD.className = "js-band-atten-db";
    if (db !== "" && db != null) inpD.value = String(db);
    td2.appendChild(inpD);
    const td3 = document.createElement("td");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-control btn-band-atten-del";
    btn.title = "Remove row";
    btn.textContent = "×";
    td3.appendChild(btn);
    tr.appendChild(td1);
    tr.appendChild(td2);
    tr.appendChild(td3);
    tb.appendChild(tr);
  }

  function applyBandAttenToForm(dict) {
    const tb = document.getElementById("js-band-atten-tbody");
    if (!tb || !dict) return;
    tb.innerHTML = "";
    const bands = Object.keys(dict)
      .map((k) => parseInt(k, 10))
      .filter((x) => Number.isFinite(x))
      .sort((a, b) => a - b);
    bands.forEach((b) => addBandAttenRow(tb, b, dict[String(b)]));
  }

  function collectBandAttenTable() {
    const out = {};
    document.querySelectorAll(".js-band-atten-row").forEach((row) => {
      const bEl = row.querySelector(".js-band-atten-band");
      const vEl = row.querySelector(".js-band-atten-db");
      if (!bEl || !vEl) return;
      const bs = String(bEl.value).trim();
      const vs = String(vEl.value).trim();
      if (bs === "" || vs === "") return;
      const b = parseInt(bs, 10);
      const v = parseFloat(vs);
      if (!Number.isFinite(b) || !Number.isFinite(v)) return;
      out[String(b)] = v;
    });
    return out;
  }

  function parseCfgNullableFloat(v) {
    const s = String(v ?? "").trim();
    if (s === "" || s === "-" || s === "." || s === "-.") return null;
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : null;
  }

  function gaugeGradient(el, bounds) {
    const c0 = el.dataset.c0 || "#e74c3c";
    const c1 = el.dataset.c1 || "#f1c40f";
    const c2 = el.dataset.c2 || "#2ecc71";
    return `linear-gradient(90deg, ${c0}, ${c1}, ${c2})`;
  }

  function parseGaugeBounds(el) {
    const m = el.dataset.metric;
    const ctrl = window.__lastControls;
    const dBmGauge =
      m === "rssi_dbm" ||
      m === "rssi_avg" ||
      m === "composite_dbm" ||
      m === "composite_avg_10";
    if (dBmGauge && ctrl) {
      let ogmin = ctrl.gauge_min;
      let ogmax = ctrl.gauge_max;
      if (
        ogmin == null ||
        ogmax == null ||
        !Number.isFinite(Number(ogmin)) ||
        !Number.isFinite(Number(ogmax))
      ) {
        ogmin = -30;
        ogmax = 25;
      }
      if (Number(ogmin) !== Number(ogmax)) {
        const lo = Math.min(Number(ogmin), Number(ogmax));
        const hi = Math.max(Number(ogmin), Number(ogmax));
        return { min: lo, max: hi };
      }
    }

    const mn = parseFloat(el.dataset.min);
    const mx = parseFloat(el.dataset.max);
    const rssiLike =
      m === "rssi_dbm" ||
      m === "rssi_avg" ||
      m === "composite_dbm" ||
      m === "composite_avg_10";
    if (Number.isFinite(mn) && Number.isFinite(mx) && mn !== mx) {
      const lo = Math.min(mn, mx);
      const hi = Math.max(mn, mx);
      /* flows.json sometimes uses non-dBm scales (e.g. -29…18); use a typical dBm span for RF gauges */
      if (rssiLike && (hi > 0 || lo > 0)) {
        return { min: -30, max: 25 };
      }
      return { min: lo, max: hi };
    }
    if (m === "carrier_count") return { min: 0, max: 14 };
    if (m === "composite_mw") return { min: 0, max: 10 };
    return { min: -30, max: 25 };
  }

  function chartYAxisFromGauge(snap, kind) {
    if (kind === "rssi_sd" || kind === "composite_sd") return null;
    if (kind !== "rssi_avg" && kind !== "composite_avg" && kind !== "all_cc_rssi") return null;
    const ctrl = snap.controls;
    let mn = -30;
    let mx = 25;
    if (ctrl) {
      if (ctrl.gauge_min != null && Number.isFinite(Number(ctrl.gauge_min))) mn = Number(ctrl.gauge_min);
      if (ctrl.gauge_max != null && Number.isFinite(Number(ctrl.gauge_max))) mx = Number(ctrl.gauge_max);
    }
    return { ymin: String(mn), ymax: String(mx) };
  }

  function updateGaugeBar(el, value) {
    const fill = el.querySelector(".gauge-bar-fill");
    if (!fill) return;
    const bounds = parseGaugeBounds(el);
    fill.style.background = gaugeGradient(el, bounds);
    if (value === null || value === undefined || value === "—") {
      fill.style.width = "0%";
      return;
    }
    const n = typeof value === "number" ? value : parseFloat(String(value).replace(/,/g, ""));
    if (!Number.isFinite(n)) {
      fill.style.width = "0%";
      return;
    }
    const { min, max } = bounds;
    const pct = ((n - min) / (max - min)) * 100;
    fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  }

  function applySnap(snap) {
    lastSnap = snap;
    if (snap.connection) {
      const line = document.getElementById("hdr-serial");
      if (line) {
        line.textContent = snap.connection.serial_port + " @ " + snap.connection.baudrate;
      }
      const mockEl = document.getElementById("hdr-mock");
      if (mockEl) {
        mockEl.textContent = snap.connection.mock_modem ? "MOCK modem" : "HW modem";
      }
    }
    if (snap.modem) {
      const hwEl = document.getElementById("hdr-modem-hw");
      const fwEl = document.getElementById("hdr-modem-fw");
      if (hwEl) hwEl.textContent = snap.modem.hw || "—";
      if (fwEl) fwEl.textContent = snap.modem.fw || "—";
      const stateEl = document.getElementById("hdr-modem-state");
      if (stateEl) {
        const st = String(snap.modem.state || "degraded").toLowerCase();
        stateEl.classList.remove("modem-state--ok", "modem-state--degraded", "modem-state--offline");
        if (st === "ok") stateEl.classList.add("modem-state--ok");
        else if (st === "offline") stateEl.classList.add("modem-state--offline");
        else stateEl.classList.add("modem-state--degraded");
        stateEl.textContent = st === "ok" ? "MODEM OK" : st === "offline" ? "MODEM OFFLINE" : "MODEM DEGRADED";
        stateEl.title = snap.modem.status || "";
      }
      document.querySelectorAll(".js-ctrl-modem-state").forEach((el) => {
        const st = String(snap.modem.state || "offline").toLowerCase();
        const serialOpen = !!(snap.connection && snap.connection.serial_open);
        const connected = serialOpen && st !== "offline";
        el.textContent = connected ? "Modem connected" : "Modem not connected";
        el.classList.toggle("modem-conn-status--ok", connected);
        el.classList.toggle("modem-conn-status--bad", !connected);
        el.title = snap.modem.status || "";
      });
    }
    if (snap.controls) window.__lastControls = snap.controls;
    if (snap.controls) {
      const sac = snap.controls.scan_active_channel;
      document.querySelectorAll("[data-scan-led]").forEach((el) => {
        const key = el.getAttribute("data-scan-led");
        const want = sac != null && sac !== "" && key != null;
        const on = want && String(key) === String(sac);
        el.classList.toggle("scan-led--on", on);
        const g = el.querySelector(".scan-led-graphic");
        if (g) {
          g.setAttribute("fill", on ? "#39ff14" : "#000000");
          g.setAttribute("stroke", on ? "#e8ffe8" : "#525252");
        }
      });
    }
    CHANNEL_KEYS.forEach((ch) => {
      const d = snap[ch];
      if (!d) return;
      document.querySelectorAll(`article.panel[data-group="${ch}"]`).forEach((panel) => {
        panel.classList.toggle("panel-stale", !!d.stale);
      });
      document.querySelectorAll(`.js-ch[data-channel="${ch}"]`).forEach((el) => {
        const field = el.dataset.field;
        if (!field) return;
        if (el.type === "checkbox" && field === "channel_enabled") {
          el.checked = !!d.channel_enabled;
          return;
        }
        if (el.tagName === "SELECT") {
          if (field === "band_eutra") el.value = String(d.band_eutra);
          if (field === "bw_mhz") el.value = String(d.bw_mhz);
          return;
        }
        if (el.type === "text" && field === "mno") {
          el.value = d.mno ?? "";
          return;
        }
        if (el.type === "number") {
          /* Do not clobber numeric edits while focused — WS updates can reset mid-typing. */
          if (document.activeElement === el) return;
          if (field === "earfcn") el.value = String(d.earfcn);
          if (field === "atten_db") el.value = String(d.atten_db);
        }
      });
      updateChannelCentreFreqDisplay(ch);
      document.querySelectorAll(`.js-gauge[data-channel="${ch}"]`).forEach((el) => {
        const m = el.dataset.metric;
        let v = d.rssi_dbm;
        if (m === "rssi_avg") v = d.rssi_avg;
        if (m === "rssi_sd") v = d.rssi_sd;
        const raw = v;
        if (v === null || v === undefined) v = "—";
        const gv = el.querySelector(".gauge-value");
        if (gv) gv.textContent = v;
        updateGaugeBar(el, raw === null || raw === undefined ? "—" : raw);
      });
      document.querySelectorAll(`.js-meas-count[data-channel="${ch}"]`).forEach((el) => {
        el.textContent = d.measurement_count;
      });
    });

    if (snap.composite) {
      const d = snap.composite;
      document.querySelectorAll('.js-gauge[data-channel="composite"]').forEach((el) => {
        const m = el.dataset.metric;
        let v = d[m];
        const raw = v;
        if (v === null || v === undefined) v = "—";
        const gv = el.querySelector(".gauge-value");
        if (gv) gv.textContent = v;
        updateGaugeBar(el, raw === null || raw === undefined ? "—" : raw);
      });
    }

    document.querySelectorAll(".chart-canvas").forEach((canvas) => {
      const ch = canvas.dataset.channel;
      const kind = canvas.dataset.chartKind;
      const d = snap[ch];
      if (!d) return;
      let points;
      if (ch === "composite") {
        if (kind === "composite_avg") points = d.chart_composite_avg;
        else if (kind === "composite_sd") points = d.chart_composite_sd;
        else if (kind === "all_cc_rssi") points = d.chart_all_cc_rssi;
        else points = d.chart_composite_avg;
      } else {
        if (kind === "rssi_avg") points = d.chart_rssi_avg;
        else if (kind === "rssi_sd") points = d.chart_rssi_sd;
        else points = [];
      }
      const chart = ensureChart(canvas);
      let ymin = canvas.dataset.ymin;
      let ymax = canvas.dataset.ymax;
      const ax = chartYAxisFromGauge(snap, kind);
      if (ax) {
        ymin = ax.ymin;
        ymax = ax.ymax;
      }
      pushSeries(chart, points || [], ymin, ymax);
    });

    const logEl = document.getElementById("at-log");
    if (logEl && snap.at_log) logEl.textContent = snap.at_log.join("\n");

    const ca = document.querySelector(".js-control-all");
    if (ca && snap.controls) {
      const c = snap.controls;
      if (c.all_channels_on) {
        ca.checked = true;
        ca.indeterminate = false;
      } else if (!c.any_channel_on) {
        ca.checked = false;
        ca.indeterminate = false;
      } else {
        ca.checked = false;
        ca.indeterminate = true;
      }
    }

    if (snap.controls) {
      document.querySelectorAll(".js-ctrl-uptime").forEach((el) => {
        if (snap.controls.uptime != null) el.textContent = snap.controls.uptime;
      });
      document.querySelectorAll(".js-ctrl-watchdog").forEach((el) => {
        if (snap.controls.watchdog != null) el.textContent = snap.controls.watchdog;
      });
      document.querySelectorAll(".js-ctrl-scan-count").forEach((el) => {
        if (snap.controls.scan_count != null) el.textContent = snap.controls.scan_count;
      });
    }
    pushLteVizRuntime(snap);
  }

  function pushLteVizRuntime(snap) {
    const frame = document.getElementById("lte-viz-frame");
    if (!frame || !frame.contentWindow || !snap) return;
    const ch = {};
    for (let i = 0; i < 14; i++) {
      const key = `ch${i}`;
      ch[key] = snap[key] || null;
    }
    frame.contentWindow.postMessage(
      {
        type: "lte-viz-runtime",
        channels: ch,
      },
      window.location.origin
    );
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  const patch = debounce(async (channel, body) => {
    await fetch(`/api/runtime/${channel}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }, 250);

  function readChannelFieldValue(el, field) {
    if (el.type === "checkbox") return el.checked;
    if (el.tagName === "SELECT" && field === "band_eutra") return parseInt(el.value, 10);
    if (el.tagName === "SELECT" && field === "bw_mhz") return parseFloat(el.value);
    if (el.tagName === "SELECT" && field === "mno") return el.value;
    if (el.type === "number") {
      if (field === "atten_db") {
        const s = String(el.value).trim();
        if (s === "" || s === "-" || s === "." || s === "-.") return null;
        const v = parseFloat(s);
        return Number.isFinite(v) ? v : null;
      }
      return parseInt(el.value, 10);
    }
    return undefined;
  }

  document.addEventListener("change", (e) => {
    const el = e.target;
    if (el.classList.contains("js-control-all")) {
      fetch("/api/runtime/all-channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel_enabled: el.checked }),
      })
        .then((r) => r.json())
        .then((j) => {
          if (j.ok) applySnap(j);
        });
      return;
    }
    if (!el.classList.contains("js-ch")) return;
    const ch = el.dataset.channel;
    const field = el.dataset.field;
    if (field === "mno") return;
    if (field === "earfcn" || field === "band_eutra") {
      updateChannelCentreFreqDisplay(ch);
    }
    const val = readChannelFieldValue(el, field);
    if (field === "atten_db" && val === null) return;
    patch(ch, { [field]: val });
  });

  /* Attenuation: debounced input so values save while typing, not only on blur. */
  const patchAtten = debounce((channel, v) => {
    if (!Number.isFinite(v)) return;
    patch(channel, { atten_db: v });
  }, 400);

  document.addEventListener("input", (e) => {
    const el = e.target;
    if (
      el.classList.contains("js-ch") &&
      (el.dataset.field === "earfcn" || el.dataset.field === "band_eutra")
    ) {
      updateChannelCentreFreqDisplay(el.dataset.channel);
    }
    if (!el.classList.contains("js-ch") || el.dataset.field !== "atten_db") return;
    const s = String(el.value).trim();
    if (s === "" || s === "-" || s === "." || s === "-.") return;
    const v = parseFloat(s);
    if (!Number.isFinite(v)) return;
    patchAtten(el.dataset.channel, v);
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-control-action]");
    if (!btn || btn.disabled) return;
    const act = btn.dataset.controlAction;
    let url = null;
    let body;
    if (act === "clear-charts") url = "/api/runtime/clear-charts";
    else if (act === "zero-gauges") url = "/api/runtime/zero-gauges";
    else if (act === "preload-mno-common") url = "/api/runtime/preload-mno-common";
    if (!url) return;
    e.preventDefault();
    fetch(url, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body,
    })
      .then((r) => r.json())
      .then((j) => {
        if (j.ok) applySnap(j);
        else if (j.error) alert(j.error);
      });
  });

  document.querySelectorAll(".chart-canvas").forEach((canvas) => ensureChart(canvas));

  if (window.__SNAP) applySnap(window.__SNAP);
  updateAllCentreFreqDisplays();

  (function initTabs() {
    const tabs = document.querySelectorAll(".app-tab");
    const dash = document.getElementById("panel-dashboard");
    const viz = document.getElementById("panel-lte-viz");
    const sett = document.getElementById("panel-settings");
    if (!tabs.length || !dash || !sett || !viz) return;
    tabs.forEach((btn) => {
      btn.addEventListener("click", () => {
        const name = btn.dataset.tab;
        tabs.forEach((b) => {
          const on = b === btn;
          b.classList.toggle("app-tab--active", on);
          b.setAttribute("aria-selected", on ? "true" : "false");
        });
        const showDash = name === "dashboard";
        const showViz = name === "lte-viz";
        const showSett = name === "settings";
        dash.classList.toggle("is-hidden", !showDash);
        dash.classList.toggle("tab-panel--active", showDash);
        viz.classList.toggle("is-hidden", !showViz);
        viz.classList.toggle("tab-panel--active", showViz);
        sett.classList.toggle("is-hidden", !showSett);
        sett.classList.toggle("tab-panel--active", showSett);
        if (name === "settings") {
          fetch("/api/config/dashboard")
            .then((r) => r.json())
            .then((j) => {
              if (!j.ok) return;
              const f = document.getElementById("form-dashboard-config");
              if (!f) return;
              const sp = f.querySelector('[name="serial_port"]');
              const bd = f.querySelector('[name="baudrate"]');
              const mk = f.querySelector('[name="mock_modem"]');
              const sc = f.querySelector('[name="scan_channel_delay_sec"]');
              const sr = f.querySelector('[name="scan_round_delay_sec"]');
              const wh = f.querySelector('[name="ws_push_hz"]');
              const rss = f.querySelector('[name="rssi_smooth_samples"]');
              const css = f.querySelector('[name="composite_smooth_samples"]');
              if (sp) sp.value = j.serial_port ?? "";
              if (bd) bd.value = j.baudrate ?? 115200;
              /* Mock mode is CLI/env-controlled; show current state read-only. */
              if (mk) mk.checked = !!j.mock_modem;
              if (sc) sc.value = j.scan_channel_delay_sec ?? 1;
              if (sr) sr.value = j.scan_round_delay_sec ?? 0;
              if (wh) wh.value = j.ws_push_hz ?? 4;
              if (rss) rss.value = j.rssi_smooth_samples ?? 5;
              if (css) css.value = j.composite_smooth_samples ?? 10;
              fetch("/api/config/mno-common")
                .then((r) => r.json())
                .then((mj) => {
                  if (mj && mj.ok && mj.mno_common_preset) {
                    applyMnoPresetToForm(mj.mno_common_preset, f);
                  }
                })
                .catch(() => {});
              const gmn = f.querySelector('[name="cfg_gauge_min"]');
              const gmx = f.querySelector('[name="cfg_gauge_max"]');
              const setG = (el, val) => {
                if (!el) return;
                el.value = val == null || val === undefined ? "" : String(val);
              };
              setG(gmn, j.gauge_min);
              setG(gmx, j.gauge_max);
              if (j.band_attenuation_db) applyBandAttenToForm(j.band_attenuation_db);
            })
            .catch(() => {});
        }
      });
    });
  })();

  (function initLteVizTabs() {
    const frame = document.getElementById("lte-viz-frame");
    const tabs = document.querySelectorAll(".lte-viz-tab");
    if (!frame || !tabs.length) return;
    frame.addEventListener("load", () => {
      if (lastSnap) pushLteVizRuntime(lastSnap);
    });
    tabs.forEach((btn) => {
      btn.addEventListener("click", () => {
        const src = btn.dataset.vizSrc;
        if (src) frame.src = src;
        tabs.forEach((t) => {
          const on = t === btn;
          t.classList.toggle("is-active", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
        });
      });
    });
  })();

  (function initSettingsForm() {
    const form = document.getElementById("form-dashboard-config");
    const status = document.getElementById("settings-save-status");
    if (!form) return;
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      syncMnoSelectValues(form);
      const fd = new FormData(form);
      const body = {
        serial_port: String(fd.get("serial_port") || "").trim(),
        baudrate: parseInt(String(fd.get("baudrate") || "115200"), 10),
        scan_channel_delay_sec: parseFloat(String(fd.get("scan_channel_delay_sec") || "1")),
        scan_round_delay_sec: parseFloat(String(fd.get("scan_round_delay_sec") || "0")),
        ws_push_hz: parseFloat(String(fd.get("ws_push_hz") || "4")),
        rssi_smooth_samples: parseInt(String(fd.get("rssi_smooth_samples") || "5"), 10),
        composite_smooth_samples: parseInt(
          String(fd.get("composite_smooth_samples") || "10"),
          10
        ),
        band_attenuation_db: collectBandAttenTable(),
        gauge_min: parseCfgNullableFloat(fd.get("cfg_gauge_min")),
        gauge_max: parseCfgNullableFloat(fd.get("cfg_gauge_max")),
      };
      if (!body.serial_port) {
        if (status) {
          status.textContent = "Serial port is required.";
          status.className = "settings-save-status is-err";
        }
        return;
      }
      if (status) {
        status.textContent = "Saving…";
        status.className = "settings-save-status";
      }
      fetch("/api/config/dashboard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then((r) => r.json())
        .then((j) => {
          if (j.ok) {
            applySnap(j);
            if (status) {
              status.textContent = "Saved.";
              status.className = "settings-save-status is-ok";
            }
          } else {
            if (status) {
              status.textContent = j.error || "Save failed.";
              status.className = "settings-save-status is-err";
            }
          }
        })
        .catch(() => {
          if (status) {
            status.textContent = "Network error.";
            status.className = "settings-save-status is-err";
          }
        });
    });

    const mnoBtn = document.getElementById("js-mno-preset-save");
    const mnoStatus = document.getElementById("js-mno-preset-status");
    if (mnoBtn) {
      mnoBtn.addEventListener("click", () => {
        const mnoPreset = collectMnoCommonPreset(form);
        if (mnoStatus) {
          mnoStatus.textContent = "Saving…";
          mnoStatus.className = "settings-save-status";
        }
        fetch("/api/config/mno-common", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(mnoPreset),
        })
          .then((r) => r.json())
          .then((j) => {
            if (j && j.ok) {
              if (j.mno_common_preset) applyMnoPresetToForm(j.mno_common_preset, form);
              applySnap(j);
              if (mnoStatus) {
                mnoStatus.textContent = "MNO preset saved.";
                mnoStatus.className = "settings-save-status is-ok";
              }
            } else if (mnoStatus) {
              mnoStatus.textContent = (j && j.error) || "Save failed.";
              mnoStatus.className = "settings-save-status is-err";
            }
          })
          .catch(() => {
            if (mnoStatus) {
              mnoStatus.textContent = "Network error.";
              mnoStatus.className = "settings-save-status is-err";
            }
          });
      });
    }
  })();

  // Live gauge scale apply (typing into Gauge min/max updates the gauges immediately).
  (function initGaugeScaleLivePatch() {
    const form = document.getElementById("form-dashboard-config");
    if (!form) return;
    const gmn = form.querySelector('[name="cfg_gauge_min"]');
    const gmx = form.querySelector('[name="cfg_gauge_max"]');
    if (!gmn && !gmx) return;

    const doPatch = debounce(() => {
      const body = {
        gauge_min: parseCfgNullableFloat(gmn ? gmn.value : null),
        gauge_max: parseCfgNullableFloat(gmx ? gmx.value : null),
      };
      fetch("/api/runtime/gauge-ranges", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then((r) => r.json())
        .then((j) => {
          if (j && j.ok) applySnap(j);
        })
        .catch(() => {});
    }, 200);

    [gmn, gmx].forEach((el) => {
      if (!el) return;
      el.addEventListener("input", doPatch);
      el.addEventListener("change", doPatch);
    });
  })();

  (function initBandAttenTableControls() {
    const tb = document.getElementById("js-band-atten-tbody");
    if (tb) {
      tb.addEventListener("click", (e) => {
        const btn = e.target.closest(".btn-band-atten-del");
        if (btn) btn.closest("tr")?.remove();
      });
    }
    document.getElementById("js-band-atten-add")?.addEventListener("click", () => {
      const tbody = document.getElementById("js-band-atten-tbody");
      if (tbody) addBandAttenRow(tbody, "", "");
    });
  })();

  const wsProto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(wsProto + "//" + location.host + "/ws");
  ws.onmessage = (ev) => {
    try {
      applySnap(JSON.parse(ev.data));
    } catch (_) {}
  };
})();
