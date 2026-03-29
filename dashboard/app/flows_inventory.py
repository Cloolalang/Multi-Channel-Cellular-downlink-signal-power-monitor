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
