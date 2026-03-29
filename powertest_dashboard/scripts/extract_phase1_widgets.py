"""Extract ui_* nodes for Channel 0 / Channel 1 groups from Powertest flows.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOWS = ROOT / "flows.json"
OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "phase1_widgets.json"

CH0 = "eff2e3723fcad433"
CH1 = "eddd60f951544d6d"
SECTOR1_FLOW = "2d81681b3a2dcca8"


def main() -> None:
    data = json.loads(FLOWS.read_text(encoding="utf-8"))
    out = []
    for node in data:
        t = node.get("type", "")
        if not t.startswith("ui_"):
            continue
        g = node.get("group")
        if g not in (CH0, CH1):
            continue
        z = node.get("z")
        if z != SECTOR1_FLOW:
            continue
        slim = {k: v for k, v in node.items() if k not in ("x", "y", "wires")}
        out.append(slim)
    out.sort(key=lambda n: (n.get("group", ""), n.get("order", 0), n.get("id", "")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} widgets to {OUT}")


if __name__ == "__main__":
    main()
