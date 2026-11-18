"""Round 12: around tau_offset=-2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}
BEST = {**LOCKED, "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3,
        "step_tau_offset": -2}


def show(tag, P):
    r = score_params(P)
    print(f"{tag:46s} all {r['all']:.4f} | rolling {r['rolling']:.4f} "
          f"| gta {r['gta']:.4f}")
    return r


show("BEST offset=-2", BEST)
show("offset=-3", {**BEST, "step_tau_offset": -3})
show("offset=-2 + blend 0.7", {**BEST, "step_blend": 0.7})
show("offset=-2 + cap6", {**BEST, "step_shift_cap": 6})
show("offset=-2 + gate_thresh=2.2", {**BEST, "gate_thresh": 2.2})
show("offset=-2 + gate_thresh=2.6", {**BEST, "gate_thresh": 2.6})
show("offset=-2 + level_gamma=0.9", {**BEST, "step_level_gamma": 0.9})
show("offset=-2 + level_gamma=1.1", {**BEST, "step_level_gamma": 1.1})
show("offset=-2 + level_temper=0.2", {**BEST, "step_level_temper": 0.2})
show("offset=-2 + level_temper=0.5", {**BEST, "step_level_temper": 0.5})
show("offset=-2 + gate_a=0.5", {**BEST, "gate_a": 0.5})
show("offset=-2 + gate_h1=4000", {**BEST, "gate_h1": 4000})
