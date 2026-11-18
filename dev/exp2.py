"""Round 8: gated stepper-level path, Cornish-Fisher skew, combos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}


def show(tag, P):
    r = score_params(P)
    print(f"{tag:46s} all {r['all']:.4f} | rolling {r['rolling']:.4f} "
          f"| gta {r['gta']:.4f}")
    return r


show("LOCKED", LOCKED)
for gh, ga in ((6000, 0.6), (4000, 0.6), (10000, 0.6), (6000, 0.5),
               (6000, 0.7), (10000, 0.35), (3000, 0.25)):
    show(f"E7 gate h1<={gh} a<={ga}", {**LOCKED, "gate_h1": gh, "gate_a": ga})
show("E7b gate + level_gamma=0.9", {**LOCKED, "gate_h1": 6000, "gate_a": 0.6,
                                    "step_level_gamma": 0.9})
show("E7c gate + level_temper=0.3", {**LOCKED, "gate_h1": 6000, "gate_a": 0.6,
                                     "step_level_temper": 0.3})
show("E7d gate + level_temper=0.8", {**LOCKED, "gate_h1": 6000, "gate_a": 0.6,
                                     "step_level_temper": 0.8})
show("E9a gamma_late=1.0", {**LOCKED, "gamma_late": 1.0})
show("E9b gamma=0.95 gamma_late=0.85", {**LOCKED, "gamma": 0.95,
                                        "gamma_late": 0.85})
show("E10 qmethod=cf", {**LOCKED, "qmethod": "cf"})
show("E10b cf + gamma_late=0.85", {**LOCKED, "qmethod": "cf",
                                   "gamma_late": 0.85})
show("E8 gate + temper=0.5", {**LOCKED, "gate_h1": 6000, "gate_a": 0.6,
                              "temper": 0.5})
show("E8b gate + cf", {**LOCKED, "gate_h1": 6000, "gate_a": 0.6,
                       "qmethod": "cf"})
