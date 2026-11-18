"""Per-case comparison: LOCKED vs regime mixture; also print pi per target."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import (DEFAULT_PARAMS, load_pool, model_pred, pinball_loss,
                      comp_weight)

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}
REG = {**LOCKED, "regime": True}

pool = load_pool()
print(f"{'target':42s} {'a=H1/pre':>8s} {'locked':>7s} {'regime':>7s} {'diff':>7s}")
tot_l = tot_r = 0.0
for comp in pool:
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
         "p1": float(comp["day"][1])}
    l = pinball_loss(model_pred(t, pool, LOCKED), comp["day"])
    r = pinball_loss(model_pred(t, pool, REG), comp["day"])
    tot_l += l
    tot_r += r
    flag = "  <-- stepper" if math.log(
        max(comp["day"].values()) / comp["day"][1]) >= 1.386 else ""
    print(f"{comp['name'][:42]:42s} {t['p1']/comp['pre_max']:8.3f} "
          f"{l:7.3f} {r:7.3f} {r-l:+7.3f}{flag}")
print(f"{'TOTAL':42s} {'':8s} {tot_l:7.3f} {tot_r:7.3f} {tot_r-tot_l:+7.3f}")
