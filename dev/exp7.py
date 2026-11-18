"""Round 13: scale-mixture (heavy-tail) anchored predictive."""
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


show("BEST normal", BEST)
for eps, kk in ((0.15, 2.2), (0.2, 2.5), (0.1, 2.0), (0.25, 3.0),
                (0.15, 3.0), (0.3, 2.5)):
    show(f"mixn eps={eps} k={kk}", {**BEST, "qmethod": "mixn",
                                     "tail_mix": (eps, kk)})
show("mixn 0.2/2.5 offset=-3", {**BEST, "qmethod": "mixn",
                                "tail_mix": (0.2, 2.5), "step_tau_offset": -3})
