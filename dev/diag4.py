"""Per-case losses under the gated config; inspect gated cases' forecasts."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, load_pool, model_pred, pinball_loss

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}
GATED = {**LOCKED, "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3}

pool = load_pool()
rows = []
for comp in pool:
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
         "p1": float(comp["day"][1])}
    l = pinball_loss(model_pred(t, pool, LOCKED), comp["day"])
    g = pinball_loss(model_pred(t, pool, GATED), comp["day"])
    rows.append((g, l, comp))
rows.sort(reverse=True)
print(f"{'target':42s} {'locked':>7s} {'gated':>7s}")
for g, l, comp in rows:
    mark = " GATE" if (comp["day"][1] <= 6000
                       and comp["day"][1] / comp["pre_max"] <= 0.6) else ""
    print(f"{comp['name'][:42]:42s} {l:7.3f} {g:7.3f}{mark}")
print(f"sum gated-config = {sum(r[0] for r in rows):.2f} "
      f"(mean {sum(r[0] for r in rows)/len(rows):.4f})")

# inspect two gated cases in level space
by_name = {c["name"]: c for c in pool}
for name in ("Black Myth: Wukong", "HELLDIVERS 2"):
    comp = by_name[name]
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
         "p1": float(comp["day"][1])}
    pred = model_pred(t, pool, GATED)
    print(f"\n{name}: actual level vs predicted q05/q50/q95 (thousands)")
    for h in range(2, 25):
        a = comp["day"][h] / 1000
        q = [pred[h][i] / 1000 for i in (0, 2, 4)]
        print(f" h{h:02d} act {a:8.1f}   q05 {q[0]:8.1f}  q50 {q[1]:8.1f}  "
              f"q95 {q[2]:8.1f}")
