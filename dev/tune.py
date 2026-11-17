"""Grid-search model knobs on the pseudo-LOO harness."""
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, score_params


def show(tag, P):
    r = score_params(P)
    print(f"{tag:55s} all {r['all']:.4f} | rolling {r['rolling']:.4f} "
          f"(base {r['rolling_base']:.4f}) | gta-like {r['gta']:.4f} (base {r['gta_base']:.4f}, n={r['gta_n']})")
    return r


def main():
    base = dict(DEFAULT_PARAMS)
    show("v1 defaults", base)
    print("\n-- gamma --")
    for g in (0.85, 0.95, 1.0, 1.1, 1.2, 1.35):
        show(f"gamma={g}", {**base, "gamma": g})
    print("\n-- scale_sigma --")
    for s in (0.6, 0.8, 1.1, 1.5, 2.2, 99.0):
        show(f"scale_sigma={s}", {**base, "scale_sigma": s})
    print("\n-- qmethod / smoothing --")
    show("qmethod=normal", {**base, "qmethod": "normal"})
    show("smooth_med=1", {**base, "smooth_med": 1})
    show("smooth_med=2", {**base, "smooth_med": 2})
    print("\n-- rolling-target pool weights --")
    for rg in (0.0, 0.05, 0.25):
        show(f"roll_global={rg}", {**base, "roll_global": rg})
    for ru in (0.25, 0.65, 0.9):
        show(f"roll_unknown={ru}", {**base, "roll_unknown": ru})
    for rm in (0.4, 0.85, 1.0):
        show(f"roll_mixed={rm}", {**base, "roll_mixed": rm})
    print("\n-- ea / mode factors --")
    for ea in (0.15, 0.5, 0.7):
        show(f"ea_factor={ea}", {**base, "ea_factor": ea})
    for mp in (0.15, 0.55, 0.8):
        show(f"mode_mp={mp}", {**base, "mode_mp": mp})
    for pc in (0.35, 0.8):
        show(f"pc_mismatch_down={pc}", {**base, "pc_mismatch_down": pc})


if __name__ == "__main__":
    main()
