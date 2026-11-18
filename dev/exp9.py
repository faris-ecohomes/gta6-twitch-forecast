"""Round 15: micro-combinations on the current base."""
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
show("qmethod=normalm", {**BEST, "qmethod": "normalm"})
show("qmethod=blend", {**BEST, "qmethod": "blend"})
show("qmethod=robust", {**BEST, "qmethod": "robust"})
show("scale=1.0", {**BEST, "scale_sigma": 1.0})
show("scale=1.0 + pre=0.9", {**BEST, "scale_sigma": 1.0, "pre_sigma": 0.9})
show("pre=0.9", {**BEST, "pre_sigma": 0.9})
show("gamma 0.82/0.68", {**BEST, "gamma": 0.82, "gamma_late": 0.68})
show("gamma 0.88/0.72", {**BEST, "gamma": 0.88, "gamma_late": 0.72})
show("gamma 0.85/0.75", {**BEST, "gamma_late": 0.75})
show("gamma 0.9/0.7", {**BEST, "gamma": 0.9})
show("scale=1.0 + gamma 0.88/0.72", {**BEST, "scale_sigma": 1.0,
                                     "gamma": 0.88, "gamma_late": 0.72})
show("unk_global=0.15 + unk_mixed=0.35", {**BEST, "unk_global": 0.15,
                                          "unk_mixed": 0.35})
show("offset=-3 + unk_global=0.15", {**BEST, "step_tau_offset": -3,
                                     "unk_global": 0.15})
