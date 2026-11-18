"""Diagnose: where does the ALL loss concentrate? Curve shapes + observables."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, load_pool, model_pred, pinball_loss

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}

pool = load_pool()

print(f"{'name':42s} {'cls':8s} {'mode':4s} {'pc':2s} {'ea':2s} {'H1':>8s} "
      f"{'peak':>8s} {'pkH':>3s} {'pk/H1':>6s} {'pre_max':>8s} {'H1/pre':>6s} {'loss':>6s}")
rows = []
for comp in pool:
    day = comp["day"]
    peak_h = max((h for h in range(1, 25) if day.get(h)), key=lambda h: day[h])
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
         "p1": float(day[1])}
    loss = pinball_loss(model_pred(t, pool, LOCKED), day)
    rows.append((loss, comp, peak_h))
    print(f"{comp['name'][:42]:42s} {comp['unlock']:8s} {comp['mode']:4s} "
          f"{str(comp['has_pc']):2s} {str(comp['ea']):2s} {day[1]:8.0f} "
          f"{day[peak_h]:8.0f} {peak_h:3d} {day[peak_h]/day[1]:6.1f} "
          f"{comp['pre_max']:8.0f} {day[1]/comp['pre_max']:6.2f} {loss:6.3f}")

tot = sum(r[0] for r in rows)
print(f"\ntotal loss-mass = {tot:.2f} over {len(rows)} cases")
for thr in (3, 6, 10, 20):
    n = sum(1 for _, c, ph in rows if c["day"][ph] / c["day"][1] >= thr)
    mass = sum(l for l, c, ph in rows if c["day"][ph] / c["day"][1] >= thr)
    print(f"peak/H1 >= {thr:2d}: n={n:2d}  loss-mass={mass:.2f} ({100*mass/tot:.0f}%)")

# per-hour loss profile for the worst cases
print("\nper-hour loss (worst 6 cases):")
rows.sort(reverse=True)
for loss, comp, ph in rows[:6]:
    t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
         "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
         "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
         "p1": float(comp["day"][1])}
    pred = model_pred(t, pool, LOCKED)
    per = []
    for h in range(2, 25):
        per.append(pinball_loss({h: pred[h]}, {h: comp["day"][h]}))
    print(f"{comp['name'][:30]:30s} " + " ".join(f"{v:.1f}" for v in per))
    print(f"{'actual log-ratio':30s} " + " ".join(
        f"{math.log(comp['day'][h]/comp['day'][1]):+.0f}" if comp["day"].get(h) else "  ."
        for h in range(2, 25)))
