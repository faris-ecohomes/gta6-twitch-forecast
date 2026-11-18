"""Residual bias by hour x anchor-ratio band (anchored cases), + channel stats."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, load_pool, model_pred

BEST = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
        "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
        "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7,
        "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3}

pool = load_pool()
bands = {"a<0.45": [], "a>=0.45": []}
for comp in pool:
    if comp["day"][1] <= 6000 and comp["day"][1] / comp["pre_max"] <= 0.6:
        continue  # gated
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "text": comp["text"],
         "day_start": comp["day_start"], "pre_max": comp["pre_max"],
         "p1": float(comp["day"][1])}
    pred = model_pred(t, pool, BEST)
    band = "a<0.45" if t["p1"] / comp["pre_max"] < 0.45 else "a>=0.45"
    bands[band].append((comp, pred))

for band, items in bands.items():
    print(f"\n{band}: n={len(items)}  mean signed log-err of q50 (actual - pred)")
    line = []
    for h in range(2, 25):
        errs = [math.log(c["day"][h]) - math.log(p[h][2]) for c, p in items]
        line.append(f"{h}:{sum(errs)/len(errs):+.2f}")
    print("  " + " ".join(line))

print("\nchannel stats: name, ch1, ch_peak, ch growth, vpc1, vpc@peak, plateau")
for comp in pool:
    dch = comp["day_ch"]
    day = comp["day"]
    if not dch.get(1):
        continue
    ch_peak_h = max(dch, key=lambda h: dch[h])
    plateau = math.log(max(day.values()) / day[1])
    print(f"{comp['name'][:34]:34s} ch1={dch[1]:6.0f} chpk={dch[ch_peak_h]:6.0f} "
          f"growth={dch[ch_peak_h]/dch[1]:5.1f}x vpc1={comp['vpc1']:6.1f} "
          f"plateau={plateau:.2f}")
