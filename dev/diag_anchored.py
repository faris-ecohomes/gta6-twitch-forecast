"""Diagnose top anchored unprotected losers under round-1 main.py."""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import main_round1 as M
from validate import load_pool
from eval2 import build_cases

NAMES = ["Halo Infinite", "Borderlands 4", "Saros", "Marvel Rivals",
         "Starfield", "Clair Obscur: Expedition 33", "Forza Horizon 5",
         "Forza Horizon 6", "Elden Ring Nightreign", "Stellar Blade"]


def main():
    pool = {c["name"]: c for c in load_pool()}
    cases = {comp["name"]: case for comp, case, _, _ in build_cases()}
    for name in NAMES:
        comp = pool[name]
        case = cases[name]
        target = M.target_features(case)
        day = comp["day"]
        feats_list = []
        for c in case.get("comparables") or []:
            f = M.comparable_features(c)
            if f is not None and f["name"] != target["name"]:
                feats_list.append(f)
        poolw = []
        for f in feats_list:
            w = M.similarity(target, f)
            if w > 1e-6:
                poolw.append((f, w))
        poolw.sort(key=lambda t: -t[1])
        tw = sum(w for _, w in poolw)
        ess = tw * tw / sum(w * w for _, w in poolw)
        print(f"\n=== {name} === unl={target['unlock']} mode={target['mode']} "
              f"pc={target['has_pc']} ea={target['ea']} H1={target['p1']:.0f} "
              f"pre_max={target['pre_max']} ESS={ess:.1f} npool={len(poolw)}")
        print("  top comps: " + ", ".join(
            f"{f['name']}({w/tw:.2f},unl={f['unlock']},plt={math.log(max(f['day'].values())/f['day'][1]):.2f})"
            for f, w in poolw[:5]))
        # predicted mu path vs actual log-ratio at selected hours
        out = M.forecast_case(case)
        pred = {row["hour"]: row["q"] for row in out["hours"]}
        for h in (4, 8, 12, 16, 20, 24):
            act = M.log_ratio(day, h)
            q50 = pred[h][2]
            mu_hat = math.log(q50 / target["p1"])
            print(f"   h{h:2d} actual_ratio={math.exp(act) if act is not None else float('nan'):7.2f}x "
                  f"pred_q50_ratio={q50/target['p1']:7.2f}x  "
                  f"q05={pred[h][0]/target['p1']:6.2f}x q95={pred[h][4]/target['p1']:6.2f}x")


if __name__ == "__main__":
    main()
