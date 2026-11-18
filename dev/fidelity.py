"""End-to-end fidelity: run the ported main.py on synthesized LOO cases.

Each pool comparable becomes a case in the real input format (notes built
from its platforms + unlock text, known = its hour-1 print, history = its
pre-launch rows, comparables = the full raw pool). Scores main.py's output
with the harness's exact pinball-log loss and subset definitions.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as entry
from validate import KIT, load_pool, pinball_loss


def synth_case(comp_raw, all_raw, day1):
    notes = (f"Released on {comp_raw['platforms']}. "
             f"real unlock: {comp_raw['unlock']}")
    hist = [{"from": pt["from"], "viewers": pt["viewers"],
             "channels": pt["channels"]}
            for pt in comp_raw["hourly"] if pt["from"] < comp_raw["day_start"]]
    return {
        "game": {"name": comp_raw["name"]},
        "notes": notes,
        "day_start": comp_raw["day_start"],
        "known": [{"hour": 1, "viewers": day1["viewers"],
                   "channels": day1["channels"]}],
        "history_hourly": hist,
        "forecast": [{"hour": h} for h in range(2, 25)],
        "comparables": all_raw,
    }


def main():
    raw_case = json.loads((KIT / "input/p00.in").read_text())
    all_raw = raw_case["comparables"]
    raw_by_name = {c["name"]: c for c in all_raw}
    pool = load_pool()
    sums = {"all": [], "rolling": [], "gta": []}
    worst = []
    for comp in pool:
        craw = raw_by_name[comp["name"]]
        day1 = next(pt for pt in craw["hourly"]
                    if pt["from"] == craw["day_start"])
        case = synth_case(craw, all_raw, day1)
        out = entry.forecast_case(case)
        pred = {row["hour"]: row["q"] for row in out["hours"]}
        loss = pinball_loss(pred, comp["day"])
        sums["all"].append(loss)
        worst.append((loss, comp["name"]))
        if comp["unlock"] in ("rolling", "mixed"):
            sums["rolling"].append(loss)
            if comp["mode"] == "sp" and not comp["has_pc"]:
                sums["gta"].append(loss)
    for k, v in sums.items():
        print(f"{k:8s} n={len(v):2d}  main.py LOO {sum(v)/len(v):.4f}")
    worst.sort(reverse=True)
    print("worst 5:", ", ".join(f"{n} {l:.3f}" for l, n in worst[:5]))


if __name__ == "__main__":
    main()
