"""Fast round-2 experiment runner.

Caches round-1 per-case outputs/losses in dev/r1_cache.json once, then each
invocation runs ONE candidate module end-to-end (fidelity-style) and reports
ALL / rolling / GTA means, the protected byte-identity verdict, and the
biggest per-case deltas vs round 1.

Usage: python3 dev/runner.py [candidate.py]   (default: main.py)
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validate import load_pool, pinball_loss  # noqa: E402
from eval2 import build_cases, load_module  # noqa: E402

CACHE = HERE / "r1_cache.json"


def run_mod(mod, cases):
    rows = {}
    for comp, case, protected, gta in cases:
        out = mod.forecast_case(case)
        pred = {row["hour"]: row["q"] for row in out["hours"]}
        rows[comp["name"]] = {
            "loss": pinball_loss(pred, comp["day"]),
            "unlock": comp["unlock"], "protected": protected, "gta": gta,
            "out": json.dumps(out, sort_keys=True),
        }
    return rows


def main():
    cand_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "main.py"
    cases = build_cases()
    if CACHE.exists():
        r1 = json.loads(CACHE.read_text())
    else:
        r1 = run_mod(load_module(HERE / "main_round1.py", "main_round1"), cases)
        CACHE.write_text(json.dumps(r1))
    rc = run_mod(load_module(cand_path, "candidate"), cases)

    def agg(rows, key):
        v = [r["loss"] for r in rows.values() if key(r)]
        return sum(v) / len(v), sum(v)

    bad = [n for n, r in rc.items()
           if (r["protected"] or r["gta"]) and r["out"] != r1[n]["out"]]
    mall, sall = agg(rc, lambda r: True)
    mroll, _ = agg(rc, lambda r: r["protected"])
    mgta, _ = agg(rc, lambda r: r["gta"])
    print(f"ALL {mall:.4f} (sum {sall:.3f}) | rolling {mroll:.4f} | gta {mgta:.4f} | "
          f"protected bytes: {'OK' if not bad else 'VIOLATED ' + str(bad)}")
    deltas = sorted(((rc[n]["loss"] - r1[n]["loss"], n) for n in rc),
                    key=lambda t: t[0])
    print("best deltas:", ", ".join(f"{n} {d:+.3f}" for d, n in deltas[:5]))
    print("worst deltas:", ", ".join(f"{n} {d:+.3f}" for d, n in deltas[-3:] if d > 0.0005))


if __name__ == "__main__":
    main()
