import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params

def show(tag, P):
    r = score_params(P)
    print(f"{tag:52s} all {r['all']:.4f} | rolling {r['rolling']:.4f} | gta {r['gta']:.4f}")
    return r

C = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.15,
     "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9, "gamma": 0.85}
show("combo normal g0.85", C)
show("normalm", {**C, "qmethod": "normalm"})
show("blend", {**C, "qmethod": "blend"})
for g in (0.8, 0.9, 1.0):
    show(f"normalm gamma={g}", {**C, "qmethod": "normalm", "gamma": g})
    show(f"blend gamma={g}", {**C, "qmethod": "blend", "gamma": g})
for vs in (0.35, 0.5, 0.75):
    show(f"normal vpc_sigma={vs}", {**C, "vpc_sigma": vs})
    show(f"normalm vpc_sigma={vs}", {**C, "qmethod": "normalm", "vpc_sigma": vs})
for ps in (0.5, 0.8, 1.2):
    show(f"normal pre_sigma={ps}", {**C, "pre_sigma": ps})
    show(f"normalm pre_sigma={ps}", {**C, "qmethod": "normalm", "pre_sigma": ps})
