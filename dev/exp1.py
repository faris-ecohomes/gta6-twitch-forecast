"""Round 7 experiments: quantile method, tempering, blending, regime mixture."""
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


show("LOCKED (current main.py)", LOCKED)
show("E1 empirical quantiles", {**LOCKED, "qmethod": "empirical"})
show("E2 temper=0.5 normal", {**LOCKED, "temper": 0.5})
show("E3 temper=0.5 empirical", {**LOCKED, "temper": 0.5,
                                "qmethod": "empirical"})
show("E3b temper=0.7 empirical", {**LOCKED, "temper": 0.7,
                                 "qmethod": "empirical"})
show("E4 uniform_blend=0.2 empirical", {**LOCKED, "uniform_blend": 0.2,
                                        "qmethod": "empirical"})
show("E4b uniform_blend=0.3 normal", {**LOCKED, "uniform_blend": 0.3})
show("E5 regime default", {**LOCKED, "regime": True})
show("E5b regime pi_sigma=0.6", {**LOCKED, "regime": True, "pi_sigma": 0.6})
show("E5c regime pi_sigma=1.1", {**LOCKED, "regime": True, "pi_sigma": 1.1})
show("E5d regime step_temper=0.3", {**LOCKED, "regime": True,
                                    "step_temper": 0.3})
show("E5e regime step_temper=0.8", {**LOCKED, "regime": True,
                                    "step_temper": 0.8})
show("E5f regime step_scale_sigma=1.0", {**LOCKED, "regime": True,
                                         "step_scale_sigma": 1.0})
show("E5g regime step_scale_sigma=2.5", {**LOCKED, "regime": True,
                                         "step_scale_sigma": 2.5})
show("E5h regime step_gamma=0.85", {**LOCKED, "regime": True,
                                    "step_gamma": 0.85})
show("E5i regime step_thresh=ln3", {**LOCKED, "regime": True,
                                    "step_thresh": 1.099})
show("E5j regime step_thresh=ln6", {**LOCKED, "regime": True,
                                    "step_thresh": 1.792})
