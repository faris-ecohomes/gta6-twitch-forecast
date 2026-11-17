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
show("combo", C)
show("combo + pre1.2", {**C, "pre_sigma": 1.2})
show("combo + filterA", {**C, "pool_filter": "A"})
show("combo + filterB", {**C, "pool_filter": "B"})
show("combo + filterA + pre1.2", {**C, "pool_filter": "A", "pre_sigma": 1.2})
show("combo + filterB + pre1.2", {**C, "pool_filter": "B", "pre_sigma": 1.2})
for gl in (0.7, 1.0, 1.15):
    show(f"combo gamma_late={gl}", {**C, "gamma_late": gl})
    show(f"combo pre1.2 gamma_late={gl}", {**C, "pre_sigma": 1.2, "gamma_late": gl})
for g in (0.75, 0.8, 0.9):
    show(f"combo pre1.2 gamma={g}", {**C, "pre_sigma": 1.2, "gamma": g})
