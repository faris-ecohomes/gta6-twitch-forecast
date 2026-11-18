"""Round 11: shift cap / tau offset / shifted-unshifted blend."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}
BEST = {**LOCKED, "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3}


def show(tag, P):
    r = score_params(P)
    print(f"{tag:46s} all {r['all']:.4f} | rolling {r['rolling']:.4f} "
          f"| gta {r['gta']:.4f}")
    return r


show("BEST (full shift)", BEST)
for cap in (3, 4, 6):
    show(f"shift_cap={cap}", {**BEST, "step_shift_cap": cap})
for off in (-1, -2):
    show(f"tau_offset={off}", {**BEST, "step_tau_offset": off})
for b in (0.5, 0.7):
    show(f"blend shifted={b}", {**BEST, "step_blend": b})
show("cap4 + blend 0.5", {**BEST, "step_shift_cap": 4, "step_blend": 0.5})
show("cap6 + offset -1", {**BEST, "step_shift_cap": 6, "step_tau_offset": -1})
