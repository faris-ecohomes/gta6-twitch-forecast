import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, load_pool, model_pred

P = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
     "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9, "gamma": 0.85,
     "pre_sigma": 1.2, "gamma_late": 0.7}
pool = load_pool()
for label, sel in (("rolling", lambda c: c["unlock"] in ("rolling", "mixed")),
                   ("gta-like", lambda c: c["unlock"] in ("rolling", "mixed")
                    and c["mode"] == "sp" and not c["has_pc"])):
    errs = {h: [] for h in range(2, 25)}
    for comp in pool:
        if not sel(comp):
            continue
        t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
             "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
             "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
             "p1": float(comp["day"][1])}
        pred = model_pred(t, pool, P)
        for h in range(2, 25):
            errs[h].append(math.log(comp["day"][h]) - math.log(pred[h][2]))
    print(label, "mean signed log-err of median by hour (actual - predicted):")
    print("  " + " ".join(f"{h}:{sum(errs[h])/len(errs[h]):+.2f}" for h in range(2, 25)))
