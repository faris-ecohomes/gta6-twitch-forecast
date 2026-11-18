"""Hunt for observables (known at forecast time) that predict a stepper's
step hour and plateau peak: pre-launch hour-of-day profile, pre-peak timing,
channel counts."""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import main_round1 as M
from validate import KIT, load_pool
from eval2 import build_cases

GATED = ["Marathon", "ARC Raiders", "HELLDIVERS 2",
         "Kingdom Come: Deliverance II", "Baldur's Gate 3",
         "Hollow Knight: Silksong", "Battlefield 6", "Black Myth: Wukong"]


def main():
    raw_case = json.loads((KIT / "input/p00.in").read_text())
    raw_by_name = {c["name"]: c for c in raw_case["comparables"]}
    pool = {c["name"]: c for c in load_pool()}
    cases = {comp["name"]: case for comp, case, _, _ in build_cases()}

    print(f"{'name':36s} {'tau':>3s} {'peak':>7s} {'preHOD':>6s} {'prePkHOD':>8s} "
          f"{'gapH':>5s} {'ch1':>6s} {'preChMx':>7s} {'vpc1':>6s} {'nPre':>4s}")
    for name in GATED:
        craw = raw_by_name[name]
        comp = pool[name]
        case = cases[name]
        day = comp["day"]
        plateau = math.log(max(day.values()) / day[1])
        tau_act = next((h for h in range(2, 25)
                        if M.log_ratio(day, h) is not None
                        and M.log_ratio(day, h) >= 0.5 * plateau), None)
        start = M.parse_ts(craw["day_start"])
        pre = []
        for pt in craw["hourly"]:
            t = M.parse_ts(pt["from"])
            if t < start and pt.get("viewers"):
                pre.append((t, float(pt["viewers"]),
                            float(pt.get("channels") or 0)))
        # viewer-weighted circular mean hour-of-day over last 7 pre days
        recent = [p for p in pre if (start - p[0]).total_seconds() <= 7 * 86400]
        use = recent if len(recent) >= 12 else pre
        sx = sum(v * math.cos(2 * math.pi * t.hour / 24) for t, v, _ in use)
        sy = sum(v * math.sin(2 * math.pi * t.hour / 24) for t, v, _ in use)
        hod = (math.atan2(sy, sx) * 24 / (2 * math.pi)) % 24 if use else float("nan")
        pre_peak_t, pre_peak_v, _ = max(pre, key=lambda p: p[1]) if pre else (None, 0, 0)
        pk_hod = pre_peak_t.hour if pre_peak_t else -1
        gap_h = (start - pre_peak_t).total_seconds() / 3600 if pre_peak_t else -1
        known = case["known"][0]
        ch1 = known.get("channels") or 0
        pre_ch_max = max((c for _, _, c in pre), default=0)
        vpc1 = (known["viewers"] / ch1) if ch1 else 0
        print(f"{name:36s} {tau_act:3d} {max(day.values()):7.0f} {hod:6.1f} "
              f"{pk_hod:8d} {gap_h:5.0f} {ch1:6.0f} {pre_ch_max:7.0f} "
              f"{vpc1:6.1f} {len(pre):4d}")


if __name__ == "__main__":
    main()
