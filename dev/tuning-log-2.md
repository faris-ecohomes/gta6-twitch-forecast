# Tuning log, round 2 — ALL < 0.30 with protected subsets frozen

Constraint: every rolling/mixed LOO target (n=12) and GTA-like target (n=4)
must stay BYTE-IDENTICAL to the round-1 model (dev/main_round1.py).
Evaluator: dev/fidelity.py end-to-end through main.py (authoritative);
dev/runner.py + dev/eval2.py check per-case deltas and byte-identity on
every run. All numbers below are end-to-end fidelity numbers.

Baseline (round 1, reproduced): ALL 0.3183 (sum 11.775) | rolling 0.2404 |
GTA-like 0.1576. Needed: sum < 11.100, i.e. -0.675 from unprotected cases
only (gated sum 4.658; anchored unprotected sum 4.234).

## Diagnosis (dev/diag_gated.py, diag_oracle.py, diag_votes.py,
## diag_predictors.py, diag_anchored.py, diag_pool.py)
- Oracle decomposition of the gated branch: perfect step timing alone
  4.658 -> 3.794; perfect plateau level alone -> 4.235; both -> 3.254.
  But NO observable predicts step hour for the 5 timestamp-less gated
  targets (pre-launch hour-of-day profile, pre-peak gap, hour-1 channels,
  viewers/channel, trickle ratio: all noisy at n=8, mutually
  contradictory — Marathon and ARC Raiders are near-twins on every
  observable yet step 7 hours apart). Timing is at its information limit.
- The stepper POOL is bigger than the 8 gated games: plateau >= ln4 also
  admits RE Requiem (12x, peak 563k), Clair Obscur (11x, 118k), Halo
  Infinite (8.7x, 179k), Saros (5.6x, 36k), Forza Horizon 6 (5.3x, 139k).
  Their low absolute levels dilute the big targets' plateau votes
  (ARC Raiders' q50 at h20 = 176k vs pool median peak ~366k).
- Anchored unknown/global targets: the pooled centre rises all day for
  nearly every target while actuals often flatten or decay (Borderlands 4,
  Marvel Rivals, Starfield, Nightreign, Forza 5) — a systematic late-day
  upward bias. True risers in the same class (Clair Obscur, Forza 6) are
  the collateral of any blanket correction; no observable separates
  Saros (helped most by correction) from Clair Obscur (hurt most).

## Experiments (ALL; protected bytes OK in every row)
| change | ALL | verdict |
|--------|-----|---------|
| STEP_THRESH ln8 / ln20+ | 0.3178 / 0.3251 | reject (Marathon +0.11 / +0.45) |
| STEP_TEMPER 0 / .15 / .5 / .8 | 0.3218 / 0.3191 / 0.3192 / 0.3228 | flat; keep 0.3 |
| TAU_OFFSET -4 / -3 / -1 / 0 | 0.3204 / 0.3177 / 0.3237 / 0.3362 | -3 marginal, kept in package |
| STEP_TAU_FRAC 0.3 / 0.7 | 0.3239 / 0.3210 | reject |
| STEP_GAMMA 0.85 / 1.15 / 1.3 | 0.3139 / 0.3135 / 0.3163 (pkg) | reject |
| STEP_PRE_CAP 1.1 / 1.8 / 2.3 | 0.3165 / 0.3142 / 0.3133 (pre-pkg) | reject (ARC/HD2 pay) |
| STEP_QMETHOD inverse-CDF | 0.3115 (pkg) | reject |
| STEP_PEAK_FLOOR 100k-250k | ~ thresh variants | reject (same trade as thresh) |
| STEP_PEAK_WEXP -0.5 / +0.75 / +1.0 | 0.3261 / 0.3102 / 0.3119 (pkg) | +0.5 best |
| **STEP_PEAK_WEXP +0.5** | **0.3091 (pkg)** | **KEEP** |
| UG_PRE_SIGMA 0.7 / 0.9 | 0.3194 / 0.3185 | reject |
| UG_LL 0.5 / 1.0, clipped 0.3, combined | 0.3218 / 0.3302 / worse | reject: extrapolation explodes on extreme pre_stat (Saros, Halo) |
| UG gamma .75/.60, .95/.80, .90/1.05, .85/1.20 | 0.3189 / 0.3189 / 0.3134 / 0.3154 | reject |
| UG_UNK_ROLL .9 + UG_UNK_GLOB .15 | 0.3186 | reject |
| UG_SCALE_SIGMA variants | ~0.318-0.319 | reject (noise) |
| **UG_MU_LATE 0.15/.25/.35/.45 (sym)** | 0.3147 / 0.3134 / 0.3131 / 0.3137 | **KEEP mechanism** |
| **UG_MU_LATE 0.25, positive-mu only** | **0.3130** | **KEEP form** |
| **UG_MU_BIAS -0.08 / -0.15 / -0.20 (pkg)** | 0.3033 / 0.3027 / 0.3001 (with smooth x1-3) | **KEEP -0.15** |
| **STEP_SMOOTH 0.5 / 1.0 x1 pass (pkg)** | 0.3066 / 0.3052 | **KEEP** |
| **STEP_SMOOTH x2 / x3 / x4 / x5 / x6 (pkg+bias)** | 0.3011 / 0.3001 / 0.2994 / 0.2989 / 0.2987 | **KEEP x5** (flat tail) |

Package assembly (cumulative): round-1 0.3183 -> +TAU_OFFSET -3 &
MU_LATE 0.25 POS 0.3125 -> +PEAK_WEXP 0.5 0.3091 -> MU_LATE 0.35 0.3086
-> +SMOOTH x1 0.3052 -> +BIAS -0.15 & SMOOTH x5 0.2989.

## Final configuration (ported to main.py, uncommitted)
1. TAU_OFFSET -2 -> -3.
2. Stepper pool weight x (comp peak / 1e5) ** 0.5 (STEP_PEAK_WEXP).
3. Gated output tracks smoothed: 5 passes of [0.25, 0.5, 0.25] over
   log-quantiles (binomial kernel, half-width 5).
4. Anchored calibration for target unlock in {unknown, global} ONLY:
   if mu > 0: mu *= 1 - 0.35*(h-2)/22; then mu += -0.15*(h-2)/22.
   Rolling/mixed targets skip the branch entirely (identical float ops).

FINAL (fidelity, ported main.py): ALL 0.2989 | rolling 0.2404 |
GTA-like 0.1576 | protected byte-identity OK.
Gated group 4.658 -> 4.380; anchored unprotected 4.234 -> 3.797.
