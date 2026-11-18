"""Round 10: gated-pool threshold sweep + anchored coordinate sweep."""
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


show("BEST (gate, thresh=ln4)", BEST)
for gt in (1.8, 2.2, 2.6, 3.0, 3.4):
    show(f"gate_thresh={gt}", {**BEST, "gate_thresh": gt})
print()
for tag, over in (
        ("scale_sigma=0.8", {"scale_sigma": 0.8}),
        ("scale_sigma=1.0", {"scale_sigma": 1.0}),
        ("pre_sigma=0.9", {"pre_sigma": 0.9}),
        ("pre_sigma=1.6", {"pre_sigma": 1.6}),
        ("ea_factor=0.15", {"ea_factor": 0.15}),
        ("ea_factor=0.3", {"ea_factor": 0.3}),
        ("gamma=0.8/0.65", {"gamma": 0.8, "gamma_late": 0.65}),
        ("gamma=0.9/0.75", {"gamma": 0.9, "gamma_late": 0.75}),
        ("weak_factor=0.3", {"weak_factor": 0.3}),
        ("weak_factor=0.55", {"weak_factor": 0.55}),
        ("pc_down=0.45", {"pc_mismatch_down": 0.45}),
        ("pc_down=0.65", {"pc_mismatch_down": 0.65}),
        ("mode_coop=0.5", {"mode_coop": 0.5}),
        ("mode_coop=0.7", {"mode_coop": 0.7}),
        ("smooth_med=1", {"smooth_med": 1}),
        ("smooth_comp=1", {"smooth_comp": 1}),
        ("vpc_sigma=0.5", {"vpc_sigma": 0.5}),
        ("vpc_sigma=0.75", {"vpc_sigma": 0.75}),
        ("recency_tau=6", {"recency_tau": 6}),
        ("recency_tau=10", {"recency_tau": 10}),
        ("roll_mixed=0.75", {"roll_mixed": 0.75}),
        ("roll_mixed=0.45", {"roll_mixed": 0.45}),
        ("min_hours=12", {"min_hours": 12}),
        ("min_hours=21", {"min_hours": 21}),
):
    show(tag, {**BEST, **over})
