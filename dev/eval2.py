"""Round-2 evaluation: per-case losses + protected-subset byte-identity.

Usage:
  python3 dev/eval2.py [candidate_main.py]
      Per-case table for the candidate (default: main.py) vs round-1 losses,
      plus a byte-identity check of forecast outputs on every protected
      target (rolling/mixed subset and GTA-like subset) between
      dev/main_round1.py and the candidate.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validate import KIT, load_pool, pinball_loss  # noqa: E402
from fidelity import synth_case  # noqa: E402


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_cases():
    raw_case = json.loads((KIT / "input/p00.in").read_text())
    all_raw = raw_case["comparables"]
    raw_by_name = {c["name"]: c for c in all_raw}
    pool = load_pool()
    cases = []
    for comp in pool:
        craw = raw_by_name[comp["name"]]
        day1 = next(pt for pt in craw["hourly"]
                    if pt["from"] == craw["day_start"])
        case = synth_case(craw, all_raw, day1)
        protected = comp["unlock"] in ("rolling", "mixed")
        gta = protected and comp["mode"] == "sp" and not comp["has_pc"]
        cases.append((comp, case, protected, gta))
    return cases


def run(mod, cases):
    rows = []
    for comp, case, protected, gta in cases:
        out = mod.forecast_case(case)
        pred = {row["hour"]: row["q"] for row in out["hours"]}
        loss = pinball_loss(pred, comp["day"])
        # which branch served it?
        tgt = mod.target_features(case)
        feats = []
        for c in case.get("comparables") or []:
            f = mod.comparable_features(c)
            if f is not None and f["name"] != tgt["name"]:
                feats.append(f)
        gated = mod.stepper_forecast(case, tgt, feats) is not None
        rows.append({
            "name": comp["name"], "unlock": comp["unlock"],
            "mode": comp["mode"], "has_pc": comp["has_pc"],
            "protected": protected, "gta": gta, "gated": gated,
            "loss": loss, "out": out,
            "p1": tgt["p1"],
            "pre_ratio": (tgt["p1"] / tgt["pre_max"]) if tgt["pre_max"] else None,
        })
    return rows


def main():
    cand_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "main.py"
    round1 = load_module(HERE / "main_round1.py", "main_round1")
    cand = load_module(cand_path, "candidate")
    cases = build_cases()
    r1 = {r["name"]: r for r in run(round1, cases)}
    rc = run(cand, cases)

    # byte-identity on protected targets
    bad = []
    for row in rc:
        if row["protected"] or row["gta"]:
            a = json.dumps(r1[row["name"]]["out"], sort_keys=True)
            b = json.dumps(row["out"], sort_keys=True)
            if a != b:
                bad.append(row["name"])
    print(f"protected byte-identity: {'OK (all identical)' if not bad else 'VIOLATED: ' + ', '.join(bad)}")

    def agg(rows, key):
        v = [r["loss"] for r in rows if key(r)]
        return sum(v) / len(v), len(v), sum(v)

    for label, key in [("ALL", lambda r: True),
                       ("rolling/mixed", lambda r: r["protected"]),
                       ("GTA-like", lambda r: r["gta"]),
                       ("unprotected", lambda r: not r["protected"])]:
        m, n, s = agg(rc, key)
        print(f"{label:14s} n={n:2d}  mean {m:.4f}  sum {s:.3f}")

    print("\nper-case (sorted by candidate loss desc):")
    print(f"{'name':44s} {'unl':8s} {'gate':4s} {'prot':4s} {'r1':>7s} {'cand':>7s} {'diff':>7s}")
    for row in sorted(rc, key=lambda r: -r["loss"]):
        d = row["loss"] - r1[row["name"]]["loss"]
        print(f"{row['name']:44s} {row['unlock']:8s} "
              f"{'G' if row['gated'] else '.':4s} "
              f"{'P' if row['protected'] else '.':4s} "
              f"{r1[row['name']]['loss']:7.4f} {row['loss']:7.4f} {d:+7.4f}")


if __name__ == "__main__":
    main()
