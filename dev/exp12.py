"""Round 18: hard regime separation for the anchored pool."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7}
SAFE = {**LOCKED, "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3,
        "step_tau_offset": -2, "step_smooth": 1,
        "unk_global": 0.15, "unk_mixed": 0.35}
AGGR = {**SAFE, "qmethod": "blend", "blend_w": 0.4, "scale_sigma": 1.0}


def show(tag, P):
    r = score_params(P)
    print(f"{tag:46s} all {r['all']:.4f} | rolling {r['rolling']:.4f} "
          f"| gta {r['gta']:.4f}")
    return r


show("SAFE", SAFE)
show("SAFE + sep_regimes", {**SAFE, "sep_regimes": True})
show("AGGR", AGGR)
show("AGGR + sep_regimes", {**AGGR, "sep_regimes": True})
show("AGGR + sep + offset=-3", {**AGGR, "sep_regimes": True,
                                "step_tau_offset": -3})
