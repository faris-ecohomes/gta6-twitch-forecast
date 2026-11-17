"""Round 2: combine round-1 winners, test robust quantiles and recency."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params


def show(tag, P):
    r = score_params(P)
    print(f"{tag:52s} all {r['all']:.4f} | rolling {r['rolling']:.4f} | gta {r['gta']:.4f}")
    return r


COMBO = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.15,
         "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9, "gamma": 0.95}

show("combo (normal)", COMBO)
show("combo robust", {**COMBO, "qmethod": "robust"})
show("combo empirical", {**COMBO, "qmethod": "empirical"})
for rt in (3.0, 5.0, 8.0):
    show(f"combo normal recency={rt}", {**COMBO, "recency_tau": rt})
    show(f"combo robust recency={rt}", {**COMBO, "qmethod": "robust", "recency_tau": rt})
for g in (0.8, 0.9, 1.0, 1.1):
    show(f"robust gamma={g}", {**COMBO, "qmethod": "robust", "gamma": g})
    show(f"normal gamma={g}", {**COMBO, "gamma": g})
for s in (0.7, 0.8, 1.0):
    show(f"robust sigma={s}", {**COMBO, "qmethod": "robust", "scale_sigma": s})
for pc in (0.45, 0.7, 0.9):
    show(f"robust pc_down={pc}", {**COMBO, "qmethod": "robust", "pc_mismatch_down": pc})
for wk in (0.2, 0.6, 1.0):
    show(f"robust weak={wk}", {**COMBO, "qmethod": "robust", "weak_factor": wk})
for mc in (0.4, 0.8):
    show(f"robust mode_coop={mc}", {**COMBO, "qmethod": "robust", "mode_coop": mc})
