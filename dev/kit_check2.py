"""Kit check for the round-2 main.py: run as a script on p00-p03 twice,
validate output shape/monotonicity/range/size, byte-compare runs, time it."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ENTRY = Path(__file__).resolve().parent.parent
KIT = Path.home() / "workspace/makefun/gta6-twitch-ccu-forecast-01-kit"


def run(outdir):
    env = {**os.environ, "MAKEFUN_INPUT_DIR": str(KIT / "input"),
           "MAKEFUN_OUTPUT_DIR": str(outdir)}
    t0 = time.time()
    subprocess.run([sys.executable, str(ENTRY / "main.py")], env=env,
                   check=True)
    return time.time() - t0


def main():
    d1, d2 = Path("/tmp/kit2_a"), Path("/tmp/kit2_b")
    for d in (d1, d2):
        d.mkdir(exist_ok=True)
        for f in d.glob("*.out"):
            f.unlink()
    t1 = run(d1)
    t2 = run(d2)
    ok = True
    for stem in ("p00", "p01", "p02", "p03"):
        a = (d1 / f"{stem}.out").read_bytes()
        b = (d2 / f"{stem}.out").read_bytes()
        if a != b:
            ok = False
            print(f"{stem}: RUNS DIFFER")
        out = json.loads(a)
        hours = out["hours"]
        assert len(hours) == 23, (stem, len(hours))
        for row in hours:
            q = row["q"]
            assert len(q) == 5, (stem, row)
            assert all(0 < v <= 1e9 for v in q), (stem, row)
            assert all(q[i] >= q[i - 1] for i in range(1, 5)), (stem, row)
        print(f"{stem}: valid, {len(a)} bytes, hours "
              f"{hours[0]['hour']}..{hours[-1]['hour']}")
    print(f"two runs byte-identical: {ok}")
    print(f"timing: run1 {t1:.2f}s run2 {t2:.2f}s for 4 cases "
          f"(~{t1 / 4:.2f}s/case, limit 8s)")


if __name__ == "__main__":
    main()
