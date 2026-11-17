"""Explore the comparables' release-day curves from the practice cases."""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

KIT = Path.home() / "workspace/makefun/gta6-twitch-ccu-forecast-01-kit"


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def release_day(comp):
    """Return {hour: viewers} for hours 1..24 of the comparable's release day."""
    start = parse_ts(comp["day_start"])
    out = {}
    for pt in comp["hourly"]:
        t = parse_ts(pt["from"])
        delta = (t - start).total_seconds()
        if 0 <= delta < 24 * 3600:
            out[int(delta // 3600) + 1] = pt["viewers"]
    return out


def main():
    case = json.loads((KIT / "input/p00.in").read_text())
    print(f"{'name':58s} {'H1':>8s} {'peakH':>5s} {'peak/H1':>7s} {'H12/H1':>6s} {'H24/H1':>6s} {'miss':>4s}")
    for comp in case["comparables"]:
        day = release_day(comp)
        missing = [h for h in range(1, 25) if h not in day or day[h] is None]
        if 1 not in day or not day.get(1):
            print(f"{comp['name'][:58]:58s}  NO HOUR 1   hours present: {len(day)}")
            continue
        h1 = day[1]
        peak_h = max(day, key=lambda h: day[h])
        def ratio(h):
            return day[h] / h1 if day.get(h) else float("nan")
        print(f"{comp['name'][:58]:58s} {h1:8d} {peak_h:5d} {day[peak_h]/h1:7.2f} "
              f"{ratio(12):6.2f} {ratio(24):6.2f} {len(missing):4d}")
    print()
    print("UNLOCK TEXTS:")
    for comp in case["comparables"]:
        print(f"- {comp['name']}: {comp['unlock'][:180]}")


if __name__ == "__main__":
    main()
