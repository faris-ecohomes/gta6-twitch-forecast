# Tuning report, round 2 — below 0.30 with the protected subsets frozen

## Result

| metric | round 1 | round 2 (final) | house baseline |
|---|---|---|---|
| ALL (n=37) | 0.3183 | **0.2989** | 0.9297 |
| rolling/mixed (n=12) | 0.2404 | 0.2404 — outputs byte-identical | 0.3568 |
| GTA-like (n=4) | 0.1576 | 0.1576 — outputs byte-identical | 0.3006 |

**The < 0.30 goal was reached**, under the hard constraint: for every LOO
target in the rolling/mixed and GTA-like subsets, the final `main.py`
produces forecasts byte-identical to the round-1 model (verified per case
by dev/eval2.py against dev/main_round1.py; every protected per-case delta
is exactly +0.0000). All improvement came from the 25 unprotected targets:
their loss sum fell 8.891 -> 8.177 (gated group 4.658 -> 4.380; anchored
unknown/global group 4.234 -> 3.797). Verified end-to-end with
dev/fidelity.py on the ported main.py: ALL 0.2989, rolling 0.2404,
GTA-like 0.1576.

## What the diagnosis said before any knob moved

- **Step timing is information-bound.** An oracle that knows each gated
  target's true step hour cuts the gated sum from 4.658 to 3.794, but no
  quantity observable at forecast time predicts that hour for the five
  timestamp-less gated targets: pre-launch hour-of-day audience profile,
  pre-peak timing, hour-1 channels, viewers-per-channel and trickle ratio
  are all noisy at n=8 and mutually contradictory (Marathon and ARC
  Raiders are near-twins on every one of them, yet step 7 hours apart).
  Round 2 therefore does not pretend to predict timing; it prices timing
  uncertainty in instead (smoothing, below).
- **The stepper pool is diluted.** The plateau >= 4x rule admits five
  minor risers (peaks 36k-179k) alongside the eight true steppers (peaks
  145k-564k). Their absolute levels drag down the plateau votes of the
  big targets — ARC Raiders' h20 median vote was 176k against a pool
  median peak of ~366k.
- **The anchored centre runs hot late for unclassified targets.** For
  nearly every unknown-unlock target the pooled centre rises all day
  while the actual curve flattens or decays (Borderlands 4, Marvel
  Rivals, Starfield, Nightreign, Forza Horizon 5). The genuine risers in
  the same class (Clair Obscur, Forza Horizon 6) are indistinguishable
  from the flat cases on every observable tried — Saros vs Clair Obscur
  is the standing example — so any centre correction buys its gains
  partly with their losses.

## The four changes that did the work

1. **Peak tilt in the stepper pool** — pool weight x (comp peak / 1e5)^0.5.
   A gated target is a major launch; tilting votes toward comparables
   that stepped to a major audience undoes the dilution above without
   removing anyone. ARC Raiders 0.782 -> 0.629, Silksong 0.475 -> 0.253
   (with smoothing), Wukong 0.370 -> 0.313, KCD2 0.574 -> 0.489,
   Battlefield 6 0.400 -> 0.347. Cost: Marathon +0.111 and Baldur's
   Gate 3 +0.047 (the two gated targets whose true peaks are at the
   pool's low end / whose twins are small).
2. **Binomial smoothing of the gated quantile tracks** — five passes of
   [0.25, 0.5, 0.25] over the log-quantiles (a binomial kernel of
   half-width 5). This is the honest response to the timing diagnosis:
   if the step lands within a few hours of the pool's timing rather than
   exactly on it, adjacent hours should share their quantiles. It is the
   single largest gated gain after the tilt (Silksong and ARC Raiders
   gain most; the sharp-step cases, Wukong included, are essentially
   unharmed because their steps are timestamp-aligned, not smeared by
   the mixture in the first place). Passes 4/5/6 score 0.2994 / 0.2989 /
   0.2987 — a flat tail, so the pass count is not a knife-edge choice.
3. **Late-day centre calibration for unclassified-unlock targets only**
   (anchored path; target unlock unknown or global): a positive centre
   is shrunk by up to 35% across the day and a -0.15 log bias is ramped
   in, both proportional to (h-2)/22. Rolling/mixed targets skip the
   branch entirely — same constants, same float ops — which is what
   keeps the protected subsets byte-identical by construction, not by
   luck. Buys Saros -0.132, Borderlands 4 -0.098, Starfield -0.078,
   Nightreign -0.065, Marvel Rivals -0.062, Forza 5 -0.052; costs Clair
   Obscur +0.103, Forza 6 +0.107, Ghost of Tsushima +0.042, Diablo IV
   +0.027. Net -0.44 across the group.
4. **TAU_OFFSET -2 -> -3** — the round-1 report already flagged this as
   the softest knob (flat between -2 and -3); round 2's end-to-end sweep
   puts -3 ahead by ~0.02 of sum, almost all of it Silksong. Kept, with
   the same ±1h uncertainty caveat as round 1.

## Experiments that failed (kept out; full table in dev/tuning-log-2.md)

- Stepper-pool surgery (higher plateau threshold, absolute peak floor):
  every variant taxes Marathon more than it repays the big targets —
  Marathon's forecast leans on exactly the minor curves the surgery
  removes.
- Local-linear centre in pre_stat (the textbook fix for kernel boundary
  bias): explodes on the extreme-pre_stat targets (Saros, Halo) even
  with the adjustment clipped; rejected in all forms.
- Pre-stat kernel sharpening, scale-kernel changes, unlock-match row
  overrides, gamma widening/narrowing for the unclassified group,
  step-fraction and pre-step-cap variants, inverse-CDF vote quantiles:
  all flat or negative end-to-end. As in round 1, the anchored kernel
  machinery itself is saturated; only the bias correction on top of it
  paid.

## Honest notes — where the floor sits

- The margin below 0.30 is 0.0011 of mean (0.04 of sum). The mechanisms
  are general and each was visible in diagnosis before it was fitted,
  but the last few thousandths are LOO noise, and two constants
  (TAU_OFFSET, the smoothing pass count) sit on flat response plateaus
  where neighbouring values score within ±0.002. Read the result as
  "≈0.30, defensibly below" rather than a precise 0.2989.
- The residual loss is concentrated where round 1 left it: Marathon
  1.058 (its late step remains unpredictable; round 2's peak tilt
  actually costs it 0.111, accepted because the same tilt repays 0.42
  across the other gated targets), Resident Evil Requiem 1.037
  (protected — untouchable this round by design), HELLDIVERS 2 0.632,
  ARC Raiders 0.629, Halo Infinite 0.617 (a dip-then-second-wave curve
  no single-centre model in this family will fit).
- Under the byte-identity constraint the theoretical floor is roughly
  the oracle bound: even perfect step timing AND plateau level in the
  gated branch (3.254) plus the achieved anchored gains would land near
  0.28; timing is not observable, so ~0.295-0.30 is the practical floor
  of this model family under the constraint. Going further needs new
  information (a real unlock-time signal), not new knobs.
- Nothing here touches the real final case's regime: GTA VI's hour 1
  will be far above the gate, its unlock class is rolling, and rolling
  targets run the original anchored path byte-for-byte. The round-2
  changes, like round 1's, buy robustness in regimes the final case
  does not occupy.

## Verification (all run on the final tree)

- dev/fidelity.py: ALL 0.2989, rolling 0.2404, GTA-like 0.1576.
- dev/eval2.py vs dev/main_round1.py: protected byte-identity OK; every
  protected per-case delta exactly +0.0000.
- Kit inputs p00-p03 through main.py as a script (dev/kit_check2.py):
  outputs valid (23 hours x 5 quantiles, monotone, within (0, 1e9],
  ~1.7 KB per file), two full runs byte-identical, ~0.26 s per case
  (limit 8 s). Gate does not fire on the practice cases.
- Imports are stdlib only (json, math, os, re, datetime, pathlib). No
  network, no randomness, no state. Working tree only — nothing
  committed.
