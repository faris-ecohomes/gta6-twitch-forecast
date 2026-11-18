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

One regime breaks that logic: launches whose hour-1 print is a pre-unlock
trickle (a few thousand viewers, a small fraction of the audience the game
had already drawn before launch). Their day steps up by orders of magnitude
once the unlock lands, at an hour that varies from game to game, so ratios
to hour 1 say almost nothing. When hour 1 looks like that — at most a few
thousand viewers and at most 60% of the pre-launch peak — the forecast is
built instead from the comparable launches that stepped the same way:
before each one's step it contributes the target's own hour-1 level scaled
by its pre-step ratio, from its step on it contributes its absolute viewer
level (stepper peaks cluster within ~4x of each other while their trickles
span 30x). If the case notes state the unlock instant, every comparable's
step is aligned to it; otherwise step timing stays a population spread.

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
GATE_H1 = 6000.0         # trickle gate: hour-1 viewers at/below this ...
GATE_A = 0.6             # ... and at/below this share of the pre-launch peak
STEP_THRESH = 1.386      # log(peak / hour-1) at/above which a comp "stepped"
STEP_TEMPER = 0.3        # tempering for stepper-pool factor weights
TAU_OFFSET = -2          # step-hour lead vs the stated unlock instant

# --- round-2 experiment knobs (env overrides; defaults = round-1 values) ---
def _envf(name, default):
    v = os.environ.get(name)
    return float(v) if v is not None else default


def _envi(name, default):
    v = os.environ.get(name)
    return int(v) if v is not None else default


STEP_THRESH = _envf("STEP_THRESH", STEP_THRESH)
STEP_TEMPER = _envf("STEP_TEMPER", STEP_TEMPER)
TAU_OFFSET = _envi("TAU_OFFSET", TAU_OFFSET)
GATE_H1 = _envf("GATE_H1", GATE_H1)
GATE_A = _envf("GATE_A", GATE_A)
STEP_PEAK_FLOOR = _envf("STEP_PEAK_FLOOR", 0.0)   # min comp peak in stepper pool
STEP_GAMMA = _envf("STEP_GAMMA", 1.0)             # gated quantile spread around q50
STEP_TAU_FRAC = _envf("STEP_TAU_FRAC", 0.5)       # tau_c plateau fraction
STEP_PEAK_WEXP = _envf("STEP_PEAK_WEXP", 0.0)     # extra pool weight ~ comp peak^k
STEP_PRE_CAP = _envf("STEP_PRE_CAP", 0.0)         # cap on pre-step log-ratio votes
STEP_QMETHOD = _envi("STEP_QMETHOD", 0)           # 0 = interpolated, 1 = inverse-CDF
STEP_SMOOTH = _envf("STEP_SMOOTH", 0.0)           # output log-quantile smoothing
STEP_SMOOTH_PASSES = _envi("STEP_SMOOTH_PASSES", 1)  # smoothing passes
UG_MU_BIAS = _envf("UG_MU_BIAS", 0.0)             # UG centre bias x (h-2)/22
# Anchored-path overrides applied ONLY when target unlock is unknown/global
# (rolling/mixed targets always take the original code path and constants).
UG_PRE_SIGMA = _envf("UG_PRE_SIGMA", -1.0)
UG_SCALE_SIGMA = _envf("UG_SCALE_SIGMA", -1.0)
UG_GAMMA_START = _envf("UG_GAMMA_START", -1.0)
UG_GAMMA_END = _envf("UG_GAMMA_END", -1.0)
UG_UNK_ROLL = _envf("UG_UNK_ROLL", -1.0)
UG_UNK_MIX = _envf("UG_UNK_MIX", -1.0)
UG_UNK_GLOB = _envf("UG_UNK_GLOB", -1.0)
UG_UNK_UNK = _envf("UG_UNK_UNK", -1.0)
UG_LL = _envf("UG_LL", 0.0)          # local-linear (pre_stat) centre blend
UG_LL_CLIP = _envf("UG_LL_CLIP", 0.0)  # max |LL adjustment| in log units
UG_MU_LATE = _envf("UG_MU_LATE", 0.0)  # late-day mu shrink: mu *= 1 - k*(h-2)/22
UG_MU_LATE_POS = _envf("UG_MU_LATE_POS", 0.0)  # if set, shrink only mu > 0


def _ug(target):
    return target["unlock"] in ("unknown", "global")

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
    if target["unlock"] == "unknown":
        row = {"rolling": UG_UNK_ROLL, "mixed": UG_UNK_MIX,
               "global": UG_UNK_GLOB, "unknown": UG_UNK_UNK}
        if row[comp["unlock"]] > 0:
            w = row[comp["unlock"]]
    if comp["ea"] != target["ea"]:
        w *= EA_FACTOR
    if comp["weak"]:
        w *= WEAK_FACTOR
    if comp["has_pc"] != target["has_pc"]:
        w *= PC_DOWN if comp["has_pc"] else PC_UP
    w *= MODE_MATCH[(target["mode"], comp["mode"])]
    scale_sigma = UG_SCALE_SIGMA if (_ug(target) and UG_SCALE_SIGMA > 0) \
        else SCALE_SIGMA
    dl = math.log(comp["day"][1]) - math.log(target["p1"])
    w *= math.exp(-(dl * dl) / (2 * scale_sigma ** 2))
    if comp["pre_stat"] is not None and target["pre_max"]:
        pre_sigma = UG_PRE_SIGMA if (_ug(target) and UG_PRE_SIGMA > 0) \
            else PRE_SIGMA
        dt = comp["pre_stat"] - math.log(target["p1"] / target["pre_max"])
        w *= math.exp(-(dt * dt) / (2 * pre_sigma ** 2))
    return w


def factor_similarity(target, comp):
    """Regime-match part of similarity(): unlock class, early access, weak
    tier, platform and mode — without the audience-scale kernels, which are
    meaningless for a comparable whose hour 1 was a trickle."""
    w = UNLOCK_MATCH[(target["unlock"], comp["unlock"])]
    if comp["ea"] != target["ea"]:
        w *= EA_FACTOR
    if comp["weak"]:
        w *= WEAK_FACTOR
    if comp["has_pc"] != target["has_pc"]:
        w *= PC_DOWN if comp["has_pc"] else PC_UP
    w *= MODE_MATCH[(target["mode"], comp["mode"])]
    return w


def weighted_quantile(xs, ws, tau):
    """Linear-interpolated weighted empirical quantile."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    xs = [xs[i] for i in order]
    ws = [ws[i] for i in order]
    total = sum(ws)
    if total <= 0:
        return xs[len(xs) // 2]
    cum = []
    acc = 0.0
    for w in ws:
        acc += w / total
        cum.append(acc)
    if STEP_QMETHOD == 1:  # inverse-CDF (lower)
        for i in range(len(xs)):
            if tau <= cum[i]:
                return xs[i]
        return xs[-1]
    if tau <= cum[0]:
        return xs[0]
    for i in range(1, len(xs)):
        if tau <= cum[i]:
            frac = (tau - cum[i - 1]) / (cum[i] - cum[i - 1])
            return xs[i - 1] + frac * (xs[i] - xs[i - 1])
    return xs[-1]


_STAMP_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})")


def parse_unlock_step_hour(notes, day_start):
    """Step hour (1..24) if the notes state an ISO unlock time on launch day.

    Research notes sometimes give the exact unlock instant ("single global
    unlock ... = 2024-08-20T02:00Z"). The audience reaches half its plateau
    roughly two hours before that stated instant — countdown and preload
    streams, and hourly buckets labelled by their end — so the step is
    placed TAU_OFFSET hours earlier than the hour containing the instant.
    Returns None when no same-day ISO timestamp is present.
    """
    if not notes or not day_start:
        return None
    try:
        start = parse_ts(day_start)
    except Exception:
        return None
    for m in _STAMP_RE.finditer(notes):
        try:
            stamp = datetime(int(m.group(1)), int(m.group(2)),
                             int(m.group(3)), int(m.group(4)),
                             int(m.group(5)), tzinfo=timezone.utc)
        except ValueError:
            continue
        delta_h = (stamp - start).total_seconds() / 3600.0
        if 0 <= delta_h < 24:
            return min(24, max(1, int(delta_h) + 1 + TAU_OFFSET))
    return None


def stepper_forecast(case, target, feats_list):
    """Forecast for a trickle target, from transplanted stepper curves.

    Returns None when the target's hour 1 is a real launch anchor (the gate
    does not fire) or when no comparable stepped. Each stepper comparable
    (its own day peaked at >= ~4x its hour 1) is reduced to a step hour —
    the first hour its log-ratio reaches half its plateau — and votes at
    target hour h from its own timeline at j = h - (tau_t - tau_c), where
    tau_t is the target's step hour from its stated unlock time (no stated
    time: no shift, step timing stays a population spread). Before its
    step, the vote is the target's hour-1 level scaled by the comparable's
    pre-step ratio; from its step on, it is the comparable's absolute
    level. Quantiles are the weighted empirical quantiles of those votes.
    """
    pre_max = target["pre_max"]
    if not pre_max or target["p1"] > GATE_H1 \
            or target["p1"] / pre_max > GATE_A:
        return None
    tau_t = parse_unlock_step_hour(case.get("notes") or "",
                                   case.get("day_start") or "")
    steppers = []
    for feats in feats_list:
        day = feats["day"]
        plateau = math.log(max(day.values()) / day[1])
        if plateau < STEP_THRESH:
            continue
        if max(day.values()) < STEP_PEAK_FLOOR:
            continue
        tau_c = 25
        for h in range(2, 25):
            r = log_ratio(day, h)
            if r is not None and r >= STEP_TAU_FRAC * plateau:
                tau_c = h
                break
        w = factor_similarity(target, feats) ** STEP_TEMPER
        if STEP_PEAK_WEXP:
            w *= (max(day.values()) / 1e5) ** STEP_PEAK_WEXP
        if w > 1e-9:
            steppers.append((feats, w, tau_c))
    if not steppers:
        return None
    log_p1 = math.log(target["p1"])
    hours = []
    for row in case["forecast"]:
        h = row["hour"]
        xs, ws = [], []
        for feats, w, tau_c in steppers:
            day = feats["day"]
            shift = (tau_t - tau_c) if tau_t is not None else 0
            j = min(24, max(1, h - shift))
            r = log_ratio(day, j)
            if r is None:
                continue
            if j < tau_c:
                if STEP_PRE_CAP > 0:
                    r = min(r, STEP_PRE_CAP)
                xs.append(log_p1 + r)
            else:
                xs.append(math.log(day[1]) + r)
            ws.append(w)
        if not xs:
            hours.append({"hour": h, "q": shape_row(target["p1"], 0.0, 0.5)})
            continue
        row_q = []
        for tau in LEVELS:
            q = weighted_quantile(xs, ws, tau)
            row_q.append(min(max(math.exp(q), 0.01), 1e9))
        for i in range(1, len(row_q)):
            row_q[i] = max(row_q[i], row_q[i - 1])
        if STEP_GAMMA != 1.0:
            med = row_q[2]
            row_q = [min(max(med * (v / med) ** STEP_GAMMA, 0.01), 1e9)
                     for v in row_q]
            for i in range(1, len(row_q)):
                row_q[i] = max(row_q[i], row_q[i - 1])
        hours.append({"hour": h, "q": [round(v, 4) for v in row_q]})
    if STEP_SMOOTH:
        for _pass in range(STEP_SMOOTH_PASSES):
            logs = [[math.log(max(q, 1e-9)) for q in row["q"]] for row in hours]
            for i, row in enumerate(hours):
                vals = []
                for k in range(5):
                    a = logs[i - 1][k] if i > 0 else logs[i][k]
                    b = logs[i][k]
                    c = logs[i + 1][k] if i < len(logs) - 1 else logs[i][k]
                    v = (1.0 - STEP_SMOOTH) * b \
                        + STEP_SMOOTH * (0.25 * a + 0.5 * b + 0.25 * c)
                    vals.append(min(max(math.exp(v), 0.01), 1e9))
                for k in range(1, len(vals)):
                    vals[k] = max(vals[k], vals[k - 1])
                row["q"] = [round(v, 4) for v in vals]
    return {"hours": hours}


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
    feats_list = []
    for comp in case.get("comparables") or []:
        feats = comparable_features(comp)
        if feats is None or feats["name"] == target["name"]:
            continue
        feats_list.append(feats)
    gated = stepper_forecast(case, target, feats_list)
    if gated is not None:
        return gated
    pool = []
    tgt_pre = math.log(target["p1"] / target["pre_max"]) \
        if target["pre_max"] else None
    for feats in feats_list:
        w = similarity(target, feats)
        if w > 1e-6:
            dt = None
            if feats["pre_stat"] is not None and tgt_pre is not None:
                dt = feats["pre_stat"] - tgt_pre
            pool.append((feats, w, dt))
    ug = _ug(target)
    g_start = UG_GAMMA_START if (ug and UG_GAMMA_START > 0) else GAMMA_START
    g_end = UG_GAMMA_END if (ug and UG_GAMMA_END > 0) else GAMMA_END
    hours = []
    for row in case["forecast"]:
        h = row["hour"]
        xs, ws, dts = [], [], []
        for feats, w, dt in pool:
            x = log_ratio(feats["day"], h)
            if x is not None:
                xs.append(x)
                ws.append(w)
                dts.append(dt)
        if xs:
            tw = sum(ws)
            mu = sum(w * x for x, w in zip(xs, ws)) / tw
            var = sum(w * (x - mu) ** 2 for x, w in zip(xs, ws)) / tw
            sd = math.sqrt(max(var, 1e-6))
        else:
            mu, sd = 0.0, 0.5
        if ug and UG_LL and xs:
            s0 = s1 = s2 = t0 = t1 = 0.0
            for x, w, dt in zip(xs, ws, dts):
                if dt is None:
                    continue
                s0 += w
                s1 += w * dt
                s2 += w * dt * dt
                t0 += w * x
                t1 += w * dt * x
            det = s0 * s2 - s1 * s1
            if s0 > 0 and det > 1e-9:
                a = (s2 * t0 - s1 * t1) / det
                adj = UG_LL * (a - mu)
                if UG_LL_CLIP > 0:
                    adj = max(-UG_LL_CLIP, min(UG_LL_CLIP, adj))
                mu = mu + adj
        if ug and UG_MU_LATE:
            if not UG_MU_LATE_POS or mu > 0:
                mu *= 1.0 - UG_MU_LATE * (h - 2) / 22.0
        if ug and UG_MU_BIAS:
            mu += UG_MU_BIAS * (h - 2) / 22.0
        gamma = g_start + (g_end - g_start) * (h - 2) / 22.0
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
