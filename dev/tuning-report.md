# Tuning report — pseudo-LOO push toward < 0.30

## Result

| metric | start (submitted model) | final | house baseline |
|---|---|---|---|
| ALL (n=37) | 0.4542 | **0.3183** | 0.9297 |
| rolling/mixed (n=12) | 0.2404 | 0.2404 (unchanged) | 0.3568 |
| GTA-like (n=4) | 0.1576 | 0.1576 (unchanged) | 0.3006 |

**The < 0.30 goal was NOT reached.** The final model cuts the ALL loss by
30% (0.4542 -> 0.3183) with both guardrail subsets exactly untouched, then
plateaus: the last ~10 experiment rounds moved ALL by less than ±0.005
each, and every remaining large loss sits in a case whose decisive feature
(step timing, step height, or an unusually strong all-day build) is not
observable at forecast time. Verified end-to-end: the ported `main.py`,
run on synthesized LOO cases in the real input format, reproduces the
harness numbers exactly (dev/fidelity.py): ALL 0.3183, rolling 0.2404,
GTA-like 0.1576.

## Where the loss was, and what remains

Per-regime means (start -> final):

| group | n | start | final |
|---|---|---|---|
| gated trickle targets | 8 | 1.2110 | 0.5822 |
| anchored targets | 29 | 0.2454 | 0.2454 |
| unlock=global | 5 | 0.8432 | 0.3735 |
| unlock=unknown | 20 | 0.4853 | 0.3512 |
| unlock=rolling | 8 | 0.2659 | 0.2659 |
| unlock=mixed | 4 | 0.1892 | 0.1892 |

Diagnosis (dev/diag1.py, diag2.py): 75% of the starting loss mass sat in
launches whose day peaks at >= 3x their hour-1 print. The extreme ones are
"steppers": hour 1 is a pre-unlock trickle (hundreds to a few thousand
viewers), and the curve steps up +4 to +8 log once the unlock lands — at
hour 3 for Wukong, ~10 for ARC Raiders, ~13-14 for BG3/Silksong, ~17 for
Marathon. The submitted model failed them twice over: its scale kernel
judged comparables by hour-1 size (meaningless for a trickle), collapsing
the effective pool to ~1 comparable (Marathon forecast = 93% ARC Raiders,
which steps 7 hours earlier; ARC's = 89% Marathon), and its ratios-to-hour-1
framing cannot express "the audience has not arrived yet".

Worst remaining cases: Resident Evil Requiem 1.037 (rolling riser: builds
to +2.5 log by hour 20 on a US-unlock wave; its pool's risers top out near
+1.3, so the centre undershoots all day — no observable separates it from
milder risers), Marathon 0.948 (latest stepper in the pool; any population
forecast steps too early for it), ARC Raiders 0.782 (mirror image),
HELLDIVERS 2 0.628, Halo Infinite 0.625 (gradual risers the anchored fit
under-rises).

## The change that did the work (one architectural change, three parts)

A hard **trickle gate** in front of the existing model, plus a dedicated
forecast behind it. The existing anchored model is byte-for-byte untouched
for every non-gated target — which is why the guardrail subsets did not
move at all.

1. **Gate** — fires when hour-1 viewers <= 6,000 AND hour 1 <= 60% of the
   pre-launch peak: hour 1 is then demonstrably not a launch measurement.
   In the LOO pool this selects exactly the 8 trickle launches (Wukong,
   Silksong, Battlefield 6, Marathon, BG3, KCD2, ARC Raiders, HELLDIVERS 2)
   and nothing else; boundary tests (H1 <= 4,000 or ratio <= 0.5) are much
   worse because they drop Wukong (H1 4,941, ratio 0.55) back into the
   anchored model. Effect alone (level-space pool): 0.4542 -> 0.3835.
2. **Transplant sampling** — each stepper comparable votes at hour h from
   its own timeline: before its step, the *target's* hour-1 level scaled
   by the comparable's pre-step ratio (a trickle is the target's own
   audience, not another game's); from its step on, the comparable's
   *absolute level* (stepper peaks cluster at 145k-564k, within ~4x, while
   their trickles span 30x — levels are the transferable quantity).
   Weights are regime factors only (unlock/EA/weak/PC/mode), tempered
   ^0.3, because step timing is not predictable from features; quantiles
   are the weighted empirical quantiles of the votes. 0.3835 -> 0.3793,
   and it fixes the early-hour overshoot for the quietest trickles
   (HELLDIVERS 2's pre-step audience is ~100-500, not the population's
   ~2,000 median).
3. **Unlock-time alignment** — when the case notes state the unlock
   instant as an ISO timestamp on the launch date (Wukong "…= 2024-08-20
   T02:00Z", Silksong "2025-09-04T14:00Z", Battlefield "…T14:00…"), every
   comparable's step is shifted to align with it, with the step placed 2
   hours before the stated instant (audiences reach half-plateau ahead of
   the official time: countdown/preload streams, hourly buckets labelled
   by their end). No timestamp -> no shift. 0.3793 -> 0.3183; Wukong
   1.87 -> 0.38, BG3 0.97 -> 0.48, Silksong -> 0.48.

## Experiments that failed (kept out)

- **Soft two-regime mixture** (stepper probability from a kernel over
  log(H1/pre), mixture CDF): 0.5456. The probability leaks onto every
  anchored target (~+0.05 each) and dilutes the good single-comparable
  clones (HELLDIVERS 2 +1.25, Wukong +0.82). Hard gating beat soft mixing
  decisively.
- **Empirical quantiles / weight tempering / uniform blending** on the
  anchored model: 0.42-0.48; tempering's apparent ALL gain came only from
  the trickle cases the gate later took over, and it taxed the anchored
  bulk once they were gone.
- **Heavy tails** (normal scale mixture), **trimmed centre**,
  **Cornish-Fisher skew**: 0.32-0.34 with guardrail damage (GTA-like up to
  0.19-0.21). The well-calibrated regime pays more for wider intervals
  than the outliers gain.
- **Hard regime separation** (banning stepper comps from anchored pools):
  0.3381, rolling 0.2760, GTA-like 0.1857 — rolling/console targets
  actively *need* riser and stepper curves in their pools.
- **Viewers-per-channel kernel**: 0.3491-0.3663, both guardrails worse.
- **Normal/empirical blend quantiles** (best micro-variant, 0.3128-0.3147):
  real but tiny ALL gain bought with GTA-like headroom (0.1576 -> 0.1609+).
  Not ported: the task's guardrail logic says not to trade the real
  case's regime for the average.
- ~25 single-knob sweeps on the anchored side (scale/pre kernels, EA,
  weak, PC, mode, gamma ramps, smoothing, recency, unlock-match overrides,
  coverage minimums): all within ±0.005 — that side of the model is
  saturated.

## Overfitting risk — honest notes

- The headline improvement rests on 8 gated cases. The gate itself is a
  coarse, order-of-magnitude rule (thousands of viewers; a ratio, not a
  tuned boundary), and each of its two conditions is doing visible work
  (dropping either resurrects specific disasters). I judge the gate and
  the transplant/level-space construction to be genuinely structural:
  they encode *why* the old model failed, not *which games* it failed on.
  No game names, ids, or per-case adjustments appear anywhere.
- The softest number is **TAU_OFFSET = -2**: per-case optima are 0
  (Wukong), -1 (Battlefield), -2 (Silksong), and the aggregate curve is
  flat between -2 and -3 (0.3183 vs 0.3177). It is one global constant
  with a stated mechanism, but on 3 timestamped cases it should be read
  as ±1 hour uncertain. If the final case were gated (it is not — GTA
  VI's hour 1 will be enormous), this is the knob I would trust least.
- The stepper label threshold (peak >= 4x hour 1) and the tempering
  exponent (0.3) were swept; the response surface is flat around the
  chosen values (0.318-0.340 across the whole grid), which is reassuring.
- The final pool will contain 42 comparables (the 4 practice launches
  join as pool members, all anchored console single-player games). The
  gate cannot fire on the real case (hour 1 will be far above 6,000), so
  the shipped change can only affect hypothetical trickle targets; the
  real forecast runs the original, untouched anchored path. The LOO gain
  is therefore best read as "the model is now much less wrong on a whole
  regime" rather than as points bought for the final.
- Residual risk accepted knowingly: RE Requiem-type risers (rolling,
  strong all-day build) remain the largest single loss. Three separate
  mechanisms aimed at them (mixture, channels, anchor re-leveling) each
  cost more on their look-alike neighbours than they repaid.

## Verification (all run on the final tree)

- dev/final_check.py (harness, final config): ALL 0.3183, rolling 0.2404,
  GTA-like 0.1576; baselines 0.9297 / 0.3568 / 0.3006.
- dev/fidelity.py: ported main.py on synthesized real-format LOO cases
  reproduces those numbers exactly, per case as well as in aggregate.
- Kit inputs p00-p03 through main.py: gate does not fire; outputs valid
  (23 hours x 5 quantiles, monotone, within (0, 1e9], <= 1.8 KB per file),
  ~0.22 s per case (limit 8 s); two full runs byte-identical.
- Imports are stdlib only (json, math, os, re, datetime, pathlib). No
  network, no randomness, no state. Working tree only — nothing committed.
