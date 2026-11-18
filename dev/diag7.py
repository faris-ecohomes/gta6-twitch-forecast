"""Inspect gated forecasts vs actuals (log levels) for the gated losers."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, load_pool, model_pred, pinball_loss

BEST = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
        "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
        "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7,
        "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3}
LOCKED = {**BEST, "gate_h1": None}

pool = load_pool()
by_name = {c["name"]: c for c in pool}
for name in ("Marathon", "Hollow Knight: Silksong", "ARC Raiders",
             "HELLDIVERS 2", "Battlefield 6"):
    comp = by_name[name]
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "text": comp["text"],
         "day_start": comp["day_start"], "pre_max": comp["pre_max"],
         "p1": float(comp["day"][1])}
    pred = model_pred(t, pool, BEST)
    lp = pinball_loss(pred, comp["day"])
    print(f"\n{name} gated loss {lp:.3f}  (log10 levels: act vs q05/q50/q95)")
    for h in range(2, 25):
        a = math.log10(comp["day"][h])
        q = [math.log10(pred[h][i]) for i in (0, 2, 4)]
        print(f" h{h:02d} act {a:5.2f}  q05 {q[0]:5.2f} q50 {q[1]:5.2f} "
              f"q95 {q[2]:5.2f}")
