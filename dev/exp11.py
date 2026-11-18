"""Round 17: blend weight + stacking small winners."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}
BEST = {**LOCKED, "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3,
        "step_tau_offset": -2, "step_smooth": 1}


def show(tag, P):
    r = score_params(P)
    print(f"{tag:46s} all {r['all']:.4f} | rolling {r['rolling']:.4f} "
          f"| gta {r['gta']:.4f}")
    return r


show("BEST (smooth1, normal)", BEST)
for bw in (0.25, 0.4, 0.5, 0.65):
    show(f"blend_w={bw}", {**BEST, "qmethod": "blend", "blend_w": bw})
show("blend 0.4 + unk 0.15/0.35", {**BEST, "qmethod": "blend", "blend_w": 0.4,
                                   "unk_global": 0.15, "unk_mixed": 0.35})
show("blend 0.4 + scale=1.0", {**BEST, "qmethod": "blend", "blend_w": 0.4,
                               "scale_sigma": 1.0})
show("blend 0.4 + offset=-3", {**BEST, "qmethod": "blend", "blend_w": 0.4,
                               "step_tau_offset": -3})
