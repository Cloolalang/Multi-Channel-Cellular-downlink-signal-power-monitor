"""Load Phase-1 ui_* definitions from flows.json (MC-DSPM dashboard)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Function node that fans out the "Pre-load MNO Common" button payload to change nodes.
MNO_COMMON_FN_ID = "028fa85211a887be"

# Sector 1 tab — ui_group ids for Channel 0 … Channel 13 (order matches ch0…ch13).
CHANNEL_GROUP_IDS: tuple[str, ...] = (
    "eff2e3723fcad433",
    "eddd60f951544d6d",
    "bdfd84092ab34eb4",
    "fb831d7e1ae43d16",
    "e17cc135bf23ef85",
    "55993677934ebe50",
    "7ccd128779aab4ba",
    "f5a8343738b68d85",
    "ed97332a84b09df6",
    "ce2898c8f5e91690",
    "9664c745c9b02cd4",
    "8e7385b0139fdf36",
    "c577cde4ba263221",
    "680fd6a06e1217eb",
)
CHANNEL_COUNT = len(CHANNEL_GROUP_IDS)
_GROUP_TO_INDEX = {gid: i for i, gid in enumerate(CHANNEL_GROUP_IDS)}

COMPOSITE_GROUP = "6e24f381c3bac9d4"
CONTROLS_GROUP = "8cc90b8d61ab2e81"
SECTOR1_FLOW = "2d81681b3a2dcca8"


def channel_prefixes() -> list[str]:
    return [f"ch{i}" for i in range(CHANNEL_COUNT)]


VALID_CHANNEL_PREFIXES = frozenset(channel_prefixes())

# Defaults for settings UI / stored preset when flows have no MNO Common block.
MNO_DROPDOWN_LABELS: tuple[str, ...] = ("Vodafone", "VMO2", "EE", "H3G")
BW_MHZ_OPTIONS: tuple[int, ...] = (5, 10, 15, 20)


@dataclass(frozen=True)
class MnoCommonPreset:
    """Per-channel RF fields from Node-RED Pre-load MNO Common (None = leave unchanged)."""

    earfcn: tuple[int | None, ...]
    band_eutra: tuple[int | None, ...]
    bw_mhz: tuple[int | None, ...]
    mno: tuple[str | None, ...]


def _parse_intish(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return int(float(str(raw).strip()))
        except (TypeError, ValueError):
            return None


def parse_mno_common_preset(flows_path: Path) -> MnoCommonPreset | None:
    """Walk flows: Pre-load MNO Common → change nodes → ui widgets per channel group."""
    data = json.loads(flows_path.read_text(encoding="utf-8"))
    nodes: dict[str, dict[str, Any]] = {n["id"]: n for n in data}
    fn = nodes.get(MNO_COMMON_FN_ID)
    if not fn or fn.get("type") != "function":
        return None
    fan = (fn.get("wires") or [[]])[0]
    if not fan:
        return None

    earfcn_ids: dict[str, int] = {}
    band_ids: dict[str, int] = {}
    bw_ids: dict[str, int] = {}
    mno_ids: dict[str, int] = {}
    for n in data:
        if n.get("z") != SECTOR1_FLOW:
            continue
        g = n.get("group")
        idx = _GROUP_TO_INDEX.get(g) if g else None
        if idx is None:
            continue
        nid = str(n["id"])
        t = n.get("type")
        if t == "ui_text_input" and n.get("label") == "Band":
            band_ids[nid] = idx
        elif t == "ui_text_input" and n.get("label") == "DL EARFCN":
            earfcn_ids[nid] = idx
        elif t == "ui_dropdown" and n.get("label") == "Bandwidth":
            bw_ids[nid] = idx
        elif t == "ui_dropdown" and n.get("label") == "MNO":
            mno_ids[nid] = idx

    ch_earfcn: list[int | None] = [None] * CHANNEL_COUNT
    ch_band: list[int | None] = [None] * CHANNEL_COUNT
    ch_bw: list[int | None] = [None] * CHANNEL_COUNT
    ch_mno: list[str | None] = [None] * CHANNEL_COUNT

    for cid in fan:
        n = nodes.get(str(cid))
        if not n or n.get("type") != "change":
            continue
        rules = n.get("rules") or []
        if not rules:
            continue
        r0 = rules[0]
        raw = r0.get("to")
        targets = (n.get("wires") or [[]])[0]
        for tid in targets:
            sid = str(tid)
            if sid in earfcn_ids:
                v = _parse_intish(raw)
                if v is not None:
                    ch_earfcn[earfcn_ids[sid]] = v
            if sid in band_ids:
                v = _parse_intish(raw)
                if v is not None:
                    ch_band[band_ids[sid]] = v
            if sid in bw_ids:
                v = _parse_intish(raw)
                if v is not None:
                    ch_bw[bw_ids[sid]] = v
            if sid in mno_ids:
                if raw is not None:
                    ch_mno[mno_ids[sid]] = str(raw)

    return MnoCommonPreset(
        earfcn=tuple(ch_earfcn),
        band_eutra=tuple(ch_band),
        bw_mhz=tuple(ch_bw),
        mno=tuple(ch_mno),
    )


def _normalize_mno_cell(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _normalize_int_cell(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            return int(float(str(val).strip()))
        except (TypeError, ValueError):
            return None


def _list_column(raw: dict[str, Any], key: str) -> list[Any]:
    v = raw.get(key)
    if not isinstance(v, list):
        return []
    return v


def mno_preset_from_stored_dict(raw: dict[str, Any] | None) -> MnoCommonPreset | None:
    """Build preset from dashboard_config.json `mno_common_preset` object."""
    if raw is None or not isinstance(raw, dict):
        return None
    ear_l = _list_column(raw, "earfcn")
    band_l = _list_column(raw, "band_eutra")
    bw_l = _list_column(raw, "bw_mhz")
    mno_l = _list_column(raw, "mno")
    ch_earfcn: list[int | None] = []
    ch_band: list[int | None] = []
    ch_bw: list[int | None] = []
    ch_mno: list[str | None] = []
    for i in range(CHANNEL_COUNT):
        ch_earfcn.append(_normalize_int_cell(ear_l[i]) if i < len(ear_l) else None)
        ch_band.append(_normalize_int_cell(band_l[i]) if i < len(band_l) else None)
        ch_bw.append(_normalize_int_cell(bw_l[i]) if i < len(bw_l) else None)
        ch_mno.append(_normalize_mno_cell(mno_l[i]) if i < len(mno_l) else None)
    return MnoCommonPreset(
        earfcn=tuple(ch_earfcn),
        band_eutra=tuple(ch_band),
        bw_mhz=tuple(ch_bw),
        mno=tuple(ch_mno),
    )


def mno_preset_to_form_dict(preset: MnoCommonPreset) -> dict[str, Any]:
    """API/settings form shape: parallel arrays per channel index."""
    return {
        "band_eutra": [preset.band_eutra[i] for i in range(CHANNEL_COUNT)],
        "earfcn": [preset.earfcn[i] for i in range(CHANNEL_COUNT)],
        "bw_mhz": [preset.bw_mhz[i] for i in range(CHANNEL_COUNT)],
        "mno": [preset.mno[i] for i in range(CHANNEL_COUNT)],
    }


def default_mno_form_dict() -> dict[str, Any]:
    """Fallback when no flows preset and nothing stored yet."""
    return {
        "band_eutra": [20] * CHANNEL_COUNT,
        "earfcn": [6400] * CHANNEL_COUNT,
        "bw_mhz": [10] * CHANNEL_COUNT,
        "mno": ["EE"] * CHANNEL_COUNT,
    }


def _normalize_mno_common_form_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Ensure parallel arrays exist with length CHANNEL_COUNT (null-padded) for templates and GET /api."""
    out = dict(d)
    for key in ("band_eutra", "earfcn", "bw_mhz", "mno"):
        col = out.get(key)
        if not isinstance(col, list):
            col = []
        out[key] = [col[i] if i < len(col) else None for i in range(CHANNEL_COUNT)]
    return out


def resolved_mno_common_form_dict(
    stored: dict[str, Any] | None,
    flows_path: Path,
) -> dict[str, Any]:
    """Form/API payload: saved dashboard preset wins; else flows.json MNO Common; else defaults."""
    if stored is not None:
        return _normalize_mno_common_form_dict(stored)
    if flows_path.is_file():
        fp = parse_mno_common_preset(flows_path)
        if fp is not None:
            return mno_preset_to_form_dict(fp)
    return default_mno_form_dict()


def load_phase1_widgets(flows_path: Path) -> list[dict[str, Any]]:
    data = json.loads(flows_path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for node in data:
        t = node.get("type", "")
        if not t.startswith("ui_"):
            continue
        if node.get("group") not in CHANNEL_GROUP_IDS:
            continue
        if node.get("z") != SECTOR1_FLOW:
            continue
        slim = {k: v for k, v in node.items() if k not in ("x", "y", "wires")}
        out.append(slim)
    out.sort(key=lambda n: (n.get("group", ""), n.get("order", 0), n.get("id", "")))
    return out


def widgets_by_channels(widgets: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(CHANNEL_COUNT)]
    for w in widgets:
        g = w.get("group")
        idx = _GROUP_TO_INDEX.get(g)
        if idx is not None:
            buckets[idx].append(w)
    for b in buckets:
        b.sort(key=lambda n: (n.get("order", 0), n.get("id", "")))
    return buckets


def load_controls_widgets(flows_path: Path) -> list[dict[str, Any]]:
    data = json.loads(flows_path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for node in data:
        t = node.get("type", "")
        if not t.startswith("ui_"):
            continue
        if node.get("group") != CONTROLS_GROUP:
            continue
        if node.get("z") != SECTOR1_FLOW:
            continue
        if node.get("d") is True:
            continue
        slim = {k: v for k, v in node.items() if k not in ("x", "y", "wires")}
        out.append(slim)
    out.sort(key=lambda n: (n.get("order", 0), n.get("id", "")))
    return out


def load_composite_widgets(flows_path: Path) -> list[dict[str, Any]]:
    data = json.loads(flows_path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for node in data:
        t = node.get("type", "")
        if not t.startswith("ui_"):
            continue
        if node.get("group") != COMPOSITE_GROUP:
            continue
        if node.get("z") != SECTOR1_FLOW:
            continue
        slim = {k: v for k, v in node.items() if k not in ("x", "y", "wires")}
        out.append(slim)
    out.sort(key=lambda n: (n.get("order", 0), n.get("id", "")))
    return out
