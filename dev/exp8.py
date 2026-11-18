"""Round 14: trimmed centre; unknown-target unlock-match overrides."""
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
show("trimnormal", {**BEST, "qmethod": "trimnormal"})
for ug in (0.15, 0.45):
    show(f"unk_global={ug}", {**BEST, "unk_global": ug})
for ur in (0.45, 0.75):
    show(f"unk_rolling={ur}", {**BEST, "unk_rolling": ur})
for um in (0.35, 0.65):
    show(f"unk_mixed={um}", {**BEST, "unk_mixed": um})
show("trimnormal + offset=-3", {**BEST, "qmethod": "trimnormal",
                                "step_tau_offset": -3})
