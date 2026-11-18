"""Print the actual votes/weights inside stepper_forecast for ARC + BF6."""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import main_round1 as M
from eval2 import build_cases

for tname, hours in [("ARC Raiders", [12, 16, 20]), ("Battlefield 6", [16, 19]),
                     ("Marathon", [12, 20])]:
    cases = {comp["name"]: case for comp, case, _, _ in build_cases()}
    case = cases[tname]
    target = M.target_features(case)
    feats_list = []
    for c in case.get("comparables") or []:
        f = M.comparable_features(c)
        if f is not None and f["name"] != target["name"]:
            feats_list.append(f)
    tau_t = M.parse_unlock_step_hour(case.get("notes") or "",
                                     case.get("day_start") or "")
    print(f"\n### target {tname}: unlock={target['unlock']} mode={target['mode']} "
          f"has_pc={target['has_pc']} ea={target['ea']} tau_t={tau_t}")
    steppers = []
    for feats in feats_list:
        day = feats["day"]
        plateau = math.log(max(day.values()) / day[1])
        if plateau < M.STEP_THRESH:
            continue
        tau_c = 25
        for h in range(2, 25):
            r = M.log_ratio(day, h)
            if r is not None and r >= 0.5 * plateau:
                tau_c = h
                break
        w = M.factor_similarity(target, feats) ** M.STEP_TEMPER
        steppers.append((feats, w, tau_c))
        print(f"  comp {feats['name']:36s} unl={feats['unlock']:8s} mode={feats['mode']:4s} "
              f"pc={feats['has_pc']} ea={feats['ea']} weak={feats['weak']} "
              f"tau_c={tau_c:2d} peak={max(day.values()):7.0f} hours={len(day)} "
              f"w={w:.3f}")
    for h in hours:
        print(f"  hour {h} votes:")
        for feats, w, tau_c in steppers:
            day = feats["day"]
            shift = (tau_t - tau_c) if tau_t is not None else 0
            j = min(24, max(1, h - shift))
            r = M.log_ratio(day, j)
            if r is None:
                print(f"    {feats['name']:36s} j={j:2d} -> None (dropped)")
                continue
            v = (target["p1"] * math.exp(r)) if j < tau_c else day[1] * math.exp(r)
            print(f"    {feats['name']:36s} j={j:2d} tau_c={tau_c:2d} "
                  f"{'pre ' if j < tau_c else 'post'} vote={v:9.0f} w={w:.3f}")
