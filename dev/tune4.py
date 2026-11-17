"""Per-target detail for the GTA-like and rolling subsets, pre-kernel on/off."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import (DEFAULT_PARAMS, load_pool, model_pred, baseline_pred,
                      pinball_loss)

C = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.15,
     "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9, "gamma": 0.85}

pool = load_pool()
print(f"{'target':45s} {'cls':8s} {'H1':>8s} {'pre/H1':>6s} {'base':>6s} {'plain':>6s} {'pre1.2':>6s} {'pre0.8':>6s}")
for comp in pool:
    if comp["unlock"] not in ("rolling", "mixed"):
        continue
    target = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
              "has_pc": comp["has_pc"], "mode": comp["mode"],
              "year": comp["year"], "vpc1": comp["vpc1"],
              "pre_max": comp["pre_max"], "p1": float(comp["day"][1])}
    bl = pinball_loss(baseline_pred(target["p1"]), comp["day"])
    m0 = pinball_loss(model_pred(target, pool, C), comp["day"])
    m1 = pinball_loss(model_pred(target, pool, {**C, "pre_sigma": 1.2}), comp["day"])
    m2 = pinball_loss(model_pred(target, pool, {**C, "pre_sigma": 0.8}), comp["day"])
    gta = " GTA-like" if (comp["mode"] == "sp" and not comp["has_pc"]) else ""
    print(f"{comp['name'][:45]:45s} {comp['unlock']:8s} {target['p1']:8.0f} "
          f"{comp['pre_max']/target['p1']:6.2f} {bl:6.3f} {m0:6.3f} {m1:6.3f} {m2:6.3f}{gta}")
