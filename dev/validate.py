"""Leave-one-out validation over the kit's comparables.

Each comparable with a usable release day takes a turn as the pseudo-target:
anchor on its release-day hour-1 viewers, predict hours 2..24 quantiles from
the OTHER comparables, and score with the contest's exact pinball-log loss.
The house baseline (starter formula) goes through the same harness.
"""
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

KIT = Path.home() / "workspace/makefun/gta6-twitch-ccu-forecast-01-kit"
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Single-player / co-op / multiplayer-live classification by game name.
# (Names are data in the case file; the final pool reuses these names plus
# the four practice launches, all single-player.)
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


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def release_day(comp):
    start = parse_ts(comp["day_start"])
    out = {}
    for pt in comp["hourly"]:
        delta = (parse_ts(pt["from"]) - start).total_seconds()
        if 0 <= delta < 24 * 3600:
            out[int(delta // 3600) + 1] = pt
    return out


def classify_unlock(text):
    """(unlock_class, early_access, weak_tier) from free-text research notes."""
    t = " " + text.lower() + " "
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


def features(comp):
    day = release_day(comp)
    cls, ea, weak = classify_unlock(comp["unlock"])
    plats = comp["platforms"]
    start = parse_ts(comp["day_start"])
    pre = [pt["viewers"] for pt in comp["hourly"]
           if parse_ts(pt["from"]) < start and pt["viewers"]]
    pre_max = max(pre) if pre else 1
    return {
        "name": comp["name"],
        "day_start": comp["day_start"],
        "year": int(comp["day_start"][:4]),
        "pre_max": pre_max,
        "day": {h: pt["viewers"] for h, pt in day.items()},
        "day_ch": {h: pt["channels"] for h, pt in day.items()},
        "unlock": cls, "ea": ea, "weak": weak,
        "vpc1": (day[1]["viewers"] / day[1]["channels"]) if day.get(1) else 1.0,
        "has_pc": "PC" in plats,
        "mode": MODE.get(comp["name"], "sp"),
        "text": comp["unlock"],
    }


def load_pool():
    case = json.loads((KIT / "input/p00.in").read_text())
    pool = []
    for comp in case["comparables"]:
        f = features(comp)
        if f["day"].get(1):  # needs an hour-1 anchor
            pool.append(f)
    return pool


# ---------------- scoring ----------------

def pinball_loss(pred, actual):
    """pred: {h: [q05..q95]}, actual: {h: viewers}. Exact contest formula."""
    total, n = 0.0, 0
    for h in range(2, 25):
        if h not in actual or actual[h] is None:
            continue
        y = max(1.0, float(actual[h]))
        ly = math.log(y)
        for tau, q in zip(LEVELS, pred[h]):
            d = ly - math.log(max(1e-9, q))
            total += 2.0 * max(tau * d, (tau - 1.0) * d)
            n += 1
    return total / n if n else float("nan")


def baseline_pred(p1):
    p1 = max(1.0, float(p1))
    return {h: [p1 * math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z]
            for h in range(2, 25)}


# ---------------- model ----------------

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
    if tau <= cum[0]:
        return xs[0]
    for i in range(1, len(xs)):
        if tau <= cum[i]:
            frac = (tau - cum[i - 1]) / (cum[i] - cum[i - 1])
            return xs[i - 1] + frac * (xs[i] - xs[i - 1])
    return xs[-1]


UNLOCK_MATCH = {
    ("rolling", "rolling"): 1.0, ("rolling", "mixed"): 0.6,
    ("rolling", "unknown"): 0.45, ("rolling", "global"): 0.12,
    ("mixed", "mixed"): 1.0, ("mixed", "rolling"): 0.7,
    ("mixed", "unknown"): 0.45, ("mixed", "global"): 0.3,
    ("global", "global"): 1.0, ("global", "mixed"): 0.3,
    ("global", "rolling"): 0.12, ("global", "unknown"): 0.3,
    ("unknown", "rolling"): 0.6, ("unknown", "mixed"): 0.5,
    ("unknown", "global"): 0.3, ("unknown", "unknown"): 0.5,
}
MODE_MATCH = {("sp", "sp"): 1.0, ("sp", "coop"): 0.6, ("sp", "mp"): 0.35,
              ("coop", "sp"): 0.7, ("coop", "coop"): 1.0, ("coop", "mp"): 0.5,
              ("mp", "sp"): 0.4, ("mp", "coop"): 0.6, ("mp", "mp"): 1.0}

DEFAULT_PARAMS = {
    "scale_sigma": 1.1,     # kernel width for log hour-1 proximity
    "ea_factor": 0.35,      # early-access comp when target has none (and v.v.)
    "weak_factor": 0.4,
    "pc_match": 1.0, "pc_mismatch_down": 0.55, "pc_mismatch_up": 0.7,
    "gamma": 1.0,           # spread multiplier around the weighted median
    "min_hours": 18,        # comp must cover at least this many day hours
    "qmethod": "empirical", # "normal": mean + z*sd; "robust": median + z*(IQR/1.349)
    "smooth_med": 0,        # moving-average half-window for the median curve
    "recency_tau": None,    # years; exp(-|year gap|/tau) weight if set
    "target_year": 2026,
    "winsor": False,        # winsorize log-ratios at pooled 5/95 pct per hour
    "vpc_sigma": None,      # kernel width on log viewers-per-channel at hour 1
    "pre_sigma": None,      # kernel width on log(H1 / pre-launch max)
    "pool_filter": None,    # "A": sp/coop, non-global, H1>=5000; "B": console SP only
    "gamma_late": None,     # if set, gamma ramps gamma->gamma_late over hours 2..24
    "smooth_comp": 0,       # half-window to smooth each comp's log day curve
    "roll_global": None,    # override UNLOCK_MATCH[("rolling","global")]
    "roll_unknown": None,   # override UNLOCK_MATCH[("rolling","unknown")]
    "roll_mixed": None,     # override UNLOCK_MATCH[("rolling","mixed")]
    "mode_mp": None,        # override MODE_MATCH[("sp","mp")]
    "mode_coop": None,      # override MODE_MATCH[("sp","coop")]
    "temper": None,         # raise weights to this power (flatten concentration)
    "uniform_blend": None,  # mix this fraction of the mean weight into every weight
    "regime": False,        # two-regime mixture: anchored normal + stepper empirical
    "step_thresh": 1.386,   # log(peak/H1) at/above which a comp is a "stepper"
    "pi_sigma": 0.8,        # kernel width for P(stepper) over log(H1/pre_max)
    "step_temper": 0.5,     # tempering for stepper-pool weights
    "step_scale_sigma": 1.5,  # scale kernel width for stepper pool (peak vs proxy)
    "step_gamma": 1.0,      # shrink stepper samples toward their median by this
    "gate_h1": None,        # trickle gate: target H1 at/below this AND ...
    "gate_a": None,         # ... H1/pre_max at/below this -> stepper-level path
    "step_level_temper": 0.5,  # tempering for gated stepper-level pool
    "step_level_gamma": 1.0,   # shrink level quantiles toward median by this
    "step_shift": True,        # align stepper curves to a stated unlock time
    "gate_thresh": None,       # stepper label threshold for the gated pool
                               # (defaults to step_thresh)
    "step_shift_cap": None,    # cap |shift| when aligning stepper curves
    "step_tau_offset": 0,      # shift the parsed target step hour by this
    "step_blend": None,        # if set, average shifted & unshifted gated
                               # forecasts with this weight on the shifted one
    "tail_mix": (0.15, 2.2),   # (eps, k) for qmethod="mixn"
    "unk_global": None,        # override UNLOCK_MATCH[("unknown","global")]
    "unk_rolling": None,       # override UNLOCK_MATCH[("unknown","rolling")]
    "unk_mixed": None,         # override UNLOCK_MATCH[("unknown","mixed")]
    "step_smooth": 0,          # moving-average half-window for stepper curves
    "blend_w": 0.5,            # empirical share for qmethod="blend"
    "sep_regimes": False,      # keep stepper comps out of the anchored pool
}

ZTAU = {0.05: -1.644854, 0.25: -0.674490, 0.5: 0.0, 0.75: 0.674490, 0.95: 1.644854}


def factor_weight(target, comp, P):
    """Regime-match factors only (unlock / EA / weak / PC / mode)."""
    w = UNLOCK_MATCH[(target["unlock"], comp["unlock"])]
    if target["unlock"] == "rolling":
        if comp["unlock"] == "global" and P["roll_global"] is not None:
            w = P["roll_global"]
        elif comp["unlock"] == "unknown" and P["roll_unknown"] is not None:
            w = P["roll_unknown"]
        elif comp["unlock"] == "mixed" and P["roll_mixed"] is not None:
            w = P["roll_mixed"]
    if target["unlock"] == "unknown":
        if comp["unlock"] == "global" and P["unk_global"] is not None:
            w = P["unk_global"]
        elif comp["unlock"] == "rolling" and P["unk_rolling"] is not None:
            w = P["unk_rolling"]
        elif comp["unlock"] == "mixed" and P["unk_mixed"] is not None:
            w = P["unk_mixed"]
    if comp["ea"] != target["ea"]:
        w *= P["ea_factor"]
    if comp["weak"]:
        w *= P["weak_factor"]
    if comp["has_pc"] == target["has_pc"]:
        w *= P["pc_match"]
    elif comp["has_pc"]:
        w *= P["pc_mismatch_down"]   # target console-only, comp has PC
    else:
        w *= P["pc_mismatch_up"]     # target has PC, comp console-only
    mf = MODE_MATCH[(target["mode"], comp["mode"])]
    if target["mode"] == "sp" and comp["mode"] == "mp" and P["mode_mp"] is not None:
        mf = P["mode_mp"]
    if target["mode"] == "sp" and comp["mode"] == "coop" and P["mode_coop"] is not None:
        mf = P["mode_coop"]
    return w * mf


def comp_weight(target, comp, P):
    w = factor_weight(target, comp, P)
    dl = math.log(comp["day"][1]) - math.log(target["p1"])
    w *= math.exp(-(dl * dl) / (2 * P["scale_sigma"] ** 2))
    if P["recency_tau"]:
        w *= math.exp(-abs(comp["year"] - target.get("year", P["target_year"]))
                      / P["recency_tau"])
    if P["vpc_sigma"] and target.get("vpc1"):
        dv = math.log(comp["vpc1"]) - math.log(target["vpc1"])
        w *= math.exp(-(dv * dv) / (2 * P["vpc_sigma"] ** 2))
    if P["pre_sigma"] and target.get("pre_max"):
        dc = (math.log(comp["day"][1] / comp["pre_max"])
              - math.log(target["p1"] / target["pre_max"]))
        w *= math.exp(-(dc * dc) / (2 * P["pre_sigma"] ** 2))
    return w


def interp_log_ratio(day, h):
    """log V(h)/V(1) with log-space interpolation over missing hours."""
    if day.get(h):
        return math.log(day[h]) - math.log(day[1])
    lo = max([k for k in day if k < h and day[k]], default=None)
    hi = min([k for k in day if k > h and day[k]], default=None)
    if lo is None or hi is None:
        return None
    a = math.log(day[lo]) - math.log(day[1])
    b = math.log(day[hi]) - math.log(day[1])
    return a + (b - a) * (h - lo) / (hi - lo)


def regime_pred(target, pool, P, covered):
    """Two-regime mixture forecast.

    Each comparable is labelled from its OWN curve: a "stepper" if its day
    peaks at >= exp(step_thresh) x its hour-1 print (hour 1 was a pre-unlock
    trickle), else "anchored". The target's stepper probability is a
    Nadaraya-Watson estimate over log(H1/pre-launch peak) — the observable
    that separates the regimes. Anchored comps keep the usual weighted-normal
    fit; steppers form an empirical pool weighted by regime factors and a
    wide scale kernel on (comp day peak vs target max(H1, pre-launch peak)),
    tempered because step timing is not predictable from features. The
    predictive quantiles invert the mixture CDF.
    """
    p1 = target["p1"]
    info = []
    for comp in covered:
        day = comp["day"]
        peak = max(day[h] for h in range(1, 25) if day.get(h))
        stepper = math.log(peak / day[1]) >= P["step_thresh"]
        a = (day[1] / comp["pre_max"]) if comp.get("pre_max") else None
        info.append({"comp": comp, "stepper": stepper, "a": a, "peak": peak,
                     "w": comp_weight(target, comp, P)})
    # --- pi: P(stepper | target anchor ratio) ---
    pi = None
    if target.get("pre_max"):
        lt = math.log(target["p1"] / target["pre_max"])
        num = den = 0.0
        for e in info:
            if e["a"] is None:
                continue
            d = math.log(e["a"]) - lt
            k = math.exp(-(d * d) / (2 * P["pi_sigma"] ** 2))
            den += k
            if e["stepper"]:
                num += k
        if den > 1e-9:
            pi = num / den
    if pi is None:
        pi = sum(1 for e in info if e["stepper"]) / max(1, len(info))
    pi = min(0.98, max(0.02, pi))
    # --- stepper weights: factors x wide scale kernel on peaks, tempered ---
    proxy = max(target["p1"], target.get("pre_max") or 0.0)
    for e in info:
        if not e["stepper"]:
            e["sw"] = 0.0
            continue
        fw = factor_weight(target, e["comp"], P)
        d = math.log(e["peak"]) - math.log(proxy)
        fw *= math.exp(-(d * d) / (2 * P["step_scale_sigma"] ** 2))
        e["sw"] = fw ** P["step_temper"]
    anchored = [e for e in info if not e["stepper"] and e["w"] > 1e-6]
    steppers = [e for e in info if e["stepper"] and e["sw"] > 1e-9]
    pred = {}
    for h in range(2, 25):
        g = P["gamma"]
        if P["gamma_late"] is not None:
            g = g + (P["gamma_late"] - g) * (h - 2) / 22.0
        xs_a, ws_a, xs_s, ws_s = [], [], [], []
        for e in anchored:
            x = interp_log_ratio(e["comp"]["day"], h)
            if x is not None:
                xs_a.append(x)
                ws_a.append(e["w"])
        for e in steppers:
            x = interp_log_ratio(e["comp"]["day"], h)
            if x is not None:
                xs_s.append(x)
                ws_s.append(e["sw"])
        mu = sd = None
        if xs_a and sum(ws_a) > 0:
            tw = sum(ws_a)
            mu = sum(wi * xi for xi, wi in zip(xs_a, ws_a)) / tw
            var = sum(wi * (xi - mu) ** 2 for xi, wi in zip(xs_a, ws_a)) / tw
            sd = math.sqrt(max(var, 1e-6)) * g
        cum_s = None
        if xs_s and sum(ws_s) > 0:
            med_s = weighted_quantile(xs_s, ws_s, 0.5)
            if P["step_gamma"] != 1.0:
                xs_s = [med_s + P["step_gamma"] * (x - med_s) for x in xs_s]
            tot = sum(ws_s)
            order = sorted(range(len(xs_s)), key=lambda i: xs_s[i])
            xs_s = [xs_s[i] for i in order]
            cum_s, acc = [], 0.0
            for i in order:
                acc += ws_s[i] / tot
                cum_s.append(acc)
        if mu is None and cum_s is None:
            pred[h] = [p1] * 5
            continue
        pi_h = pi if (mu is not None and cum_s is not None) else \
            (1.0 if cum_s is not None else 0.0)

        def cdf(q, mu=mu, sd=sd, xs_s=xs_s, cum_s=cum_s, pi_h=pi_h):
            f = 0.0
            if mu is not None:
                f += (1 - pi_h) * 0.5 * (
                    1 + math.erf((q - mu) / (sd * math.sqrt(2))))
            if cum_s is not None:
                s = 0.0
                for xi, ci in zip(xs_s, cum_s):
                    if xi <= q:
                        s = ci
                    else:
                        break
                f += pi_h * s
            return f

        row = []
        for tau in LEVELS:
            lo, hi = -8.0, 10.0
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if cdf(mid) < tau:
                    lo = mid
                else:
                    hi = mid
            row.append(p1 * math.exp(0.5 * (lo + hi)))
        for i in range(1, 5):
            row[i] = max(row[i], row[i - 1])
        pred[h] = row
    return pred


_STAMP_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})")


def parse_unlock_step_hour(text, day_start):
    """Step hour (1..24) if the notes state an ISO unlock time on launch day.

    Research notes sometimes give the exact unlock instant ("single global
    unlock ... = 2024-08-20T02:00Z"). With day_start at 00:00Z the step lands
    in the hour containing that instant. Returns None when no same-day ISO
    timestamp is present.
    """
    if not text or not day_start:
        return None
    try:
        start = parse_ts(day_start)
    except Exception:
        return None
    for m in _STAMP_RE.finditer(text):
        try:
            stamp = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                             int(m.group(4)), int(m.group(5)),
                             tzinfo=timezone.utc)
        except ValueError:
            continue
        delta_h = (stamp - start).total_seconds() / 3600.0
        if 0 <= delta_h < 24:
            return int(delta_h) + 1
    return None


def stepper_level_pred(target, P, covered):
    """Forecast for a gated trickle target: transplanted stepper curves.

    Each stepper comparable (own peak >= exp(step_thresh) x own hour 1) is
    reduced to a step time tau_c (first hour its log-ratio reaches half its
    plateau) and a plateau. Its vote for the target at hour h reads the
    comparable's own timeline at j = h - (tau_t - tau_c):
      - before its step (j < tau_c): the TARGET's hour-1 level scaled by the
        comparable's pre-step ratio — a trickle is the target's own audience,
        not another game's;
      - from its step on: the comparable's absolute LEVEL — stepper peaks
        cluster within ~4x while their trickles span 30x, so levels are the
        transferable quantity.
    tau_t comes from the target's stated unlock time when the notes give
    one; otherwise no shift is applied and step timing stays a population
    distribution. Weights are regime factors only, tempered.
    """
    tau_t = None
    if P["step_shift"]:
        tau_t = parse_unlock_step_hour(target.get("text"),
                                       target.get("day_start"))
        if tau_t is not None:
            tau_t = min(24, max(1, tau_t + P["step_tau_offset"]))
    thresh = P["gate_thresh"] if P["gate_thresh"] is not None \
        else P["step_thresh"]
    steppers = []
    for comp in covered:
        day = comp["day"]
        peak = max(day[h] for h in range(1, 25) if day.get(h))
        plateau = math.log(peak / day[1])
        if plateau < thresh:
            continue
        tau_c = 25
        for h in range(2, 25):
            r = interp_log_ratio(day, h)
            if r is not None and r >= 0.5 * plateau:
                tau_c = h
                break
        w = factor_weight(target, comp, P) ** P["step_level_temper"]
        if w > 1e-9:
            curve = None
            if P["step_smooth"]:
                lvl = {}
                last = math.log(day[1])
                for hh in range(1, 25):
                    r = interp_log_ratio(day, hh)
                    if r is not None:
                        last = math.log(day[1]) + r
                    lvl[hh] = last
                k = P["step_smooth"]
                curve = {}
                for hh in range(1, 25):
                    vals = [lvl[j] for j in range(max(1, hh - k),
                                                  min(24, hh + k) + 1)]
                    curve[hh] = sum(vals) / len(vals)
            steppers.append((comp, w, tau_c, curve))
    if not steppers:
        return None
    log_p1 = math.log(target["p1"])
    pred = {}
    for h in range(2, 25):
        xs, ws = [], []
        for comp, w, tau_c, curve in steppers:
            day = comp["day"]
            shift = (tau_t - tau_c) if tau_t is not None else 0
            if P["step_shift_cap"] is not None:
                shift = max(-P["step_shift_cap"],
                            min(P["step_shift_cap"], shift))
            j = min(24, max(1, h - shift))
            if curve is not None:
                if j < tau_c:
                    xs.append(log_p1 + (curve[j] - curve[1]))
                else:
                    xs.append(curve[j])
                ws.append(w)
                continue
            r = interp_log_ratio(day, j)
            if r is None:
                continue
            if j < tau_c:
                xs.append(log_p1 + r)
            else:
                xs.append(math.log(day[1]) + r)
            ws.append(w)
        if not xs:
            pred[h] = [target["p1"]] * 5
            continue
        med = weighted_quantile(xs, ws, 0.5)
        row = []
        for tau in LEVELS:
            q = weighted_quantile(xs, ws, tau)
            row.append(math.exp(med + P["step_level_gamma"] * (q - med)))
        for i in range(1, 5):
            row[i] = max(row[i], row[i - 1])
        pred[h] = row
    return pred


def model_pred(target, pool, P=DEFAULT_PARAMS):
    p1 = target["p1"]
    covered = []
    for comp in pool:
        if comp["name"] == target["name"]:
            continue
        n_cov = sum(1 for h in range(1, 25) if comp["day"].get(h))
        if n_cov < P["min_hours"]:
            continue
        if P["pool_filter"] == "A":
            if comp["mode"] == "mp" or comp["unlock"] == "global" \
                    or comp["day"][1] < 5000:
                continue
        elif P["pool_filter"] == "B":
            if comp["mode"] != "sp" or comp["has_pc"] or comp["unlock"] == "global":
                continue
        if P["smooth_comp"]:
            k = P["smooth_comp"]
            day = comp["day"]
            sm = {}
            for h in range(1, 25):
                vals = [math.log(day[j]) for j in
                        range(max(1, h - k), min(24, h + k) + 1) if day.get(j)]
                if vals:
                    sm[h] = math.exp(sum(vals) / len(vals))
            comp = {**comp, "day": sm}
        covered.append(comp)
    if P["gate_h1"] is not None and target.get("pre_max"):
        if target["p1"] <= P["gate_h1"] and \
                target["p1"] / target["pre_max"] <= P["gate_a"]:
            gated = stepper_level_pred(target, P, covered)
            if gated is not None:
                if P["step_blend"] is not None and P["step_shift"]:
                    plain = stepper_level_pred(
                        target, {**P, "step_shift": False}, covered)
                    if plain is not None:
                        b = P["step_blend"]
                        for h in range(2, 25):
                            gated[h] = [
                                math.exp(b * math.log(max(1e-9, gated[h][i]))
                                         + (1 - b) * math.log(
                                             max(1e-9, plain[h][i])))
                                for i in range(5)]
                return gated
    if P["regime"]:
        return regime_pred(target, pool, P, covered)
    usable = []
    for comp in covered:
        if P["sep_regimes"]:
            day = comp["day"]
            peak = max(day[h] for h in range(1, 25) if day.get(h))
            if math.log(peak / day[1]) >= P["step_thresh"]:
                continue  # stepper comps stay out of the anchored pool
        w = comp_weight(target, comp, P)
        if P["temper"] is not None:
            w = w ** P["temper"]
        if w > 1e-6:
            usable.append((comp, w))
    if P["uniform_blend"] is not None and usable:
        lam = P["uniform_blend"]
        mean_w = sum(w for _, w in usable) / len(usable)
        usable = [(c, (1 - lam) * w + lam * mean_w) for c, w in usable]
    # Collect per-hour weighted log-ratio samples.
    samples = {}
    for h in range(2, 25):
        xs, ws = [], []
        for comp, w in usable:
            x = interp_log_ratio(comp["day"], h)
            if x is not None:
                xs.append(x)
                ws.append(w)
        samples[h] = (xs, ws)
    # Raw per-hour quantiles (log space) and centres.
    raw, centre = {}, {}
    for h, (xs, ws) in samples.items():
        if not xs:
            raw[h] = None
            continue
        if P["qmethod"] == "normal":
            tw = sum(ws)
            mu = sum(w * x for x, w in zip(xs, ws)) / tw
            var = sum(w * (x - mu) ** 2 for x, w in zip(xs, ws)) / tw
            sd = math.sqrt(max(var, 1e-6))
            centre[h] = mu
            raw[h] = [mu + ZTAU[t] * sd for t in LEVELS]
        elif P["qmethod"] == "trimnormal":
            # Weighted mean/sd after trimming samples outside the weighted
            # [15%, 85%] quantile band (robust centre vs regime contamination).
            lo_q = weighted_quantile(xs, ws, 0.15)
            hi_q = weighted_quantile(xs, ws, 0.85)
            keep = [(x, w) for x, w in zip(xs, ws) if lo_q <= x <= hi_q]
            if len(keep) >= 3:
                xs2 = [x for x, _ in keep]
                ws2 = [w for _, w in keep]
            else:
                xs2, ws2 = xs, ws
            tw = sum(ws2)
            mu = sum(w * x for x, w in zip(xs2, ws2)) / tw
            var = sum(w * (x - mu) ** 2 for x, w in zip(xs2, ws2)) / tw
            sd = math.sqrt(max(var, 1e-6))
            centre[h] = mu
            raw[h] = [mu + ZTAU[t] * sd for t in LEVELS]
        elif P["qmethod"] == "mixn":
            # Scale-mixture normal: (1-eps) N(mu, sd) + eps N(mu, k*sd),
            # a Student-t-like robust predictive. Quantiles by CDF inversion;
            # pre-divided by the hour's gamma so the caller's shrink is a
            # no-op on them.
            tw = sum(ws)
            mu = sum(w * x for x, w in zip(xs, ws)) / tw
            var = sum(w * (x - mu) ** 2 for x, w in zip(xs, ws)) / tw
            sd = math.sqrt(max(var, 1e-6))
            centre[h] = mu
            g_h = P["gamma"]
            if P["gamma_late"] is not None:
                g_h = g_h + (P["gamma_late"] - g_h) * (h - 2) / 22.0
            eps, kk = P["tail_mix"]

            def mixcdf(q, mu=mu, sd=sd):
                z1 = (q - mu) / sd
                z2 = (q - mu) / (kk * sd)
                return (1 - eps) * 0.5 * (1 + math.erf(z1 / math.sqrt(2))) \
                    + eps * 0.5 * (1 + math.erf(z2 / math.sqrt(2)))

            qs = []
            for tau in LEVELS:
                lo, hi = mu - 8 * kk * sd, mu + 8 * kk * sd
                for _ in range(50):
                    mid = 0.5 * (lo + hi)
                    if mixcdf(mid) < tau:
                        lo = mid
                    else:
                        hi = mid
                qs.append(0.5 * (lo + hi))
            raw[h] = [mu + (q - mu) / g_h for q in qs]
        elif P["qmethod"] == "cf":
            # Cornish-Fisher: normal quantiles corrected by pooled skewness.
            tw = sum(ws)
            mu = sum(w * x for x, w in zip(xs, ws)) / tw
            var = sum(w * (x - mu) ** 2 for x, w in zip(xs, ws)) / tw
            sd = math.sqrt(max(var, 1e-6))
            m3 = sum(w * (x - mu) ** 3 for x, w in zip(xs, ws)) / tw
            skew = max(-1.0, min(1.5, m3 / max(sd ** 3, 1e-9)))
            centre[h] = mu
            raw[h] = [mu + sd * (ZTAU[t] + (ZTAU[t] ** 2 - 1) * skew / 6.0)
                      for t in LEVELS]
        elif P["qmethod"] == "normalm":
            med = weighted_quantile(xs, ws, 0.5)
            tw = sum(ws)
            var = sum(w * (x - med) ** 2 for x, w in zip(xs, ws)) / tw
            sd = math.sqrt(max(var, 1e-6))
            centre[h] = med
            raw[h] = [med + ZTAU[t] * sd for t in LEVELS]
        elif P["qmethod"] == "blend":
            tw = sum(ws)
            mu = sum(w * x for x, w in zip(xs, ws)) / tw
            var = sum(w * (x - mu) ** 2 for x, w in zip(xs, ws)) / tw
            sd = math.sqrt(max(var, 1e-6))
            centre[h] = weighted_quantile(xs, ws, 0.5)
            bw = P["blend_w"]
            raw[h] = [bw * weighted_quantile(xs, ws, t)
                      + (1 - bw) * (mu + ZTAU[t] * sd) for t in LEVELS]
        elif P["qmethod"] == "robust":
            med = weighted_quantile(xs, ws, 0.5)
            iqr = weighted_quantile(xs, ws, 0.75) - weighted_quantile(xs, ws, 0.25)
            sd = max(iqr / 1.349, 0.05)
            centre[h] = med
            raw[h] = [med + ZTAU[t] * sd for t in LEVELS]
        else:
            centre[h] = weighted_quantile(xs, ws, 0.5)
            raw[h] = [weighted_quantile(xs, ws, t) for t in LEVELS]
    # Optional smoothing of the centre (median) curve across hours.
    med = dict(centre)
    if P["smooth_med"]:
        k = P["smooth_med"]
        for h in range(2, 25):
            if h not in centre:
                continue
            vals = [centre[j] for j in range(max(2, h - k), min(24, h + k) + 1)
                    if j in centre]
            med[h] = sum(vals) / len(vals)
    pred = {}
    for h in range(2, 25):
        if raw[h] is None:
            pred[h] = [p1] * 5
            continue
        g = P["gamma"]
        if P["gamma_late"] is not None:
            g = g + (P["gamma_late"] - g) * (h - 2) / 22.0
        row = []
        for q in raw[h]:
            adj = q + (med[h] - centre[h])          # shift by smoothed centre
            adj = med[h] + g * (adj - med[h])
            row.append(p1 * math.exp(adj))
        for i in range(1, 5):
            row[i] = max(row[i], row[i - 1])
        pred[h] = row
    return pred


# ---------------- LOO ----------------

def run_loo(P=DEFAULT_PARAMS, verbose=True):
    pool = load_pool()
    rows = []
    for comp in pool:
        target = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
                  "has_pc": comp["has_pc"], "mode": comp["mode"],
                  "year": comp["year"], "vpc1": comp["vpc1"],
                  "text": comp["text"], "day_start": comp["day_start"],
                  "pre_max": comp["pre_max"], "p1": float(comp["day"][1])}
        actual = comp["day"]
        bl = pinball_loss(baseline_pred(target["p1"]), actual)
        md = pinball_loss(model_pred(target, pool, P), actual)
        rows.append((comp["name"], comp["unlock"], comp["ea"], target["p1"], bl, md))
    if verbose:
        print(f"{'target':45s} {'cls':8s} {'ea':2s} {'H1':>8s} {'base':>7s} {'model':>7s}")
        for name, cls, ea, p1, bl, md in rows:
            print(f"{name[:45]:45s} {cls:8s} {str(ea):2s} {p1:8.0f} {bl:7.3f} {md:7.3f}")
    def mean(sel):
        vals = [(bl, md) for _, cls, ea, _, bl, md in rows if sel(cls, ea)]
        return (sum(v[0] for v in vals) / len(vals), sum(v[1] for v in vals) / len(vals), len(vals))
    allm = mean(lambda c, e: True)
    roll = mean(lambda c, e: c in ("rolling", "mixed"))
    if verbose:
        print(f"\nALL targets        n={allm[2]:2d}  baseline {allm[0]:.4f}  model {allm[1]:.4f}")
        print(f"ROLLING/MIXED only n={roll[2]:2d}  baseline {roll[0]:.4f}  model {roll[1]:.4f}")
    return rows


_POOL = None


def score_params(P, pool=None):
    """Quiet LOO: returns dict of mean model losses (all / rolling / gta-like)."""
    global _POOL
    if pool is None:
        if _POOL is None:
            _POOL = load_pool()
        pool = _POOL
    sums = {"all": [], "rolling": [], "gta": []}
    base = {"all": [], "rolling": [], "gta": []}
    for comp in pool:
        target = {"name": comp["name"], "unlock": comp["unlock"], "ea": comp["ea"],
                  "has_pc": comp["has_pc"], "mode": comp["mode"],
                  "year": comp["year"], "vpc1": comp["vpc1"],
                  "text": comp["text"], "day_start": comp["day_start"],
                  "pre_max": comp["pre_max"], "p1": float(comp["day"][1])}
        md = pinball_loss(model_pred(target, pool, P), comp["day"])
        bl = pinball_loss(baseline_pred(target["p1"]), comp["day"])
        sums["all"].append(md)
        base["all"].append(bl)
        if comp["unlock"] in ("rolling", "mixed"):
            sums["rolling"].append(md)
            base["rolling"].append(bl)
            if comp["mode"] == "sp" and not comp["has_pc"]:
                sums["gta"].append(md)
                base["gta"].append(bl)
    out = {}
    for k in sums:
        out[k] = sum(sums[k]) / len(sums[k])
        out[k + "_base"] = sum(base[k]) / len(base[k])
        out[k + "_n"] = len(sums[k])
    return out


if __name__ == "__main__":
    run_loo()
