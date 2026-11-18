"""Oracle decomposition for gated cases: how much loss is step timing,
how much is plateau level, how much is irreducible shape?

Variants of the round-1 stepper branch per gated target:
  base        : round-1 as-is
  oracle_tau  : tau_t forced to the target's actual half-plateau hour
  oracle_lvl  : base + post-step votes rescaled so the pool's weighted
                median peak equals the target's actual peak
  oracle_both : both
"""
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import main_round1 as M
from validate import KIT, load_pool, pinball_loss
from eval2 import build_cases

GATED = ["Marathon", "ARC Raiders", "HELLDIVERS 2",
         "Kingdom Come: Deliverance II", "Baldur's Gate 3",
         "Hollow Knight: Silksong", "Battlefield 6", "Black Myth: Wukong"]


def stepper_variant(case, target, feats_list, tau_override=None,
                    level_target=None):
    pre_max = target["pre_max"]
    if not pre_max or target["p1"] > M.GATE_H1 or target["p1"] / pre_max > M.GATE_A:
        return None
    tau_t = tau_override
    if tau_t is None:
        tau_t = M.parse_unlock_step_hour(case.get("notes") or "",
                                         case.get("day_start") or "")
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
        if w > 1e-9:
            steppers.append((feats, w, tau_c))
    if not steppers:
        return None
    # optional level rescale factor: pool weighted-median peak -> level_target
    scale = 1.0
    if level_target is not None:
        peaks = [max(f["day"].values()) for f, _, _ in steppers]
        ws = [w for _, w, _ in steppers]
        med = M.weighted_quantile([math.log(p) for p in peaks], ws, 0.5)
        scale = level_target / math.exp(med)
    log_p1 = math.log(target["p1"])
    hours = []
    for row in case["forecast"]:
        h = row["hour"]
        xs, ws = [], []
        for feats, w, tau_c in steppers:
            day = feats["day"]
            shift = (tau_t - tau_c) if tau_t is not None else 0
            j = min(24, max(1, h - shift))
            r = M.log_ratio(day, j)
            if r is None:
                continue
            if j < tau_c:
                xs.append(log_p1 + r)
            else:
                xs.append(math.log(day[1]) + r + math.log(scale))
            ws.append(w)
        if not xs:
            hours.append({"hour": h, "q": M.shape_row(target["p1"], 0.0, 0.5)})
            continue
        row_q = []
        for tau in M.LEVELS:
            q = M.weighted_quantile(xs, ws, tau)
            row_q.append(min(max(math.exp(q), 0.01), 1e9))
        for i in range(1, len(row_q)):
            row_q[i] = max(row_q[i], row_q[i - 1])
        hours.append({"hour": h, "q": [round(v, 4) for v in row_q]})
    return {"hours": hours}


def main():
    pool = {c["name"]: c for c in load_pool()}
    cases = {comp["name"]: (comp, case) for comp, case, _, _ in build_cases()}
    tots = {"base": 0.0, "oracle_tau": 0.0, "oracle_lvl": 0.0, "oracle_both": 0.0}
    for name in GATED:
        comp, case = cases[name]
        target = M.target_features(case)
        feats_list = []
        for c in case.get("comparables") or []:
            f = M.comparable_features(c)
            if f is not None and f["name"] != target["name"]:
                feats_list.append(f)
        day = comp["day"]
        plateau = math.log(max(day.values()) / day[1])
        tau_act = next((h for h in range(2, 25)
                        if M.log_ratio(day, h) is not None
                        and M.log_ratio(day, h) >= 0.5 * plateau), None)
        peak = max(day.values())
        outs = {
            "base": stepper_variant(case, target, feats_list),
            "oracle_tau": stepper_variant(case, target, feats_list,
                                          tau_override=tau_act),
            "oracle_lvl": stepper_variant(case, target, feats_list,
                                          level_target=peak),
            "oracle_both": stepper_variant(case, target, feats_list,
                                           tau_override=tau_act,
                                           level_target=peak),
        }
        line = f"{name:38s} tau_act={tau_act:2d} peak={peak:7.0f} | "
        for k, out in outs.items():
            pred = {row["hour"]: row["q"] for row in out["hours"]}
            loss = pinball_loss(pred, day)
            tots[k] += loss
            line += f"{k} {loss:.3f}  "
        print(line)
    print(f"\n{'TOTAL (8 gated)':38s} " + "  ".join(f"{k} {v:.3f}" for k, v in tots.items()))


if __name__ == "__main__":
    main()
