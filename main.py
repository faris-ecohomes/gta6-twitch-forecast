"""Forecast GTA VI's launch-day Twitch viewers, hour by hour (make.fun entry).

Approach: a launch day's hourly viewer curve, divided by its own hour-1
count, has a shape that repeats across big game launches. This program reads
the comparable launches bundled in the case file, keeps the ones whose
launch resembled the target's (same unlock pattern, similar platform mix,
similar audience scale, similar pre-launch profile), and summarises their
per-hour log-ratios to hour 1 as a weighted normal distribution. The five
scored quantiles of each future hour are that distribution's quantiles,
scaled back by the target's hour-1 print, with the spread slightly shrunk
(a factor that eases from 0.85 early in the day to 0.70 by hour 24) because
the pooled spread overstates how much one specific launch wanders.

Everything is standard library, deterministic, and defensive: any case that
cannot be modelled still gets a valid, flat, wide forecast rather than an
invalid file.
"""

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard-normal quantiles at LEVELS.
ZTAU = [-1.6448536269514722, -0.6744897501960817, 0.0,
        0.6744897501960817, 1.6448536269514722]

# --- tuned constants (chosen by leave-one-out over the practice pool) ---
SCALE_SIGMA = 0.9        # kernel width for log hour-1 audience proximity
PRE_SIGMA = 1.2          # kernel width for log(hour-1 / pre-launch peak)
EA_FACTOR = 0.2          # weight kept when early-access status differs
WEAK_FACTOR = 0.4        # weight kept for comparables the notes call weak
PC_DOWN = 0.55           # console-only target, comparable also on PC
PC_UP = 0.7              # PC target, comparable console-only
GAMMA_START = 0.85       # spread multiplier at hour 2
GAMMA_END = 0.70         # spread multiplier at hour 24
MIN_DAY_HOURS = 18       # comparable must cover this much of its launch day

UNLOCK_MATCH = {
    ("rolling", "rolling"): 1.0, ("rolling", "mixed"): 0.6,
    ("rolling", "unknown"): 0.9, ("rolling", "global"): 0.12,
    ("mixed", "mixed"): 1.0, ("mixed", "rolling"): 0.7,
    ("mixed", "unknown"): 0.45, ("mixed", "global"): 0.3,
    ("global", "global"): 1.0, ("global", "mixed"): 0.3,
    ("global", "rolling"): 0.12, ("global", "unknown"): 0.3,
    ("unknown", "rolling"): 0.6, ("unknown", "mixed"): 0.5,
    ("unknown", "global"): 0.3, ("unknown", "unknown"): 0.5,
}
MODE_MATCH = {
    ("sp", "sp"): 1.0, ("sp", "coop"): 0.6, ("sp", "mp"): 0.15,
    ("coop", "sp"): 0.7, ("coop", "coop"): 1.0, ("coop", "mp"): 0.5,
    ("mp", "sp"): 0.4, ("mp", "coop"): 0.6, ("mp", "mp"): 1.0,
}
# Audience mode by game name: single-player story, co-op, or multiplayer
# live. Names come from the case data; unlisted games default to "sp".
MODE = {
    "ELDEN RING": "sp", "Resident Evil Requiem": "sp", "Hogwarts Legacy": "sp",
    "Cyberpunk 2077": "sp", "Ghost of Yōtei": "sp", "Monster Hunter Wilds": "coop",
    "Black Myth: Wukong": "sp", "Hollow Knight: Silksong": "sp",
    "Battlefield 6": "mp", "Call of Duty: Black Ops 6": "mp",
    "Call of Duty: Modern Warfare III": "mp", "Call of Duty: Black Ops 7": "mp",
    "Call of Duty: Modern Warfare 4": "mp", "007 First Light": "sp",
    "Forza Horizon 6": "mp", "Marathon": "mp", "Saros": "sp",
    "The Legend of Zelda: Tears of the Kingdom": "sp", "Starfield": "sp",
    "Baldur's Gate 3": "sp", "Diablo IV": "coop", "Borderlands 4": "coop",
    "Kingdom Come: Deliverance II": "sp", "Assassin's Creed Shadows": "sp",
    "DOOM: The Dark Ages": "sp", "Elden Ring Nightreign": "coop",
    "Clair Obscur: Expedition 33": "sp", "Death Stranding 2: On the Beach": "sp",
    "FINAL FANTASY VII REBIRTH": "sp", "The Last of Us Part II": "sp",
    "Ghost of Tsushima": "sp", "Halo Infinite": "mp", "Forza Horizon 5": "mp",
    "Stellar Blade": "sp", "ARC Raiders": "mp", "Marvel Rivals": "mp",
    "HELLDIVERS 2": "coop",
    "Marvel's Wolverine": "sp", "Red Dead Redemption 2": "sp",
    "God of War Ragnarök": "sp", "Marvel's Spider-Man 2": "sp",
    "Grand Theft Auto VI": "sp",
}


def parse_ts(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def classify_unlock(text):
    """(unlock class, early-access flag, weak flag) from research-note text."""
    t = " " + (text or "").lower() + " "
    ea = False
    if "early-access-contaminated" in t or "early access contaminated" in t:
        ea = True
    elif "no early access" not in t and "without early access" not in t:
        if "early access" in t or "early-access" in t:
            ea = True
    weak = "tier: weak" in t
    rolling = ("midnight local" in t) or ("rolling" in t) or ("12 am local" in t) \
        or ("midnight in" in t) or ("local time" in t and "midnight" in t)
    glob = ("simultaneous" in t) or ("single global" in t) or ("global unlock" in t) \
        or ("one global" in t) or ("single time" in t)
    if rolling and glob:
        cls = "mixed"
    elif rolling:
        cls = "rolling"
    elif glob:
        cls = "global"
    else:
        cls = "unknown"
    return cls, ea, weak


def target_features(case):
    """Everything the model needs to know about the game being forecast."""
    notes = case.get("notes") or ""
    unlock, ea, _weak = classify_unlock(notes)
    release_note = notes.split("real unlock")[0].lower()
    if "console only" in release_note:
        has_pc = False
    else:
        has_pc = re.search(r"\bpc\b", release_note) is not None
    first = None
    for row in case.get("known") or []:
        if row.get("hour") == 1:
            first = row
            break
    p1 = 1.0
    if first and first.get("viewers"):
        p1 = max(1.0, float(first["viewers"]))
    day_start = case.get("day_start") or ""
    pre_max = None
    for key in ("history_hourly", "history"):
        pts = case.get(key) or []
        vals = []
        for pt in pts:
            when = pt.get("from") or pt.get("at") or ""
            if when and day_start and when >= day_start:
                continue
            if pt.get("viewers"):
                vals.append(float(pt["viewers"]))
        if vals:
            pre_max = max(vals)
            break
    return {
        "name": (case.get("game") or {}).get("name", ""),
        "unlock": unlock, "ea": ea, "has_pc": has_pc,
        "mode": MODE.get((case.get("game") or {}).get("name", ""), "sp"),
        "p1": p1, "pre_max": pre_max,
    }


def comparable_features(comp):
    """A comparable launch reduced to its release-day curve and traits."""
    try:
        start = parse_ts(comp["day_start"])
    except Exception:
        return None
    day = {}
    for pt in comp.get("hourly") or []:
        try:
            delta = (parse_ts(pt["from"]) - start).total_seconds()
        except Exception:
            continue
        if 0 <= delta < 24 * 3600 and pt.get("viewers"):
            day[int(delta // 3600) + 1] = float(pt["viewers"])
    if not day.get(1) or len(day) < MIN_DAY_HOURS:
        return None
    unlock, ea, weak = classify_unlock(comp.get("unlock"))
    pre_vals = []
    for pt in comp.get("hourly") or []:
        try:
            if parse_ts(pt["from"]) < start and pt.get("viewers"):
                pre_vals.append(float(pt["viewers"]))
        except Exception:
            continue
    return {
        "name": comp.get("name", ""), "day": day,
        "unlock": unlock, "ea": ea, "weak": weak,
        "has_pc": "PC" in (comp.get("platforms") or ""),
        "mode": MODE.get(comp.get("name", ""), "sp"),
        "pre_stat": math.log(day[1] / max(pre_vals)) if pre_vals else None,
    }


def similarity(target, comp):
    """How much one comparable's launch should speak for the target's."""
    w = UNLOCK_MATCH[(target["unlock"], comp["unlock"])]
    if comp["ea"] != target["ea"]:
        w *= EA_FACTOR
    if comp["weak"]:
        w *= WEAK_FACTOR
    if comp["has_pc"] != target["has_pc"]:
        w *= PC_DOWN if comp["has_pc"] else PC_UP
    w *= MODE_MATCH[(target["mode"], comp["mode"])]
    dl = math.log(comp["day"][1]) - math.log(target["p1"])
    w *= math.exp(-(dl * dl) / (2 * SCALE_SIGMA ** 2))
    if comp["pre_stat"] is not None and target["pre_max"]:
        dt = comp["pre_stat"] - math.log(target["p1"] / target["pre_max"])
        w *= math.exp(-(dt * dt) / (2 * PRE_SIGMA ** 2))
    return w


def log_ratio(day, h):
    """log(viewers at hour h / viewers at hour 1), interpolated if h is missing."""
    base = math.log(day[1])
    if day.get(h):
        return math.log(day[h]) - base
    lo = max([k for k in day if k < h], default=None)
    hi = min([k for k in day if k > h], default=None)
    if lo is None or hi is None:
        return None
    a, b = math.log(day[lo]) - base, math.log(day[hi]) - base
    return a + (b - a) * (h - lo) / (hi - lo)


def model_forecast(case):
    target = target_features(case)
    p1 = target["p1"]
    pool = []
    for comp in case.get("comparables") or []:
        feats = comparable_features(comp)
        if feats is None or feats["name"] == target["name"]:
            continue
        w = similarity(target, feats)
        if w > 1e-6:
            pool.append((feats, w))
    hours = []
    for row in case["forecast"]:
        h = row["hour"]
        xs, ws = [], []
        for feats, w in pool:
            x = log_ratio(feats["day"], h)
            if x is not None:
                xs.append(x)
                ws.append(w)
        if xs:
            tw = sum(ws)
            mu = sum(w * x for x, w in zip(xs, ws)) / tw
            var = sum(w * (x - mu) ** 2 for x, w in zip(xs, ws)) / tw
            sd = math.sqrt(max(var, 1e-6))
        else:
            mu, sd = 0.0, 0.5
        gamma = GAMMA_START + (GAMMA_END - GAMMA_START) * (h - 2) / 22.0
        hours.append({"hour": h, "q": shape_row(p1, mu, gamma * sd)})
    return {"hours": hours}


def shape_row(p1, mu, sd):
    """Five quantiles around a log-space centre, clamped and non-decreasing."""
    row = []
    for z in ZTAU:
        q = p1 * math.exp(mu + z * sd)
        row.append(min(max(q, 0.01), 1e9))
    for i in range(1, len(row)):
        row[i] = max(row[i], row[i - 1])
    return [round(q, 4) for q in row]


def fallback_forecast(case):
    """A valid forecast from the hour-1 print alone, if modelling fails."""
    p1 = 1.0
    for row in case.get("known") or []:
        if row.get("hour") == 1 and row.get("viewers"):
            p1 = max(1.0, float(row["viewers"]))
            break
    hours = []
    for row in case.get("forecast") or []:
        hours.append({"hour": row["hour"], "q": shape_row(p1, 0.0, 0.5)})
    if not hours:  # last resort: the standard 23 hours
        hours = [{"hour": h, "q": shape_row(p1, 0.0, 0.5)} for h in range(2, 25)]
    return {"hours": hours}


def forecast_case(case):
    try:
        out = model_forecast(case)
        if len(out["hours"]) != len(case.get("forecast") or []) or not out["hours"]:
            raise ValueError("incomplete forecast")
        return out
    except Exception:
        return fallback_forecast(case)


def main():
    in_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(in_dir.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        text = json.dumps(result, separators=(",", ":")) + "\n"
        (out_dir / (path.stem + ".out")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
