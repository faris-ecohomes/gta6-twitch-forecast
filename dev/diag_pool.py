"""All comparables: plateau ratio, peak, tau_c — pool composition by threshold."""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import main_round1 as M
from validate import load_pool

pool = load_pool()
rows = []
for comp in pool:
    day = comp["day"]
    plateau = math.log(max(day.values()) / day[1])
    tau_c = 25
    for h in range(2, 25):
        r = M.log_ratio(day, h)
        if r is not None and r >= 0.5 * plateau:
            tau_c = h
            break
    rows.append((plateau, comp["name"], comp["unlock"], max(day.values()),
                 day[1], tau_c))
rows.sort(reverse=True)
print(f"{'plateau':>7s} {'ratio':>6s} {'name':38s} {'unlock':8s} {'peak':>7s} {'H1':>7s} {'tau_c':>5s}")
for plateau, name, unlock, peak, h1, tau_c in rows:
    print(f"{plateau:7.3f} {math.exp(plateau):6.1f} {name:38s} {unlock:8s} "
          f"{peak:7.0f} {h1:7.0f} {tau_c:5d}")
