"""Leave-one-out validation over the kit's comparables.

Each comparable with a usable release day takes a turn as the pseudo-target:
anchor on its release-day hour-1 viewers, predict hours 2..24 quantiles from
the OTHER comparables, and score with the contest's exact pinball-log loss.
The house baseline (starter formula) goes through the same harness.
"""
import json
import math
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
}

ZTAU = {0.05: -1.644854, 0.25: -0.674490, 0.5: 0.0, 0.75: 0.674490, 0.95: 1.644854}


def comp_weight(target, comp, P):
    w = UNLOCK_MATCH[(target["unlock"], comp["unlock"])]
    if target["unlock"] == "rolling":
        if comp["unlock"] == "global" and P["roll_global"] is not None:
            w = P["roll_global"]
        elif comp["unlock"] == "unknown" and P["roll_unknown"] is not None:
            w = P["roll_unknown"]
        elif comp["unlock"] == "mixed" and P["roll_mixed"] is not None:
            w = P["roll_mixed"]
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
    w *= mf
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


def model_pred(target, pool, P=DEFAULT_PARAMS):
    p1 = target["p1"]
    usable = []
    for comp in pool:
        if comp["name"] == target["name"]:
            continue
        covered = sum(1 for h in range(1, 25) if comp["day"].get(h))
        if covered < P["min_hours"]:
            continue
        if P["pool_filter"] == "A":
            if comp["mode"] == "mp" or comp["unlock"] == "global" \
                    or comp["day"][1] < 5000:
                continue
        elif P["pool_filter"] == "B":
            if comp["mode"] != "sp" or comp["has_pc"] or comp["unlock"] == "global":
                continue
        w = comp_weight(target, comp, P)
        if w > 1e-6:
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
            usable.append((comp, w))
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
            raw[h] = [0.5 * weighted_quantile(xs, ws, t) + 0.5 * (mu + ZTAU[t] * sd)
                      for t in LEVELS]
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
