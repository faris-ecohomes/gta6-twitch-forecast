# Tuning log — push ALL pseudo-LOO below 0.30

Baseline (LOCKED = current main.py), reproduced with dev/final_check.py:
ALL 0.4542 | rolling/mixed 0.2404 (guardrail ≤ ~0.25) | GTA-like 0.1576 (guardrail ≤ ~0.17)
House baseline in harness: ALL 0.9297.

## Diagnosis (dev/diag1.py, dev/diag2.py)
- 75% of loss mass sits in cases whose peak/H1 ≥ 3; 58% in peak/H1 ≥ 20.
- Worst cases are "steppers": hour 1 is a pre-unlock trickle, the curve steps
  up +4..+8 log at some hour 3..17, timing varies (Wukong h~3, ARC h~10,
  BG3 h~14, Silksong h~15, Marathon h~17).
- For trickle targets the similarity weights collapse (ESS ≈ 1.1): Marathon
  puts 93% on ARC Raiders (steps early) -> massive midday overshoot; ARC puts
  89% on Marathon (steps late) -> massive undershoot. The scale kernel on H1
  is meaningless when H1 is a trickle, and step timing is not predictable
  from the available features.
- Observable separating steppers: H1/pre_max (Marathon 0.004, ARC 0.007,
  Silksong 0.014, KCD2 0.03, Battlefield 0.12, HD2 0.17, BG3 0.20) vs
  anchored cases mostly > 0.3. Stepper plateau log-ratios cluster +4.5..+7.6.
- Secondary pattern: "risers" (RE Requiem +2.5 plateau, loss 1.037, rolling!)
  — anchored but builds all day; current centre rises too slowly.

## Experiments
| # | change | ALL | rolling | GTA-like | verdict |
|---|--------|-----|---------|----------|---------|
| E1 | empirical quantiles instead of normal fit | 0.4783 | 0.2498 | 0.1685 | reject |
| E2 | weight tempering 0.5 (normal) | 0.4222 | 0.2485 | 0.1668 | helps ALL via trickle cases only; hurts anchored bulk when gate present — reject |
| E3/E4 | temper/uniform-blend + empirical | 0.4498 / 0.4558 | — | — | reject |
| E5 | soft two-regime mixture (NW pi over pre-stat, stepper empirical in ratio space) | 0.5456 | 0.2752 | 0.1998 | reject: pi leakage taxes every anchored case ~+0.05; dilution breaks good clones (HD2 +1.25, Wukong +0.82) |
| E7 | HARD GATE (H1<=6000 and H1/pre<=0.6) -> stepper pool in LEVEL space, factor weights | 0.3835 | 0.2404 | 0.1576 | KEEP: gate never fires for rolling/GTA subsets |
| E7c | gate + stepper level_temper 0.3 | 0.3793 | 0.2404 | 0.1576 | keep |
| E9 | gamma/gamma_late widening | ~0.4500 (pre-gate) | — | 0.1665+ | reject |
| E10 | Cornish-Fisher skew quantiles | 0.4520 (pre-gate) | 0.2403 | 0.1597 | negligible — reject |
| R9 | gated path v2: TRANSPLANT (pre-step = target H1 x comp ratio; post-step = comp level) + SHIFT comps to target's stated unlock hour (ISO stamp in notes, same date as day_start) | 0.3362 | 0.2404 | 0.1576 | KEEP: Wukong 1.87->0.38, BG3 0.97->0.48 |
| R10 | gate_thresh sweep (pool plateau cut) | 0.3356–0.3452 | = | = | ln4 best; reject changes |
| R10b | anchored coordinate sweep (scale/pre/ea/weak/pc/coop/smooth/vpc/recency/roll_mixed/min_hours) | 0.3349–0.3663 | — | — | all noise or worse; vpc clearly bad; anchored side saturated |
| R11 | shift cap 3/4/6 | 0.3388/0.3363/0.3329 | = | = | reject (uncapped best at the time) |
| R11b | tau_offset -1 / -2 (audience hits half-plateau before the stated unlock hour) | 0.3237 / 0.3183 | = | = | KEEP -2 |
| R11c | blend shifted+unshifted gated forecasts | 0.3296–0.3306 | = | = | reject vs offset |
| R12 | around offset -2: blend/cap/gate_thresh/level_gamma/level_temper/gate variants | 0.3177–0.3588 | = | = | offset -3 = 0.3177 (noise-equal); gate_a 0.5 or gate_h1 4000 much worse (drops Wukong from gate) |
| R13 | scale-mixture heavy tails (mixn) | 0.3237–0.3379 | 0.2422+ | 0.1813+ | reject: taxes the well-calibrated regime |
| R14 | trimmed centre (trimnormal) | 0.3394 | 0.2938 | 0.1672 | reject |
| R14b | unknown-target unlock overrides (unk_global 0.15, unk_mixed 0.35) | 0.3157–0.3172 | = | = | noise-level; not ported |
| R15 | qmethod normalm / blend / robust on final base | 0.3169 / 0.3147 / 0.3235 | 0.2480/0.2416/0.2510 | 0.1722/0.1609/0.1717 | blend gains 0.0036 ALL but spends GTA headroom (+0.0033) — not ported (do not trade the GTA regime for the average) |
| R16 | stepper-curve smoothing (half-window 1) | 0.3179 | = | = | noise-level; not ported |
| R18 | hard regime separation (steppers banned from anchored pool) | 0.3381 | 0.2760 | 0.1857 | reject: rolling/GTA targets NEED riser/stepper comps in their pools |

## Final configuration (ported to main.py)
LOCKED base unchanged + gate (H1 <= 6000 and H1/pre_max <= 0.6) ->
stepper transplant forecast: pool = comps with log(peak/H1) >= ln 4 and
>= 18 covered hours; weights = regime factors (unlock/EA/weak/PC/mode)
tempered ^0.3; each comp's step hour tau_c = first hour its log-ratio
reaches half its plateau; target step hour tau_t from an ISO unlock
timestamp in the notes on the day_start date, minus 2h, clamped [1, 24]
(no timestamp -> no shift); sample at hour h reads the comp's timeline at
j = clamp(h - (tau_t - tau_c)): before its step, target H1 x comp ratio;
from its step, the comp's absolute level; quantiles = weighted empirical.

FINAL (harness): ALL 0.3183 | rolling 0.2404 | GTA-like 0.1576.
Goal < 0.30 NOT reached; plateaued — see tuning-report.md.
