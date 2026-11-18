"""Check: do unlock notes state a time? Does step hour track day_start?"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import load_pool, parse_ts

KIT = Path.home() / "workspace/makefun/gta6-twitch-ccu-forecast-01-kit"
case = json.loads((KIT / "input/p00.in").read_text())
raw = {c["name"]: c for c in case["comparables"]}

pool = load_pool()
for comp in pool:
    day = comp["day"]
    peak = max(day[h] for h in range(1, 25) if day.get(h))
    lr = {h: math.log(day[h] / day[1]) for h in range(1, 25) if day.get(h)}
    plateau = max(lr.values())
    if plateau < 1.386:
        continue
    step_h = min(h for h in range(2, 25) if lr.get(h, -9) >= 0.5 * plateau)
    ds = raw[comp["name"]]["day_start"]
    print(f"{comp['name'][:34]:34s} day_start={ds} step_h={step_h:2d} "
          f"plateau={plateau:.1f}")
    print(f"    unlock: {raw[comp['name']]['unlock'][:220]}")
