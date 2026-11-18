"""Inspect predicted quantiles vs actual for the worst cases + pool makeup."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import (DEFAULT_PARAMS, load_pool, model_pred, comp_weight,
                      interp_log_ratio)

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}

pool = load_pool()
by_name = {c["name"]: c for c in pool}

for name in ("Marathon", "ARC Raiders", "Black Myth: Wukong",
             "Resident Evil Requiem", "Hollow Knight: Silksong"):
    comp = by_name[name]
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
         "p1": float(comp["day"][1])}
    pred = model_pred(t, pool, LOCKED)
    print(f"\n=== {name} (H1={t['p1']:.0f}, pre={comp['pre_max']:.0f}, "
          f"H1/pre={t['p1']/comp['pre_max']:.3f}, cls={comp['unlock']}) ===")
    print(" h   actlog  q05log q25log q50log q75log q95log")
    for h in range(2, 25):
        act = math.log(comp["day"][h] / t["p1"])
        qs = [math.log(q / t["p1"]) for q in pred[h]]
        print(f"{h:3d}  {act:+6.2f}  " + " ".join(f"{q:+6.2f}" for q in qs))
    ws = []
    for c in pool:
        if c["name"] == name:
            continue
        covered = sum(1 for h in range(1, 25) if c["day"].get(h))
        if covered < 18:
            continue
        w = comp_weight(t, c, LOCKED)
        if w > 1e-6:
            ws.append((w, c["name"]))
    ws.sort(reverse=True)
    tot = sum(w for w, _ in ws)
    ess = tot * tot / sum(w * w for w, _ in ws)
    print(f"pool: {len(ws)} comps, ESS={ess:.1f}; top: " +
          ", ".join(f"{n}={w/tot:.2f}" for w, n in ws[:6]))
