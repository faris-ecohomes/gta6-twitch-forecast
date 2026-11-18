"""Round 16: stepper-curve smoothing in the gated path."""
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


show("BEST", BEST)
for k in (1, 2):
    show(f"step_smooth={k}", {**BEST, "step_smooth": k})
show("smooth1 + offset=-3", {**BEST, "step_smooth": 1, "step_tau_offset": -3})
show("smooth1 + blend qmethod", {**BEST, "step_smooth": 1, "qmethod": "blend"})
show("smooth2 + blend qmethod", {**BEST, "step_smooth": 2, "qmethod": "blend"})
show("smooth1 + unk_global=0.15 + unk_mixed=0.35",
     {**BEST, "step_smooth": 1, "unk_global": 0.15, "unk_mixed": 0.35})
