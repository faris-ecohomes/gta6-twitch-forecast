import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params, load_pool, model_pred

def show(tag, P):
    r = score_params(P)
    print(f"{tag:52s} all {r['all']:.4f} | rolling {r['rolling']:.4f} | gta {r['gta']:.4f}")
    return r

C = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.15,
     "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9, "gamma": 0.85,
     "pre_sigma": 1.2}
show("combo+pre1.2", C)
show("+ smooth_comp=1", {**C, "smooth_comp": 1})
show("+ gamma_late=0.7", {**C, "gamma_late": 0.7})
show("+ smooth1 + gamma_late=0.7", {**C, "smooth_comp": 1, "gamma_late": 0.7})
for s in (0.75, 0.8, 1.0):
    show(f"sigma={s} (+pre, gl0.7)", {**C, "scale_sigma": s, "gamma_late": 0.7})
for ea in (0.1, 0.2, 0.25):
    show(f"ea={ea} (+pre, gl0.7)", {**C, "ea_factor": ea, "gamma_late": 0.7})
for rm in (0.45, 0.75):
    show(f"roll_mixed={rm} (+pre, gl0.7)", {**C, "roll_mixed": rm, "gamma_late": 0.7})
for rg in (0.05, 0.2, 0.35):
    show(f"roll_global={rg} (+pre, gl0.7)", {**C, "roll_global": rg, "gamma_late": 0.7})

# coverage of the leading config on rolling + gta subsets
P = {**C, "gamma_late": 0.7}
pool = load_pool()
for label, sel in (("rolling", lambda c: c["unlock"] in ("rolling", "mixed")),
                   ("gta-like", lambda c: c["unlock"] in ("rolling", "mixed")
                    and c["mode"] == "sp" and not c["has_pc"])):
    inside = tot = 0
    for comp in pool:
        if not sel(comp):
            continue
        t = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
             "has_pc": comp["has_pc"], "mode": comp["mode"], "year": comp["year"],
             "vpc1": comp["vpc1"], "pre_max": comp["pre_max"],
             "p1": float(comp["day"][1])}
        pred = model_pred(t, pool, P)
        for h in range(2, 25):
            y = comp["day"][h]
            tot += 1
            if pred[h][0] <= y <= pred[h][4]:
                inside += 1
    print(f"coverage[{label}] = {inside/tot:.3f} over {tot} hours")
