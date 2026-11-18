"""Round 9: transplant + unlock-time shift in the gated path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}
GATE = {**LOCKED, "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3}


def show(tag, P):
    r = score_params(P)
    print(f"{tag:46s} all {r['all']:.4f} | rolling {r['rolling']:.4f} "
          f"| gta {r['gta']:.4f}")
    return r


show("gate only (levels, no transplant/shift is old)", GATE)
show("gate + shift OFF (transplant only)", {**GATE, "step_shift": False})
for lt in (0.2, 0.5, 0.7):
    show(f"gate + shift, level_temper={lt}", {**GATE, "step_level_temper": lt})
for lg in (0.9, 1.1):
    show(f"gate + shift, level_gamma={lg}", {**GATE, "step_level_gamma": lg})
