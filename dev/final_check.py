import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import DEFAULT_PARAMS, run_loo, score_params

LOCKED = {**DEFAULT_PARAMS, "qmethod": "normal", "ea_factor": 0.2,
          "roll_unknown": 0.9, "mode_mp": 0.15, "scale_sigma": 0.9,
          "gamma": 0.85, "pre_sigma": 1.2, "gamma_late": 0.7,
          "gate_h1": 6000, "gate_a": 0.6, "step_level_temper": 0.3,
          "step_tau_offset": -2}
rows = run_loo(LOCKED, verbose=True)
r = score_params(LOCKED)
print("\nLOCKED CONFIG SUMMARY")
print(f"all      n={r['all_n']:2d}  model {r['all']:.4f}  baseline {r['all_base']:.4f}")
print(f"rolling  n={r['rolling_n']:2d}  model {r['rolling']:.4f}  baseline {r['rolling_base']:.4f}")
print(f"gta-like n={r['gta_n']:2d}  model {r['gta']:.4f}  baseline {r['gta_base']:.4f}")
