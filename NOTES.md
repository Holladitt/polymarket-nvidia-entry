# Polymarket NVIDIA CEO forecast — entry notes

## Method (`main.py`, Python 3.13 stdlib only, deterministic, no network)

Forecasts each market's Yes price at every minute of the next 240 minutes as
five quantiles (5/25/50/75/95%), from the case's own 1-minute price grid.

- **Median**: last price, pulled toward its board-sum-normalised share
  (`x / sum(x)`; the 24 Yes prices sum to ~1, and the 240-min move regresses
  on the sum gap with slope ~0.55), with the board-sum adjustment shared
  across markets in proportion to `x_i * sigma_i` (liquid markets absorb
  more of the gap; the old `x_i`-only sharing scored 0.2517 vs 0.2512 for
  this one, and is better on the calm cases too), plus asymmetric
  give-back of the last 60 minutes' run-up: sharp rises revert (~2/3
  within 15 min, ~3/4 within an hour), sharp falls almost never bounce
  back, so only rises are given back. Momentum extrapolation and pull
  toward a slow EMA were both tested and hurt, so neither is used.
- **Spread**: per-market realised volatility as a 0.65/0.35 blend of a fast
  (15-min half-life) and a slow (4-h half-life) EWMA of squared 1-min
  changes (winsorised at ±0.06), with a price-level floor
  (`0.0002 + 0.005·x`) and a 0.012 cap. The spread grows with horizon but
  saturates hard (`σ(h) = σ₁·√h/√(1+h/12)` — the SD of h-step changes grows
  like h^0.33, not √h). Outer quantiles widened ×1.35, inner ×0.8 for
  fat tails. A direct empirical h-step-quantile fan was tried and was much
  worse (0.313): the move distribution is a point mass at zero with rare
  jumps, so raw empirical quantiles collapse.
- All values clipped to [0, 1], rows non-decreasing, 6-decimal rounding.
  A market with no prices is forecast flat at 0.5 rather than crashing
  the run (one bad market must never invalidate the whole case).

Parameters were tuned by coordinate descent on the practice cases
(3 rounds; gains saturated at ~0.001/round by the end). Deliberately
robust rather than practice-maximal: the final is graded on 48 h of
unseen prices in a mature market, and the practice cases are dominated
by the Nov 10–11 launch regime.

## Local practice results (rebuilt answers, see below)

Current version (**v6**, round 6, practice **0.222196 — top-10 practice
zone, ~rank 10 on the 01:18 WIB board**), verified by re-running `main.py`
on the kit inputs and scoring with the local scorer; two runs byte-identical
(deterministic); ~100 ms/case; largest output 288 KB (cap 1 MiB). Calm cases
p04/p05 mean **0.127977** (best of all versions; guardrail 0.1340):

| case | checkpoint (UTC) | loss | median_error | coverage_90 | run_ms |
|------|------------------|------|--------------|-------------|--------|
| p00 | 2026-11-12 06:00 | 0.276664 | 0.7837 | 0.9594 | ~100 |
| p01 | 2026-11-12 10:00 | 0.287396 | 0.7158 | 0.9311 | ~100 |
| p02 | 2026-11-12 14:00 | 0.309507 | 0.9744 | 0.8864 | ~100 |
| p03 | 2026-11-12 18:00 | 0.247844 | 0.7296 | 0.9438 | ~100 |
| p04 | 2026-11-12 22:00 | 0.158944 | 0.4324 | 0.8594 | ~100 |
| p05 | 2026-11-13 02:00 | 0.097010 | 0.2792 | 0.9326 | ~100 |
| **mean** | | **0.222196** | **0.6317** | **0.9178** | **~100** |

v4 changes vs v3 (see "Round 4" below for the full account):
- **Regime-scaled pull**: pull strength × (1 + 1.7·(V−Vmed)/Vmed), clipped
  [0.3, 2.5], where V = the board's mean EWMA sigma at the checkpoint and
  Vmed = 0.002696 (practice median). Launch regimes pull harder, calm
  regimes pull softer.
- **Regime-scaled fan**: sigma × (V/Vmed)^0.5, clipped [0.5, 2.0] — the fan
  widens in volatile regimes and narrows in calm ones.
- k_down 1.4 → 1.61, k_up 0.5 → 0.425, cap 0.012 → 0.0102,
  pull_tau 120 → 111, outer-tail horizon widening ×(1 + 0.1·h/240).

Previous version (v3, asymmetric sum-pull + gap trend + pull tilt +
deadband/fan compression) scored **0.244106** (p00 0.390886, p01 0.295802,
p02 0.319006, p03 0.249904, p04 0.168442, p05 0.097792; median_error
0.6893, coverage_90 0.8933; calm p04/p05 mean 0.133117). The v4 changes
gain −0.007568 on the mean and −0.002720 on the calm mean. v2 scored
0.251169; v1 scored 0.251652.

Reference points (practice board): house persistence baseline **0.363589**,
#1 **0.213**, #10 **0.237**, ~rank 100 **0.243**, rank 1000 **0.275**.
This entry: **0.244106** (~rank 120–150 on practice; top 10 NOT
reached — gap 0.0071 remains).
Its calm-regime cases (p04/p05: 0.168/0.098) are far stronger than its
launch-regime cases (p00: 0.391); the final window (Nov 13–15, mature
market) resembles p04/p05 more than p00, so the final rank may beat the
practice rank.

Oracle check: with a perfect median and this spread the loss would be
0.075, so the remaining loss is dominated by median error (unpredictable
moves), not by the spread. Per-τ decomposition of v3: τ=0.5 contributes
28%, τ=0.75 28%, τ=0.25 22%, τ=0.95 14%, τ=0.05 8% — the middle
quantiles (all median-driven) dominate; the tails are relatively
well-calibrated, so no spread fix can close the remaining gap.

## Iteration round 2 (13 Nov 2026, ~22:35–23:05 WIB)

Gemini was consulted FIRST as advisor (Adit's order) via the registered
`custom.gemini` connector (Interactions API, gemini-4-hydrogen). Four
calls failed before one succeeded: two 120 s read timeouts on long
analytical prompts (hydrogen thinks long), one 503 on gemini-3.8-flash,
one 429 (rate limit). The successful call (short prompt, <400 words)
confirmed the EDA conclusions and said plainly there is no single
missing median formula worth 0.005+; the gap to the top 10 likely lives
in conditional quantile dispersion and in non-price microstructure
features, neither of which this case's data (prices only) supports.
Gemini's two concrete suggestions were both tested and rejected (below).
No Gemini output was pasted into `main.py`; all ideas were implemented
and verified locally by hand.

EDA (script `/tmp/poly_multi.py`, harness `/tmp/poly_var.py`): the board
sum mean-reverts toward ~1.0 (checkpoint sums 0.81–1.09); Ian Buck's
15-min changes correlate ~−0.15 with every other market (the big market
vs the rest); pooled regression of forward 240-min moves on sum gap +
own 15-min move + rest-of-board 15-min move gives R² = 0.045, the gap
dominating (R² = 0.024 alone).

Tried in this round, one change at a time, kept only on mean improvement
with no calm-case damage:

| change | mean | p04/p05 | verdict |
|---|---|---|---|
| liquidity-weighted pull `w∝x·σ` (a=1,b=1) | 0.251169 | 0.1320 | **KEPT** (only keeper) |
| `w∝x^0.5`, `w∝x^0.5·σ^0.5`, `w∝x^0.5·σ`, `w∝x^1.5…` | 0.2517–0.2560 | 0.1315–0.1405 | rejected (mean worse or wash) |
| rest-of-board rotation term k=0.1–0.3 | 0.362–0.765 | — | rejected (catastrophic; pooled-OLS slope is tail leverage, pinball punishes it) |
| stronger pull (pull_max 1.1/1.3) | 0.2520–0.2535 | 0.133–0.141 | rejected |
| spread shape (mid 0.6–0.9, tail 1.15–1.45) | 0.2513–0.2530 | 0.130–0.134 | rejected (noise) |
| sum anchor = 24 h EWMA of the sum | 2.22–2.36 | — | rejected (catastrophic; launch-regime sums contaminate the anchor) |
| give-back window 15/30/120 min | 0.2514–0.2550 | 0.132–0.138 | rejected (60 min stays) |
| pull tau 60/240 | 0.2525–0.2531 | 0.132–0.140 | rejected |
| per-market pull strength ∝ σ^±0.5 | 0.2521–0.2881 | 0.135–0.146 | rejected |
| boundary-skewed spread (Gemini) | 0.2533–0.2606 | 0.132–0.133 | rejected |
| regime-gated pull (Gemini) | 0.2515–0.2526 | 0.132–0.133 | rejected |

Conclusion: the entry is at a local optimum for this model family. The
remaining gap to the top 10 (0.014) is unpredictable jump risk, not a
missing heuristic: with a perfect median the loss would be 0.075, but
that median is ex-post knowledge of whether and how far jumps occurred.
Next step if there were one more round: a proper cross-market VAR on
quantile (L1) loss rather than pooled OLS — or accept the entry as is,
since the final's calm regime is where it is strongest.

## Iteration round 3 (13 Nov 2026, ~22:49–01:15 WIB; Adit gave FULL
## authority to keep searching for top 10, no process updates wanted)

Gemini consulted twice more as advisor (short prompts only; one 503
with one retry, then a success). No Gemini output was pasted into
`main.py`; everything was implemented and verified locally by hand.
EDA scripts: `/tmp/poly_r2_eda.py`, `/tmp/poly_r2_eda2.py`,
`/tmp/poly_r2_var.py`, `/tmp/poly_knn.py`. Guardrail throughout:
p04/p05 mean must stay ≤ 0.1340 (final resembles the calm cases).

KEPT (all in v3, cumulative 0.251169 → 0.244106):
- Asymmetric sum-pull: k_up = 0.5 (gap > 0, sum < 1), k_down = 1.4
  (gap < 0, sum > 1). Checkpoint gap-closure ratios support it: down-gaps
  close ~0.77–0.94 in 240 min, the p02 up-gap only ~0.46.
- Gap-trend extrapolation: gap_used = gap + 0.2·(gap − gap_60min_ago)
  (c_trend = −0.2). The gap has MOMENTUM over 60-min horizons — reversing
  the trend instead costs +0.015.
- Pull tilt κ = 0.15: pull displacement × (1 − κ·z), lower tail moves
  more with the pull (gap closure arrives as downward jumps).
- Give-back softened gb_up 0.45 → 0.35 (history OLS slope is only
  ~0.17, robust median 0.00; 0.55 is worse).
- Deadband eps = 0.001 + fan compression ×0.85 on deadbanded rows
  (57% of 240-min moves are exactly zero; a dormant market's fan is
  narrower). Alone the deadband gains −0.0006; compression adds −0.0007.

REJECTED (tested, one change at a time, all scored on 6 cases):
- Activity-weighted/gated pull (all variants worse; gating dormant
  markets' pull hurts p00 badly, 0.431).
- Spike give-back after big 1-min jumps, any strength 0.2–1.0
  (0.254–0.288): checkpoint spikes are genuine NEWS (Kress becoming
  interim CEO), not rumor spikes — the history's full-reversal pattern
  does not transfer. Same mirage kills convex give-back (0.248–0.260)
  and the 9-cell/CART median table (τ=0.5@240 loses to v3 in 5/6 cases).
- Log-space quantile fan (0.292): explodes for near-zero prices
  (σ₁/x up to 1.1 → q95 clipped at 1.0).
- Empirical-Gaussian blend fan, any weight (0.266–0.301): history
  quantiles carry launch-regime jumps into calm cases.
- k-NN analog median, K = 15/25/50 (0.317–0.395 pure; best blend 0.268):
  analogs are noise; larger K just averages toward "predict x".
- Hurdle mixture (EDA-killed): directional probabilities never exceed
  0.5 in any gap/momentum bucket (max P(dn) 0.47) — the hurdle ≈ the
  deadband, which is already in.
- Skewness offset (EDA-killed): conditional median forward move is
  exactly 0.000 in EVERY price bucket at h = 60 and 240.
- L1 cross-market / Buck-lead (EDA-killed): median F60 is flat 0.000
  in every rest-of-board decile and every Buck-move decile.
- Leader shielding (pull weights x^γ, γ = 0.5–0.85): 0.2474–0.2483,
  noise at best; γ = 0.5 worse.
- Gap threshold (0.01–0.03), fast give-back on r15 (0.15–0.5), smoothed
  11-min-median share target, fall momentum gb_dn < 0, pull-weight
  variants (slow-σ, x-only, √σ, capped-σ): all worse or noise.
- Spread re-tunes (scale 0.85–1.15, tail 1.2–1.5, mid 0.7–0.9,
  h_sat 8/20, fast_w 0.5/0.8): flat — the spread is not the bottleneck.
- Per-case adaptive slopes from history: impossible — all 6 cases share
  one history (gap-closure OLS +0.13 and give-back OLS −0.17 identical
  in every case).
- Random search, 120 combos over (k_up, k_down, c_trend, κ, gb_up,
  gb_tau, pull_tau, deadband) with the calm-case guardrail: NOTHING beat
  the coordinate-descent best. The family is saturated at ~0.244–0.245.

Conclusion: the price-only median saturates at ~0.244 on these 6 cases.
The remaining 0.0071 to the top 10 is concentrated in leader markets
making news moves at the launch-regime checkpoints (p00 0.391, p02
0.319) — moves that are unpredictable from price history by every
method tried (parametric, k-NN, tree, hurdle, empirical). The entry is
kept as v3: it is the best verified version, it respects the calm-case
guardrail, and its final-regime (calm) performance is its strongest
suit. If the search continues, the only untried directions are (a) a
finer per-τ spread calibration from binned empirical widths (expected
gain ≤ 0.001), and (b) accepting a practice-mean / final-regime
trade-off by pushing k_down/tilt harder at the cost of p04/p05.

## Iteration round 3 (STRETCH TERAKHIR, 13 Nov 2026, ~23:07–23:14 WIB)

Adit gave full authority and ordered: keep going with Gemini until top 10.
Result: **top 10 NOT reached. Entry kept as v3, unchanged (0.244106).**
6 candidate families tested (16+ configs), all one change at a time with the
calm-case guardrail (p04/p05 mean <= 0.1340; base 0.1331). Gemini consulted
3 times total this round (short prompts, gemini-4-hydrogen, all succeeded;
no output pasted into main.py).

EDA kills first (script `/tmp/poly_r3_eda.py`, `/tmp/poly_r3_eda_b.py`):
- Median forward move is 0.000 at EVERY horizon 1..240 in EVERY regime
  (launch/mid/calm) — the exponential pull ramp's shape is irrelevant;
  there is no drift to time.
- Residual-vs-pull slope flips sign between h=60 (+0.29) and h=240
  (-0.21), corr < 0.17, biggest residuals are single news jumps (p00
  Kress -0.070, p02 Kress -0.117) — no nonlinear pull in |gap|.
- Checkpoint-indexed spread is dead: per-market EWMA sigma already tracks
  regime (launch sigma1 0.0027-0.0036 vs calm 0.0013-0.0020).
- Jump stats: |1-min change| >= 0.02 occurs ~0.009/min (median), median
  jump size 0.08, mean 0.158 — but jumps REVERT, they do not accumulate
  (h-step SD grows like h^0.33, not sqrt(h)).

| change | mean | p04/p05 | verdict |
|---|---|---|---|
| horizon-linear tail widening frac 0.1/0.15/0.2/0.3 | 0.24353/0.24341/**0.24337**/0.24353 | 0.13333/0.13346/0.13362/0.13398 | **REJECTED on final-regime grounds** (see below) |
| horizon-saturating tail widening | 0.24419–0.24694 | 0.13489–0.13789 | rejected (worse + guardrail breach) |
| jump-diffusion mixture fan (Gemini's idea; core + Poisson jump component, CDF inversion) | 0.256–0.507 (5 configs) | 0.140–0.388 | rejected, CATASTROPHIC: mis-specified — assumes jumps accumulate; even J at 10% of measured median jump size still loses (0.256) |
| MAD-sigma core (robust to jumps) | 0.30275 | 0.16443 | rejected, CATASTROPHIC: 57% of 1-min moves are exactly zero, so MAD = 0 and the fan collapses to the floor |
| coarse-horizon sigma H=15/30/60 (Gemini's last idea) | 0.36867/0.37220/0.37336 | 0.287–0.299 | rejected, CATASTROPHIC: RMS of H-min changes counts reverting jumps at face value; sigma hits the 0.012 cap in p00 |
| trend_win 30/120, slow_hl 120/480 | 0.24448–0.24729 | 0.13250–0.13522 | rejected |
| kappa fading with horizon | NOT TESTED — killed by Gemini + EDA before building (overfit risk on 48-57 points/regime) | — | — |

The tail-widening trade-off, documented for the submit decision: frac=0.2
gains -0.0007 on the practice mean (p00 -0.0028, p02 -0.0017) but worsens
BOTH calm cases (p04 +0.0002, p05 +0.0008). The gain is launch-regime,
the cost is calm-regime, and the final is graded on unseen CALM prices —
so it was rejected despite passing the numeric guardrail (0.13362 <=
0.1340). One-line change if ever wanted: outer-quantile width
`tail_wide * (1 + 0.2 * h / 240)`.

Gemini's final verdict (3rd call): the price-only ceiling is ~0.244;
the 0.007 practice gap to 0.237 is launch/news-regime risk (or external
signals) — chasing it overfits the wrong regime and sabotages the
calm-regime final. Its last idea (coarse-horizon sigma) was tested and
failed as above. Conclusion: saturation is confirmed across 3 rounds,
~30 rejected variants total. The entry is v3, the best verified version,
and its final-regime (calm) performance is its strongest suit.

## Iteration round 4 (TERAKHIR, RESOURCE MAKSIMAL, 13 Nov 2026, ~23:16–01:05 WIB)

Adit ordered one last maximal-resources round (all compute + Gemini).
Result: **top-10 bar REACHED on practice: v4 mean 0.236538 < 0.237.**
Calm p04/p05 mean 0.130397 (best of all versions; guardrail 0.1340).
Entry updated to v4, verified by re-running `main.py` + local scorer
(two runs byte-identical; ~90 ms/case). NO submit, NO repo created.

**The breakthrough — regime scaling (the missing state-dependence).**
Gemini call 3 (leader/loss-attribution) diagnosed it: static leader tweaks
help launch cases but wreck calm ones — "a true structural leader edge
would not systematically reverse sign between calm and volatile cases";
the fix is "1–2 global parameters tying fan/pull directly to realized
regime volatility". Board mean EWMA sigma V at the checkpoint measures the
regime: p00 0.003635, p02 0.003494 (launch) vs p04 0.001963, p05 0.001309
(calm); practice median Vmed = 0.002696. Two orthogonal knobs:
- regime_pull (linear): pull × (1 + rp·(V−Vmed)/Vmed), clip [0.3, 2.5].
  rp=0.8 alone: 0.241448 (−0.00266), calm 0.132030, LOCO 6/6 on 5-case
  means; rp=1.2: 0.240662 but LOCO 5/6. Log-form (V/Vmed)^a is smoother
  but weaker at matched strength (a=1.0: 0.241030).
- regime_fan (power): sigma × (V/Vmed)^qf, clip [0.5, 2.0]. qf=0.5 on top
  of rp=0.8: 0.239875 (−0.00157 more), calm 0.130394. Joint grid best
  rp=1.2/qf=0.5: 0.239355, calm 0.130585; qf=0.5 is the sweet spot at
  every rp (0.7 and 1.0 both worse).
- Coordinate descent from the joint best (strict filter: mean improves,
  calm ≤ 0.1340, no case worsens > +0.0015 vs v3): k_down 1.4→1.61,
  k_up 0.5→0.425, cap 0.012→0.0102, pull_tau 120→111, tail_lin 0.1,
  regime_pull → 1.7 → **v4 = 0.236538, calm 0.130397**.
- An aggressive descent (loose filter ≤ +0.005) reached 0.236021 but was
  REJECTED as the final point: p01 worsens +0.0042 and nested LOCO is
  3 wins / 2 losses / 1 flat — the extra gain is p00-only. v4 keeps the
  clean profile (worst case +0.0013) at nearly the same mean.

**Validation (v4):** nested LOCO on the (rp, qf, k_down) family —
train-selected params still improve held-out p00 (−0.017) and p04
(−0.003); the aggressive corner fails held-out p01/p02, which is why
v4 stays at the constrained point. Permutation placebo (V shuffled
across cases, rp=0.8): true assignment 0.241448 vs shuffled mean
0.242878 over 5 trials — the V-matching premium is real but modest
(~−0.0014); about half the regime gain is the average pull-level shift.
β-check (Gemini call 2's falsifiable test): regress realized Δx on
w·ΔS through the origin — β = 0.64 (h=60), 0.87 (h=120), 1.32 (h=240);
x(1−x)σ weights give nearly identical β (0.65/1.34) — weight choice is
NOT the issue, horizon shape is.

**Gemini calls this round (4, gemini-4-hydrogen, short prompts):**
1. Per-τ quantile regression — proposed tails-move-when-median-flat +
   "hidden leak" (re-anchor median at last price, asymmetry into tails).
   REFUTED by the falsifiable check: pull=0 → 0.262554, gb=0 → 0.248742,
   pull=0+gb=0 → 0.272728 (median adjustments earn ~0.029 — they stay).
2. Board-sum AR — proposed saturating-exponential S forecast + x(1−x)σ
   distribution weights + β=1.0 falsifiable check. Weights REJECTED
   (var_w 0.5 → 0.244515, 1.0 → 0.245079); S*≠1 REJECTED (0.99 →
   0.244066 but calm 0.134921 breaches; 0.97 → 0.245611).
3. Leader/loss-attribution — the diagnosis that produced regime scaling
   (see above). Name-keyed leader tuning = overfitting on 6 cases.
4. Regime scaling (after the breakthrough) — recommends concave power /
   floored-log form over linear (linear can clip at the tails — noted:
   p05's rscale does hit the 0.3 clip at rp=1.7) and regime-scaled fan
   as the second parameter (tested and KEPT, qf=0.5); nested-LOCO and
   placebo validations per its suggestion.

**Rejected this round:** ensemble v3 + empirical fan (w=0.1 → 0.245722,
w=0.5 → 0.260890); horizon-varying weight concentration wconc_tau
(30→0.244386 … 240→0.251598); leader fan/pull standalone (fan 1.3 →
0.244875, pull 1.3 → 0.244243 but p04 +0.0071); gap_sig alone up to
0.35 → 0.243909 (kept only inside the joint descent at 0.2, then
dropped by the descent itself — final v4 has gap_sig = 0); bskew
(0.3 → 0.245113); var_w, s_star (above).

**Search volume:** ~6,600 evaluations total — local random search
2×2000 (seeds 42, 123: 0/4000 beat v3; best 0.245922) + Simular Box
independent random search 2000 (seed 777: 3/2000 beat v3, best
0.240465, 0 passing all filters — box answers rebuilt from CLOB on
the box, reconstruction maxdiff 0.0; numpy 2.2.6 wheel manually
unzipped, no pip on the box) + grids/coordinate descent/LOCO ~600.
The box search confirms v4 was found by structured descent, not luck.

**Caveat (honest):** the v4 gain is still p00-heavy (p00 −0.0422 of the
−0.0076 mean gain; p04 −0.0049, p02 −0.0025, p05/p03 ~−0.0005,
p01 +0.0013). The final is graded on 12 unseen CALM cases, not on
practice rank — v4's calm mean (0.130397) is its best number and the
reason it was chosen over the aggressive 0.236021 point. Practice
top-10 (0.236538 < 0.237) is a milestone, not the prize.

## How the local grade was done

The kit publishes no reference answers (`grade-local` refuses:
"its scorer and reference data are not published in the kit, so it is
graded on the server only"). Answers were rebuilt from Polymarket's
public CLOB history exactly as the kit's NOTICE.txt prescribes
(`GET https://clob.polymarket.com/prices-history?market=<yes_token>
&startTs=&endTs=&fidelity=1`, minute = last point with t <= minute,
forward-filled). Validation: the same fetch reproduces every case's own
input grid EXACTLY (max diff 0.0 across all 6 cases, all markets), and
scoring the kit's starter baseline through the local scorer reproduces
the house practice loss EXACTLY: **0.363589** (median_error 0.7674 vs
house 0.767503, coverage_90 0.9496 vs 0.949642).

Commands (from the kit dir):

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out \
  python3 /path/to/main.py
python3 /tmp/poly_score.py out
```

Per-case runs (one `.in` file alone in the input dir) take 80–103 ms
(cap 8000 ms); two full runs are byte-identical (deterministic);
largest output file 296 KB (cap 1 MiB). Dev artefacts (CLOB cache,
rebuilt answers, tuned params) live in `dev/`.

## Round 5 (14 Nov ~00:05-01:10 WIB) — v5: 0.236538 -> 0.222954 (target <=0.229 BEATEN)
Adit ordered (13 Nov 23:59 + 00:14 + 00:17 WIB): MUST reach top 10; use ALL
resources + Gemini; force resources to the max. Leaderboard fresh 13 Nov
23:59 WIB: 2,433 entries, rank 10 = 0.231, v4 (0.236538) ~rank 56 — the
"top 10" claim from the 22:21 snapshot was stale (corrected in MEMORY.md).
v4 was already SUBMITTED 13 Nov ~23:44 WIB (submission 01a1d5cb-...,
platform loss 0.237, rank 67/2,479) — v5 is a replacement candidate,
submit only on Adit's order. Work done ONLY in dev/main_v5_candidate.py;
main.py untouched (md5 67dfb2bd6f16f816e752dfca4b8ab772).

New mechanisms (each tested one at a time, verified locally by hand):
- REGIME-GATED TWO-TIMESCALE PULL: pull(h) gains a fast component
  (tau ~15 min) gated by regime, w_f_eff = 1.0*clip(2.7*(rscale-1),0,1);
  calm cases keep v4's slow pull exactly. EDA: true pull response is fast
  early (OLS slope 0.27 at h<=15 vs v4's 0.06). Gain ~-0.0027.
- REGIME-GATED LINEAR SHARE TARGET (Gemini #1 idea 3): in volatile regimes
  the pull converges to the pure board-sum share (adj = x/sum - x) instead
  of the x*sigma-weighted gap share; blended by regime g =
  clip(1.93*(rscale-1),0,1). p00 improves 0.3486 -> 0.2766. Gain ~-0.0047.
- EMPIRICAL-Z FAN BLEND (0.56): Gaussian z blended toward pooled empirical
  quantiles of (y-med)/sigma(h) by horizon bucket (h=8/38/90/180;
  q25 -0.07..-0.49 vs Gaussian -0.674, q75 0.00..+0.31 vs +0.674,
  q95 grows 1.1 -> 3.0 with h). Gain ~-0.0046 in ablation.
- STALENESS-WEIGHTED pull allocation (Gemini #1 idea 1): raw weights x
  stale^0.70, stale = zero-move fraction in last 240 min. Marginal (+0.0002
  in ablation, kept — never hurts materially).
- Joint random search (3 seeds, ~6,500 evals) + coordinate descent polish.
  Final params in dev/best_params_v5.json. Notables from descent: kappa
  0.15 -> 0.0026 (pull tilt nearly gone), tail_wide 1.35 -> 1.07,
  mid_wide 0.8 -> 0.99, z_blend -> 0.56, pull_tau 111 -> 161.

v5 per case: p00 0.276608, p01 0.291221, p02 0.309624, p03 0.248005,
p04 0.159240, p05 0.097526; mean 0.222954; calm p04/p05 0.128383
(guardrail <=0.1340 PASSED, better than v4's 0.130397). Wins vs v4: 5/6
cases (p05 +0.000253, negligible). Verified via official scorer path
(poly_score2.py): mean 0.222954, deterministic (byte-identical x2 runs),
~0.1 s/case. Validation: gate plateau (target_gate_k 1.5-3.0 all
0.2231-0.2238; fast_gate_k 1.5-2.5 all 0.2230-0.2238); reverse-gate
placebo 0.239869 (worse than v4 — regime signal real); z-table LOCO
+/-0.001 per case; per-fold ablations: fast pull wins 6/6 folds,
empirical-z 6/6, linear target 5/6 (value concentrated in p00, never
hurts other cases), staleness 5/6 (marginal).

REJECTED in round 5 (do not retry without new reason): vol-trend fan
scaling (catastrophic), v_mode median/recent, regime-scaled give-back,
two-timescale give-back (helps calm only), z_lo/z_hi asymmetry, per-market
tick deadband (marginal), k_up_gap_a, adj_db soft-thresholded pull,
deficit-triggered logit target, logit-space fan (catastrophic 0.267),
Fisher-information target (worse than linear), Roll bounce decomposition
(catastrophic 0.237), board conservation-ratio filter (not implemented —
low prior after 2/3 of that Gemini call failed). Gemini calls: 3 total
(#1 gave staleness + linear target; #2 all 3 failed; #3 all 3 failed).
Simular Box independent search (round-5 child) still running at 01:10 WIB;
parent's parallel 5B track (dev/main_v5b_candidate.py) also running —
compare before any replacement submit. Irreducible noise: news jumps in
tiny markets (e.g. Jonah Alben 0.004 -> 0.0835 in p01) cap the practice
score; p01/p02 remain the worst cases.

Box independent search (child 77acd72d, finished 14 Nov ~01:47 WIB):
best 0.227994, calm 0.130172 — ALSO beats target <=0.229 and v4, but
WORSE than local v5 (0.222954) by +0.00504, so NOT the submit candidate.
Per-case: p00 0.307629, p01 0.292301, p02 0.316166, p03 0.240397,
p04 0.163285, p05 0.097059. LOCO (refit 5 cases, fine CD): item-weighted
0.229229 vs in-sample 0.227994. New mechanism: horizon-dependent pull
asymmetry (kasym_up -0.590, kasym_dn -0.160; asymmetry fades to symmetric
by h=240) — real but does not stack past local v5. Files on the Box only:
 /workspace/polywork/r5mine/r5_best_entry.py, r5_best4.json, R5_SUMMARY.md.
Note: the Box harness replica reads v4 as 0.236985 (true 0.236538), so its
scores carry ~+0.0004 replica drift. The "0.226575" the Box child flagged
in /tmp/r5_loco.py is an INTERMEDIATE snapshot of this same local v5 line
(header claim), superseded by the final 0.222954 — no competing line.
5B track current best (best_params_v5b.json, 17:45 WIB): 0.230318, calm
0.128398 — does NOT beat target. RECOMMENDATION: submit v5 (0.222954).

## Round 5B (parallel lane, 14 Nov ~00:17-02:00 WIB; target <=0.229)
Angle (complementary to round 5, NOT a duplicate): exploit the v4
neighborhood + regime-V definition variants + regime-form variants, fresh
seeds (2024/555/999/31337, then 4242/7777/8888/1111, then 2222/3333/4444/5555).
Bulk compute on Simular Box (10k evals/phase, ~2-2.5 min each); local VM only
for EDA/verification/Gemini. Harness: /tmp/poly_r5b_var.py (numpy replica of
main.py + round-5 knobs + vdef/form/hinge); box copy /workspace/polywork/
poly_r5b_var.py. Selection (clean win vs v4): mean < 0.236538 AND calm
p04/p05 <= 0.1304 AND worst per-case worsening <= +0.002 AND >=2 cases improve
>= 0.001.

KEY BUG FOUND + FIXED (round-4/5 harnesses): they defaulted tail_lin to 0,
but v4's real tail_lin=0.1 lives in best_params.json "extra", not "params"
-- so they scored v4 as 0.236985 instead of the true stdlib 0.236538. Fixed
by putting tail_lin: 0.1 in X4; the 5B harness reproduces v3 EXACTLY
(0.244106) and v4 EXACTLY (0.236538, all per-case exact). Also: box
score_params returns numpy floats, so json.dump of search results raised
TypeError (np.bool_ not serializable) and killed the first Phase-B run
mid-dump -- fixed with bool() cast + default=float. Results are deterministic
across re-runs (identical best/clean counts).

Phase A (vdef x form at v4 params, vmed recentered per vdef): best slow/log
0.235648 (calm 0.130134); slow/lin 0.235943; mean/log 0.236246; median/log
0.236664 (best calm 0.130107); fast/wmean/max/v60/board all worse
(0.2409-0.2450). VMED_DEF at v4 P: mean 0.002696, median 0.001715, fast
0.001531, slow 0.003264, wmean 0.004857, max 0.009333, v60 0.001669,
board 0.03727. V per case (mean): [0.003544, 0.002699, 0.003209, 0.002693,
0.001945, 0.001309]. r5best rescored in the CORRECTED oracle: tail_lin 0.0
-> 0.231732; 0.1 -> 0.231209; 0.2 -> 0.231284. r5best + slow/log + tl=0.1 ->
0.230320 (calm 0.130700). v4 tail_lin sweep: 0.0 -> 0.236985; 0.05 -> 0.236698;
0.1 -> 0.236538; 0.15 -> 0.236458; 0.2 -> 0.236465 -- tail_lin ~0.15 is v4's
local optimum, an UNTUNED knob in rounds 4-5.

Gemini (1 call, gemini-4-hydrogen, short prompt): DEADZONE (HINGE-GATED)
EXCESS-VOLATILITY PULL -- add gamma*max(0, ratio-tau) to the pull weight,
tau in [1.3, 1.5], so calm cases (ratio <= tau) are EXACTLY untouched.
Implemented as hinge_tau/hinge_gamma on rscale. Tested locally: the hinge
provably leaves calm bit-identical (p04/p05 unchanged to 6 decimals) and
gains ~0.00006 on v4+slow/log; on the fitted B2#3 it is near-neutral
(0.230265 hinge-off vs 0.230318 fitted) -- kept as fitted, not hand-tuned.

Phase B (10,003 evals, 4 families x 2500): best overall 0.229466 (slow/log
r5best-neighborhood, calm 0.133775, NOT clean); best clean 0.230455
(calm 0.128780, worst -0.0014, nimp=6 -- EVERY case improves vs v4).
5 clean candidates. All top-10 from slow/log@r5best.
Phase B2 (10,003 evals, centers C1/O1 + hinge, narrow/wide): best overall
0.228738 (o1_narrow, calm 0.133371, NOT clean -- below the 0.229 target on
mean but fails calm); 61 clean candidates. Best clean 0.230169 (calm
0.129379, worst -0.000007, nimp=5). Best BALANCED clean #3: 0.230318,
calm 0.128398, worst -0.0009, nimp=5 -- dominates Phase-B C1 on BOTH mean
and calm. CHOSEN as the v5B candidate.
Phase B3 (10,003 evals, centers B2#3/B2#1/original-O1 + hinge): [PENDING --
fill in when done; if no clean winner beats B2#3, B2#3 stands.]

v5B per case: p00 0.324333, p01 0.294254, p02 0.315454, p03 0.242211,
p04 0.160436, p05 0.096360; mean 0.230318; calm p04/p05 0.128398
(guardrail <=0.1340 PASSED, better than v4's 0.130397). Wins vs v4: 5/6
cases improve >=0.001 (p02 +0.0011 -- every case improves; worst -0.0009).
Files: dev/main_v5b_candidate.py (stdlib port, 370 lines, md5
961455596c24ffe0325ec33333a00903) + dev/best_params_v5b.json (md5
8ae34a921dc45f90c23eb6143e53cf8c). Verified via official scorer path
(poly_score2.py): mean 0.230318 EXACT (per-case identical to 6 decimals),
deterministic (byte-identical x2 runs), ~0.1 s/case, shape valid.
Validation (local, /tmp/poly_r5b_valid.py): LOCO 5/6 wins (only p05 loses,
+0.0046, a train-5-vmed artifact -- nested LOCO fixes it); nested LOCO
5/6 wins; permutation placebo mean diff +0.0236 (all 5 shuffled-V perms
worse by +0.008 to +0.040 -- the regime-V matching is real, not a fluke).
Comparison candidates: C1 LOCO 4/6, nested 6/6, placebo +0.0194; B2#1
(mean 0.230169) LOCO 4/6, nested 6/6, placebo +0.0130. B2#3 chosen for
best LOCO + strongest placebo + best calm.

COMPARISON WITH ROUND 5 (read from this file, not re-derived): round 5's
v5 scores 0.222954 mean / calm 0.128383 -- BETTER than v5B's 0.230318 on
practice mean, with nearly identical calm (0.128383 vs 0.128398). Its
mechanisms (target gate, fast pull, linear target, empirical-z blend,
staleness weights) are a different, larger gain than 5B's regime-V/hinge
angle. The submit decision (v4 vs v5 vs v5B, before 04:00 WIB 14 Nov) is
Adit's; 5B's candidate stands as the verified clean regime-angle entry.
Do NOT submit any of them without his explicit yes.

## Round 6 (14 Nov ~00:55-02:50 WIB) — v6 CONSERVATIVE: 0.222954 -> 0.222196 (target <=0,215 NOT reached)
Perintah Adit 00:54 WIB: "upgrade lagi v5 sampe maksimal resource". Target: mean <=0,215
(bar top-3 ~0,219), calm <=0,1284. Hasil FINAL: mean 0.222196, calm 0.127977 — gain
kecil tapi bersih -0,000758 mean / -0,000406 calm vs v5, menang 5/6 case (p00 +0,000055,
noise). Target 0,215 TIDAK tercapai (selisih 0,006); v6 tetap di zona top-10 practice
(bar ~0,231), di luar top-3 (~0,219).

### Skor v6 FINAL per case (official scorer, reproduksi persis)
| Case | v6 | v5 | Δ |
|---|---|---|---|
| p00 | 0.276664 | 0.276608 | +0.000055 |
| p01 | 0.287396 | 0.291221 | -0.003825 |
| p02 | 0.309507 | 0.309624 | -0.000117 |
| p03 | 0.247844 | 0.248005 | -0.000161 |
| p04 | 0.158944 | 0.159240 | -0.000295 |
| p05 | 0.097010 | 0.097526 | -0.000516 |
| Mean | 0.222196 | 0.222954 | -0.000758 |
| Calm | 0.127977 | 0.128383 | -0.000406 |

### Mekanisme v6 FINAL (hanya 3 perubahan bedah di atas v5, tiap-tiap ada bukti LOCO)
1. rscale_lo 0.3 -> 0.6 (sweep 0.45-1.0, optimum ~0.6): case paling tenang
   (p05, V=0.0013) clipping di floor 0.3 dan pull terlalu lemah. Ablasi:
   hapus -> +0.000108 mean, v6 menang 6/6. Nested LOCO: train-best lo=0.6
   di 4/6 fold (p04: 0.4, p05: 0.7); held-out tetap lebih baik di 0.6.
2. Z-table + baris h=240 ([-1.96, -0.483, 0, 0.387, 3.405] dari residual v5):
   ekor terus tumbuh dengan h; tabel lama clamp h>180 ke baris 180.
   Ablasi: hapus -> +0.000173 mean. Ini koreksi miss-spesifikasi terukur,
   bukan parameter hasil tuning.
3. trend_win 60 -> 30 (Box LOCO + local sweep 15-90, plateau 25-30):
   gain -0.00046 mean, didorong p01 (-0.0028). Box LOCO: tw=30 terpilih
   4/6 fold, weighted -0.00042, fold terburuk +0.00029.

### KEPUTUSAN BESAR ronde 6: polish 30-param DITOLAK (nested LOCO)
Jalur lokal sempat mencapai 0.220954 (calm 0.126083) via random search 3 seed
(~7500 eval) + coordinate descent 3 ronde (~30 param). Tapi NESTED LOCO refit
(script /tmp/poly_r6_nested_loco.py: 1 ronde descent dari v5 di train-5,
uji held-out) MENGHANCURKANNYA: weighted refit 0.228065 vs v5 0.222763
(+0.0053 LEBIH BURUK); tiap fold refit kalah dari v5 di held-out
(p00 +0.0152, p03 +0.0076, p02 +0.0059, p01 +0.0031, p04 +0.0018, p05 0.0000).
Artinya polish itu overfit dan besar kemungkinan skor LEBIH BURUK dari v5 di
12 case final yang belum terlihat. Jalur Box independen sampai ke kesimpulan
yang sama (CD 0.221405 in-sample -> LOCO 0.233003). Maka file kandidat
DIKEMBALIKAN ke v5 + 3 mekanisme tervalidasi di atas; param hasil descent
hanya tercatat di /tmp/poly_r6_final_params.json sebagai arsip, BUKAN di file
kandidat. Pelajaran: di 6 case, tuning massal param = overfit; hanya
perubahan mekanisme dengan bukti LOCO yang boleh masuk kandidat.

### Ditolak di ronde 6 (jangan diulang tanpa alasan baru)
- kasym Box (asimetri pull bergantung horizon, up -0.59/dn -0.16): 4/4 varian
  lokal lebih buruk (0.2233-0.2251); Box juga menolak (terbaik 0.223036).
  Tidak menumpuk di atas v5 — fast pull + linear target sudah menangkapnya.
- Power-devigged share target (ide Gemini #1, a=0.7-1.5): KATASTROFIK,
  p00 0.55-1.74.
- Median drift (+/-0.001-0.002 di h=240): semua lebih buruk.
- Mid_lin (0.1-0.3) dan mid_lin_up q75-only: netral (+/-0.0001).
- gap_kup (k_up tumbuh dengan |gap|): makin buruk monoton, p02 +0.009 di 2.0.
- Z-table refit penuh dari residual v5: 0.223035, ditolak (overfit point-mass
  nol; z25=0 di h=8). Box juga netral (LOCO +0.000041).
- Regime-split z-table (volatile vs calm): 0.222108, ditolak (noisy, p00 +0.0022).
- lead_k price-discovery gate (ide Gemini #2): makin buruk monoton
  (0.2221->0.2275); bantu p02 -0.006 tapi hancurkan p00/p04.
- act_e activity-scaled sigma (ide Gemini #2): semua lebih buruk
  (0.2218-0.2676).
- Logit-space fan (ide Gemini #3): sudah ditolak katastropik di ronde 5 (0.267).
- Box probes ditolak: h_pow, db_h, k_regime, gb_dn, pull_fast_w 0.7/0.85,
  kappa 0.1/0.3, z_blend_h (datar). Box random search 2500 eval: TIDAK SATU
  PUN mengalahkan v5 — v5 optimum lokal yang kuat di ruang itu.
- EDA sampingan Box: p02 board sum 0.8075 (gap +0.1925) tapi sum masa depan
  cuma pulih ke ~0.897 — gap menutup ~45% saja, konsisten dengan k_up kecil,
  bukan celah mekanisme baru.

### Validasi v6 FINAL (script /tmp/poly_r6_validate.py, log /tmp/poly_r6_validate_cons.log)
- Skor reproduksi persis via scorer resmi; deterministik (2 run byte-identical);
  shape valid (19/19/19/23/24/24 market, 240x5, monoton, [0,1]); ~0,1 dtk/case.
- Gate plateau: rscale_lo 0.45-0.75 semua 0.2222-0.2223; target_gate_k dan
  fast_gate_k datar di sekitar optimum — bukan artefak tuning tajam.
- Reverse-gate placebo: 0.242425 (gain terhapus penuh — sinyal regime nyata).
- Z-table LOCO: ±0.0005 di 4/6 case; p03 +0.0021, p05 +0.0008 — tabel membawa
  sedikit fit case-spesifik, dicatat jujur.
- Nested LOCO rscale_lo: pilihan 0.6 robust (lihat atas).
- Ablasi per-fold: tiap mekanisme menang 6/6 (rscale_lo), 5/6 (h240),
  4/6 (trend_win — gainnya p01-sentris, tapi Box LOCO mendukung).
- CATATAN JUJUR: gain total kecil (-0.0008). Practice rank bukan final rank;
  final = 12 case CALM belum terlihat. Rekomendasi ini "lebih baik dari v5
  dengan bukti", bukan "top-3 tercapai".

### Resource ronde 6
- Lokal: 3 random search (~7500 eval) + coordinate descent 3 ronde + nested
  LOCO + EDA (per-tau, coverage, bias, z-refit, regime-split) + Gemini 2 call
  sukses (5 ide, 2 katastropik, 2 ditolak, 1 tidak diimplementasi).
- Simular Box: child independen, ~5500+ eval, 4 core; laporan final terpisah.
  Kandidat Box terbaik (v5 + trend_win 30 = 0.222484, calm 0.128395) kalah
  dari v6 konservatif lokal (0.222196) dan calm-nya praktis di garis guardrail.
- File FINAL: dev/main_v6_candidate.py (md5 e99230588c27dc340662f96f03883b98),
  dev/best_params_v6.json. main.py (v4) + file v5 + file 5B TIDAK tersentuh.
- Rekomendasi: submit v6 konservatif sebagai replacement (0.222196,
  calm 0.127977) — gain kecil tapi bersih dan tervalidasi LOCO; target 0.215
  tidak tercapai. Keputusan submit tetap Adit, deadline 04:00 WIB.
