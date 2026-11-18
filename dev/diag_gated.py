"""Diagnose the 8 gated LOO cases under the round-1 model."""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import main_round1 as r1mod
from validate import KIT, LEVELS, load_pool
from eval2 import build_cases

GATED = ["Marathon", "ARC Raiders", "HELLDIVERS 2",
         "Kingdom Come: Deliverance II", "Baldur's Gate 3",
         "Hollow Knight: Silksong", "Battlefield 6", "Black Myth: Wukong"]


def hour_losses(pred, actual):
    out = {}
    for h in range(2, 25):
        if h not in actual:
            continue
        ly = math.log(max(1.0, float(actual[h])))
        tot = 0.0
        for tau, q in zip(LEVELS, pred[h]):
            d = ly - math.log(max(1e-9, q))
            tot += 2.0 * max(tau * d, (tau - 1.0) * d)
        out[h] = tot / len(LEVELS)
    return out


def main():
    raw_case = json.loads((KIT / "input/p00.in").read_text())
    raw_by_name = {c["name"]: c for c in raw_case["comparables"]}
    pool = {c["name"]: c for c in load_pool()}
    cases = {comp["name"]: case for comp, case, _, _ in build_cases()}

    for name in GATED:
        craw = raw_by_name[name]
        comp = pool[name]
        case = cases[name]
        tgt = r1mod.target_features(case)
        tau_t = r1mod.parse_unlock_step_hour(case.get("notes") or "",
                                             case.get("day_start") or "")
        day = comp["day"]
        peak_h = max(day, key=lambda h: day[h])
        # actual half-plateau hour
        plateau = math.log(max(day.values()) / day[1])
        tau_act = next((h for h in range(2, 25)
                        if r1mod.log_ratio(day, h) is not None
                        and r1mod.log_ratio(day, h) >= 0.5 * plateau), None)
        out = r1mod.forecast_case(case)
        pred = {row["hour"]: row["q"] for row in out["hours"]}
        hl = hour_losses(pred, day)
        worst_h = sorted(hl.items(), key=lambda kv: -kv[1])[:5]
        print(f"\n=== {name} ===")
        print(f"  unlock text: {craw['unlock']!r}")
        print(f"  H1={tgt['p1']:.0f} pre_max={tgt['pre_max']} "
              f"ratio={tgt['p1']/tgt['pre_max']:.3f} tau_t(parsed)={tau_t} "
              f"tau_actual(half-plateau)={tau_act} peak_h={peak_h} "
              f"peak={max(day.values()):.0f}")
        print(f"  worst hours: " + ", ".join(f"h{h}:{v:.2f}" for h, v in worst_h))
        med = {h: pred[h][2] for h in range(2, 25)}
        print("  hr:      " + " ".join(f"{h:>6d}" for h in range(2, 25)))
        print("  actual:  " + " ".join(f"{day.get(h, 0):6.0f}" for h in range(2, 25)))
        print("  q50:     " + " ".join(f"{med[h]:6.0f}" for h in range(2, 25)))


if __name__ == "__main__":
    main()
