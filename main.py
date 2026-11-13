# ROUND 10 — v10 CANDIDATE (coordinator synthesis, 14 Nov ~02:35 WIB).
# V9 base (0.202403) + Box track: k_up 0.38, zb_w 1.5, xfan_w 0.65.
# Mean 0.199545, calm 0.120819, wins 6/6 vs V9, LOCO 6/6 folds (Box).
# REJECTED from stack: Track 3 E3c calm hurdle (Box+E3c 0.199575, +0.000030
# vs Box alone — calm gains shrink once zb/xfan are strong, p03 cost stays).
# Deterministic, stdlib-only, offline. Submitted 14 Nov ~02:30 WIB as round 3
# (replacing v6), on Adit's explicit order "Submit V10 sekarang".
# Verified independently by main agent: score 0.199545 reproduced exactly,
# deterministic (2 runs byte-identical), main.py v6 untouched until this copy.
# ROUND 9 — v9 CANDIDATE (Track G synthesis, coordinator merge, 14 Nov ~02:55 WIB).
# v8 base (0.207126) + 4 validated components: k_up 0.45 (Track A+E/C), F3 stale
# inner pin c=0 age=120 (Track F), B conditional z-shape zb_w=0.5 (Track B),
# D boundary-aware fan XFAN_W=0.20 (Track D). Mean 0.202403, calm 0.122283,
# wins 6/6 vs v8. Target 0.170-0.180 NOT reached (gap 0.022 to 0.180).
# Validation: drop-one ablation all contribute; disable-all placebo reproduces
# v8 exactly 0.207126; reverse-sign D placebo 0.208530 (worse than v8);
# per-component LOCO in NOTES.md Round 9. Deterministic, stdlib-only, offline.
#!/usr/bin/env python3
# ROUND 8 — v8 CANDIDATE (synthesis A+C+D+E, coordinator merge, 14 Nov ~02:05 WIB).
# Baseline v7 0.220199 -> v8 0.207126, calm 0.128007 -> 0.124529 (official
# scorer /tmp/poly_score2.py, verified: score reproduced exactly,
# deterministic 2 runs byte-identical, shape valid, ~0.1 s/case).
# Composition (each mechanism independently LOCO-validated by its track;
# the stack was validated by drop-one ablation + disable-all placebo
# (reproduces v7 EXACTLY, 0.220199) + reverse-sign placebo (0.241642)
# + 6-point interaction grid (plateau flat, all neighbours worse)):
#   A: last-move (d1) displacement, regime-gated, sign flips by horizon
#      (continue short, revert long) — Track A, 0.214552 standalone.
#   C: 5 hypothesis-driven param changes (pull_b 1.8, c_trend -0.18,
#      db_spread 0.9, h_sat 11.0, tail_wide 1.0) — Track C, 0.217627.
#   D: regime-gated down-momentum (gmom_k 0.25, win/tau 30, gate 2.0)
#      — Track D, 0.216063 standalone.
#   E: regime-gated pull exponent (pull_b_calm 2.25 below rscale 1.2)
#      — Track E, 0.218768 standalone.
# REJECTED from the stack: Track F fan blend (ACDEF 0.207245, worse than
# ACDE) and Box recent-vol fan (ACDEBOX 0.206844, net -0.000282 but 2/4
# volatile cases WORSE than ACDE — wash, not a stack). Target 0.170-0.190
# NOT reached (gap 0.017 to 0.190); see NOTES.md Round 8 for bound evidence.
# Target 0.170-0.190 TIDAK TERCAPAI. Submit needs Adit's explicit yes.
"""Polymarket "Next CEO of NVIDIA?" minute-by-minute Yes-price quantile forecaster.

Reads one case at a time from $MAKEFUN_INPUT_DIR (else /input): the 24 trading
markets' Yes prices on a 1-minute grid up to a checkpoint. Writes
$MAKEFUN_OUTPUT_DIR/<id>.out (else /output/<id>.out): for each market and each
of the 240 minutes after the checkpoint, five quantiles (5/25/50/75/95%) of
that minute's price.

Method (all parameters are fixed constants below; nothing is fitted at run
time beyond what the case's own prices imply). Evidence from the practice
history (EDA on the six practice cases, answers rebuilt from Polymarket's
public CLOB history):
  * Median: last price, pulled toward its board-sum-normalised share
    (the 24 Yes prices sum to ~1; a market's fair share is x / sum(x) --
    the 240-minute move regresses on the sum gap with slope ~0.55), with
    the board-sum adjustment shared across markets in proportion to
    x_i * sigma_i (liquid markets absorb more of the gap; the old x_i-only
    sharing scored 0.2517 vs 0.2512 for this one, and is better on the
    calm cases too), plus give-back of recent run-ups: after a 1-minute
    rise >= 0.02 the price gives back ~2/3 within 15 minutes and ~3/4
    within an hour, while after a fall of the same size it gives back
    almost nothing -- so the give-back is strongly asymmetric (rises
    revert, falls persist).
    Momentum extrapolation and pull toward a slow EMA both HURT badly
    (tested: momentum k=0.2 already costs +0.016 loss), so neither is used.
  * v3 changes (round 2, practice 0.2512 -> 0.2441; top-10 bar 0.237 NOT
    reached -- see NOTES.md for the full rejected list):
    - ASYMMETRIC sum-pull: when the board is UNDER-priced (sum < 1) the
      pull is scaled by k_up = 0.5 (the gap closes only ~half as much
      upward as the symmetric model assumes); when OVER-priced (sum > 1)
      it is scaled by k_down = 1.4 (down-gaps close almost fully).
    - GAP TREND (momentum, not mean-reversion): the pull uses the gap
      EXTRAPOLATED by its last-60-min change (gap - c_trend*(gap-gap60),
      c_trend = -0.2). Reversing the trend instead (c > 0) costs +0.015.
    - PULL TILT across quantiles: the pull displacement is scaled by
      (1 - kappa*z), kappa = 0.15, so the lower tail moves more with the
      pull than the upper tail (gap closure arrives as downward jumps).
    - GIVE-BACK softened to gb_up = 0.35 (0.45 over-gives-back on drifts;
      the history OLS slope is only ~0.17 and the robust median is 0).
    - DEADBAND + fan compression: when a row's median displacement from
      the last price is < 0.001 the median is set to the last price
      exactly (57% of 240-min moves are exactly zero, so small drifts are
      pure MAE drag) and the fan around it is compressed x0.85 (a market
      that is not moving has a narrower forward distribution).
  * v4 changes (round 4, practice 0.2441 -> 0.236538; top-10 bar 0.237
    REACHED; calm p04/p05 mean 0.1331 -> 0.130397 — see NOTES.md):
    REGIME SCALING. The board's mean EWMA sigma V at the checkpoint
    measures the volatility regime (launch V ~0.0035-0.0036, calm
    V ~0.0013-0.0020; practice median Vmed = 0.002696). Pull strength is
    scaled by (1 + 1.7*(V-Vmed)/Vmed), clipped to [0.3, 2.5], and sigma
    by (V/Vmed)^0.5, clipped to [0.5, 2.0]: launch regimes pull harder
    with a wider fan, calm regimes pull softer with a narrower fan.
    Also k_down 1.4 -> 1.61, k_up 0.5 -> 0.425, cap 0.012 -> 0.0102,
    pull_tau 120 -> 111, outer tail widens x(1 + 0.1*h/240).
  * v5 changes (round 5, practice 0.236538 -> 0.226575; top-10 bar ~0.231;
    calm p04/p05 mean 0.130397 -> 0.129256 — see NOTES.md):
    - REGIME-GATED TWO-TIMESCALE PULL: pull(h) gains a fast component
      (tau 10 min) gated by regime, w_f_eff = 1.0*clip(2.0*(rscale-1),0,1),
      so only volatile/launch regimes pull fast; calm cases keep v4's
      slow pull exactly (calm score unchanged by this mechanism alone).
      EDA: the true pull response is fast early (OLS slope 0.27 at h<=15)
      while v4's single exp(-h/111) gives only 0.06 there.
    - REGIME-GATED LINEAR SHARE TARGET: in volatile regimes the pull
      converges to the pure board-sum-normalised share (adj = x/sum - x)
      instead of the x*sigma-weighted gap share; blended by regime,
      g = clip(2.0*(rscale-1),0,1). v4's weighted allocation misallocates
      the gap when sigma varies wildly across markets (launch). p00
      improves 0.3486 -> 0.2884; other cases neutral-to-better.
    - EMPIRICAL-Z FAN BLEND (0.25): Gaussian z blended toward the pooled
      empirical quantiles of (y-med)/sigma(h) by horizon bucket; the
      residual distribution is narrower and asymmetric vs Gaussian
      (q25 -0.24 vs -0.674, q75 +0.06 vs +0.674; q95 grows with h).
    - k_down 1.61 -> 1.9, k_up 0.425 -> 0.3.
    Rejected in round 5: vol-trend fan scaling, v_mode median/recent,
    regime-scaled give-back, two-timescale give-back (helps calm only),
    z_lo/z_hi asymmetry, per-market tick deadband (marginal), staleness
    weights >0.5, target logit (similar to linear, slightly worse).
  * v6 changes (round 6, CONSERVATIVE version, practice 0.222954 -> 0.222196;
    calm 0.128383 -> 0.127977). Only three surgical changes on top of v5,
    each with its own out-of-sample evidence; everything else is v5 exactly:
    - rscale floor 0.3 -> 0.6 (sweep 0.45-1.0, optimum ~0.6; nested LOCO:
      train-best lo=0.6 in 5/6 folds, held-out p05 improves).
    - Z-table + h=240 row ([-1.96, -0.483, 0, 0.387, 3.405] from v5
      residuals): tails keep growing with h; old table clamped h>180.
      Ablation: removing it costs +0.00035 mean, v6 wins 6/6.
    - trend_win 60 -> 30 (Box LOCO + local sweep 15-90, plateau 25-30):
      gain -0.00046 mean, driven by p01 (-0.0028).
    REJECTED for submission (in-sample only, see NOTES.md): the full
    30-param coordinate-descent polish (0.220954 in-sample). Nested LOCO
    refit: 0.228065 held-out vs v5 0.222763 — the polish overfits and would
    likely score WORSE than v5 on unseen cases. Same verdict independently
    from the Box lane (CD 0.221405 -> LOCO 0.233003).
  * v8 Track A changes (round 8, practice 0.220199 -> 0.214552; calm UNCHANGED
    0.128007 — see NOTES.md Round 8 Track A). ONE new mechanism on top of v7:
    LAST-MOVE (d1) DISPLACEMENT, regime-gated. EDA (joint OLS of y_h-x on
    adj, d1, r60 per horizon bucket, pooled 6 cases): the last 1-minute move
    d1 CONTINUES at short horizon (slope +0.39 at h<=8, +0.69 at h9-30) then
    REVERTS at long horizon (-0.37 at h31-90, -0.52 at h91-180, -0.86 at
    h181-240); r60 slope ~0 (give-back already captures it). The median of
    every quantile row is shifted by B(h)*d1*g, B(h) linearly interpolated
    between bucket centres (4.5, 19.5, 60.5, 135.5, 210.5), g =
    clip(d1_gate_k*(rscale-1),0,1) so calm cases (rscale<=1) are EXACTLY
    untouched. This is NOT momentum extrapolation (rejected rounds 1-7):
    that was a same-sign drift on the 60-min run-up; this is a two-phase
    d1 response whose long-horizon leg is reversion, and it is gated off
    in calm regimes. The full linear-median replacement (adj+d1+r60 OLS
    median instead of v7 pull) was tried and REJECTED (0.2352, calm 0.158);
    the additive-on-v7 form is what works. Centre alternatives (median /
    mean / EWMA of last K prices) all LOSE to the last price at every
    horizon and were rejected; gap smoothing adds nothing (corr flat).
  * Spread: per-market realised volatility as a blend of a fast and a slow
    EWMA of squared 1-minute changes (winsorised), with a price-level
    floor; the per-minute spread grows with horizon but saturates hard
    (the SD of h-step changes grows like h^0.33, not sqrt(h)), and the
    outer quantiles are widened for fat tails. A direct empirical
    h-step-quantile fan was tried and was much worse (0.313): the move
    distribution is a point mass at zero with rare jumps, so raw empirical
    quantiles collapse.
  * Everything is clipped to [0, 1], rows are non-decreasing, output is
    deterministic (no randomness, no network, stdlib only). A market with
    no prices at all is forecast flat at 0.5 rather than crashing the run:
    one bad market must never invalidate the whole case.
"""
import json
import math
import os

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]

PARAMS = {
    # realised volatility: EWMA half-lives (minutes) and blend weight
    "fast_hl": 15.0,
    "slow_hl": 240.0,
    "fast_w": 0.65,
    "winsor": 0.06,          # clip 1-min changes before squaring
    "floor_a": 0.0002,       # sigma floor: floor_a + floor_b * last price
    "floor_b": 0.005,
    "cap": 0.0102,            # sigma cap (per-minute)
    # horizon saturation of the spread: sigma(h) = s1*sqrt(h)/sqrt(1+h/h_sat)
    "h_sat": 11.0,
    # quantile shape: widen the outer pair for fat tails
    "tail_wide": 1.0,
    "mid_wide": 0.994842,
    # horizon-linear outer-tail widening (round 4): outer width x (1 + tail_lin*h/240)
    "tail_lin": 0.217931,
    # median: pull toward sum-normalised share, strength pull_max*(1-exp(-h/pull_tau))
    "pull_max": 0.931198,
    "pull_tau": 161.241351,
    # pull weight: w_i propto x_i * sigma_i^pull_b, so liquid markets absorb
    # more of the board-sum adjustment (pull_b=0 is the old x_i-only weight)
    "pull_b": 1.8,
    "pull_b_gate": 1.2,
    "pull_b_calm": 2.25,
    # asymmetric pull: scale the pull when the board is under-priced
    # (gap > 0, sum < 1) vs over-priced (gap < 0, sum > 1)
    "k_up": 0.38,
    "zb_on": 1,
    "zb_w": 1.5,
    "stale_inner_c": 0.0,
    "stale_inner_age": 120.0,
    "k_down": 1.905285,
    # regime scaling (round 4): the board's mean EWMA sigma V measures the
    # volatility regime at the checkpoint; Vmed is its practice median.
    # pull strength x (1 + regime_pull*(V-Vmed)/Vmed), clipped to [0.3, 2.5];
    # sigma x (V/Vmed)^regime_fan, clipped to [0.5, 2.0]. In launch regimes
    # the pull is stronger and the fan wider; in calm regimes both shrink.
    # ROUND 6: rscale floor. The calmest case (p05, V=0.0013) clipped at the
    # 0.3 floor and pulled too weakly; 0.6 is the validated optimum
    # (sweep 0.45-1.0, plateau 25-30 for trend_win; nested LOCO clean).
    "rscale_lo": 0.6,
    "regime_pull": 1.663268,
    "regime_vmed": 0.0026960411939506426,
    "regime_fan": 0.297545,
    # gap trend: gap_used = gap - c_trend * (gap - gap_60min_ago);
    # c_trend < 0 EXTRAPOLATES the recent gap change (gap momentum)
    "c_trend": -0.18,
    "trend_win": 30,
    # pull tilt across quantiles: pull displacement x (1 - kappa*z)
    "kappa": 0.002571,
    # median: give-back of the last-60-min run-up, strength gb*(1-exp(-h/gb_tau))
    "gb_up": 0.37011,           # recent rise gives back
    "gb_dn": 0.0,            # recent fall bounces back ~nothing (measured)
    "gb_tau": 91.766134,
    # deadband: median displacement < db_eps is set to exactly the last
    # price, and the fan around it is compressed by db_spread
    "db_eps": 0.001175,
    "db_spread": 0.9,
    # ROUND 5 (experimental): empirical standardized-quantile fan.
    # z_blend in [0,1]: 0 = pure Gaussian v4, 1 = pure empirical z-table.
    # The z-table is the pooled empirical quantiles of (y - med)/sh(h),
    # bucketed by horizon (centres h=8,38,90,180), interpolated linearly.
    # z_lo / z_hi scale the lower / upper |z| magnitudes (asymmetry).
    "z_blend": 0.564716,
    "z_lo": 1.0,
    "z_hi": 1.0,
    # ROUND 5: two-timescale pull. pull(h) = pull_max*rscale*(
    #   pull_fast_w*(1-exp(-h/pull_tau_fast)) + (1-pull_fast_w)*(1-exp(-h/pull_tau))).
    # pull_fast_w=0 reproduces v4 exactly. EDA: true pull response is fast
    # early (slope 0.27 at h<=15) and grows to ~0.85 by h=240, while v4's
    # single exp(-h/111) gives only 0.06 at h=8.
    "pull_fast_w": 1.0,
    "pull_tau_fast": 14.679043,
    # ROUND 5: regime-scaled give-back. gb_up_eff = gb_up*(1+gb_regime*(rscale-1)).
    # gb_regime=0 reproduces v4.
    "gb_regime": 0.0,
    # ROUND 5: regime-gated fast pull. pull_fast_regime=1 gates the fast
    # pull component by the regime: w_f_eff = pull_fast_w*clip(gate_k*(rscale-1),0,1),
    # so calm cases keep v4's slow pull and only launch regimes pull fast.
    "pull_fast_regime": 1.0,
    "pull_fast_gate_k": 2.706696,
    # ROUND 5: two-timescale give-back. gb(h) = gb_max*(
    #   gb_fast_w*(1-exp(-h/gb_tau_fast)) + (1-gb_fast_w)*(1-exp(-h/gb_tau))).
    "gb_fast_w": 0.0,
    "gb_tau_fast": 15.0,
    # ROUND 5: vol-trend fan scaling. sigma1 *= (fast_sigma/slow_sigma)^e.
    # e=0 reproduces v4. Rising vol at the checkpoint -> wider forward fan.
    "vol_trend_e": 0.0,
    # ROUND 5 (Gemini ideas): staleness-weighted pull allocation.
    # raw_i *= stale_i^stale_w, stale_i = fraction of zero 1-min moves in
    # the last 240 prices (0 = fresh, 1 = fully stale). stale_w=0 is v4.
    "stale_w": 0.696201,
    # ROUND 5 (Gemini ideas): pull target mode. "weighted" = v4 (gap shared
    # by x*sigma weights); "linear" = adj_i = x_i/sum - x_i (pure
    # sum-normalised share target); "logit" = adj_i = sigmoid(logit(x_i)-c)
    # - x_i with c solving sum(sigmoid(logit(x_j)-c)) = 1.
    # target_gate_k > 0 BLENDS the target-mode adj with the weighted adj by
    # regime: adj = (1-g)*adj_weighted + g*adj_target, g = clip(gate_k *
    # (rscale-1), 0, 1) — calm cases keep v4, volatile cases use the target.
    "target_mode": "linear",
    "target_gate_k": 1.925936,
    # ROUND 7 (experimental): sigma-relative deadband. The flat db_eps judges
    # a median displacement against an absolute price scale, but a 0.001 move
    # is noise for a market with sigma 0.005 and signal for one with sigma
    # 0.0005. db_mode="sigma" sets eps_i = db_eps * sigma_i / median_sigma.
    "db_mode": "flat",
    "db_tick_k": 1.0,
    # ROUND 7 (experimental): size-dependent pull response. EDA (round 7):
    # pooled pull-response slope by market size: big (x>0.1) ~0.8 with
    # corr 0.5-0.7, mid (0.01-0.1) ~1.24-1.74 with corr 0.2-0.4, small
    # (x<0.01) corr ~0.00 -- small markets do not respond to the board-sum
    # gap at all (their moves are idiosyncratic/news jumps). size_mult_on=1
    # scales each market's adj by its size bucket multiplier; 0 = v6 exactly.
    "size_mult_on": 0,
    "size_mult_hi": 0.85,
    "size_mult_mid": 1.4,
    "size_mult_lo": 0.0,
    # ROUND 7b: gap-sign-dependent small-market multiplier. Small markets
    # cannot fall below 0 (floor) but can rise a lot, so their pull response
    # should be ~0 when the gap pulls DOWN (gap<0) and normal when the gap
    # pulls UP (gap>0). lo_up/lo_dn override size_mult_lo when set (>=0).
    "size_mult_lo_up": -1.0,
    "size_mult_lo_dn": -1.0,
    # ROUND 7: reallocate the gap after zeroing small markets (size_realloc=1
    # rescales the surviving adjs so their sum is preserved).
    "size_realloc": 0,
    # ROUND 7 (experimental): young-market fan boost. EDA: markets with <60
    # prices lose 1.21 (8x the average) with coverage_90 0.42-0.53 -- severe
    # under-coverage, i.e. a FAN problem, not a median problem. sigma1 is
    # multiplied by (1 + young_boost*exp(-n/young_tau)), fan only (V and
    # pull weights keep the unboosted sigma). FINAL v7: boost 1.5, tau 50
    # (plateau 1.0-2.0 x 50; train-best in nested LOCO 5/6 folds).
    "young_boost": 1.5,
    "young_tau": 50.0,
    # ROUND 7 (experimental): global fan scale (EDA: per-case optimal fan
    # multiplier 0.8-1.1, no regime pattern; gains tiny and mixed).
    "fan_scale": 1.0,
    # ROUND 8 Track A: last-move (d1) displacement, regime-gated.
    # B(h) = d1 response per horizon bucket (joint OLS, see docstring);
    # centres d1_h = [4.5, 19.5, 60.5, 135.5, 210.5], linear interp,
    # clamped outside. g = clip(d1_gate_k*(rscale-1),0,1): calm untouched.
    # d1_on=0 reproduces v7 exactly.
    "d1_on": 1,
    "d1_scale": 1.5,
    "d1_gate_k": 3.0,
    "d1_h": [4.5, 19.5, 60.5, 135.5, 210.5],
    "d1_b": [0.387, 0.694, -0.368, -0.515, -0.860],
    "gmom_k": 0.25,
    "gmom_win": 30,
    "gmom_tau": 30.0,
    "gmom_gate_k": 2.0,
    "gmom_mode": "dn",
    # ROUND 7 (experimental): saturating regime scaling, rscale =
    # 1 + regime_pull*tanh((V-Vmed)/Vmed) instead of the linear form.
    "rscale_tanh": 0,
    # ROUND 5: regime variable definition. "mean" = v4 (board mean sigma);
    # "median" = board median sigma; "recent" = sigma from last 240 prices.
    "v_mode": "mean",
    # ROUND 10 (Box track, NEW knobs; defaults reproduce v9 exactly):
    # xfan_w: v9 Track D weight, was module constant XFAN_W=0.20.
    "xfan_w": 0.65,
    # fan_h_lin: horizon-linear fan multiplier (1 + fan_h_lin*h/240) on sh.
    "fan_h_lin": 0.0,
    # pb_lo/pb_mid/pb_hi: per-x-bucket pull exponent overriding pb_eff
    # (-1 = use pb_eff). Bucket edges match _xbucket/<0.01/<0.1/>=0.1.
    "pb_lo": -1.0,
    "pb_mid": -1.0,
    "pb_hi": -1.0,
    # stale_outer_c: like stale_inner_c but for q05/q95 (1.0 = off).
    "stale_outer_c": 1.0,
}

# Empirical z-table: (h_centre, [z05, z25, z50, z75, z95]) from the v4
# residuals pooled over all six practice cases (see /tmp/poly_r5_eda.py).
ZTABLE = [
    (8, [-1.221, -0.070, 0.0, 0.000, 1.104]),
    (38, [-1.522, -0.242, 0.0, 0.062, 1.666]),
    (90, [-1.373, -0.289, 0.0, 0.164, 2.627]),
    (180, [-1.633, -0.485, 0.0, 0.308, 3.034]),
    # ROUND 6: h=240 row from v5 residuals (tails keep growing with h;
    # the old table clamped h>180 to the 180 row and understated long-h tails).
    (240, [-1.96, -0.483, 0.0, 0.387, 3.405]),
]


def _z_emp(h):
    """Interpolated empirical z vector at horizon h."""
    if h <= ZTABLE[0][0]:
        return ZTABLE[0][1]
    if h >= ZTABLE[-1][0]:
        return ZTABLE[-1][1]
    for (h0, z0), (h1, z1) in zip(ZTABLE, ZTABLE[1:]):
        if h0 <= h <= h1:
            f = (h - h0) / (h1 - h0)
            return [a + f * (b - a) for a, b in zip(z0, z1)]
    return ZTABLE[-1][1]


def price6(x):
    """Clamp to [0, 1], round to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)) * 1e6) / 1e6 + 0.0


def _ewma_sigma(prices, P):
    """Per-minute sigma from a fast/slow EWMA blend of squared 1-min changes."""
    if len(prices) < 2:
        return 0.0
    af = 1.0 - 0.5 ** (1.0 / P["fast_hl"])
    as_ = 1.0 - 0.5 ** (1.0 / P["slow_hl"])
    vf = 0.0
    vs = 0.0
    w = P["winsor"]
    prev = prices[0]
    for p in prices[1:]:
        d = p - prev
        prev = p
        if d > w:
            d = w
        elif d < -w:
            d = -w
        d2 = d * d
        vf += af * (d2 - vf)
        vs += as_ * (d2 - vs)
    var = P["fast_w"] * vf + (1.0 - P["fast_w"]) * vs
    return math.sqrt(var) if var > 0.0 else 0.0


def _sigma_capped(prices, P):
    """Per-minute sigma with the price-level floor and cap applied."""
    s = _ewma_sigma(prices, P)
    floor = P["floor_a"] + P["floor_b"] * prices[-1]
    if s < floor:
        s = floor
    if s > P["cap"]:
        s = P["cap"]
    return s


def forecast_market(prices, horizon, adj, P, rscale=1.0, fscale=1.0):
    """One market's 240x5 quantile rows. adj is this market's share of the
    board-sum adjustment (signed price units, added to the last price).
    rscale scales the pull strength, fscale scales sigma1 (regime scaling)."""
    if not prices:
        # No history at all: flat 0.5 beats crashing the whole case.
        return [[0.5, 0.5, 0.5, 0.5, 0.5] for _ in range(horizon)]
    n = len(prices)
    x = prices[-1]
    sigma1 = _sigma_capped(prices, P) * fscale
    # round-7 fan scale + young-market fan boost (both 1.0/0.0 = v6 exactly)
    sigma1 = sigma1 * P.get("fan_scale", 1.0)
    yb = P.get("young_boost", 0.0)
    if yb != 0.0:
        sigma1 = sigma1 * (1.0 + yb * math.exp(-n / P.get("young_tau", 100.0)))
    # round-5 vol-trend fan scaling
    e_vt = P.get("vol_trend_e", 0.0)
    if e_vt != 0.0:
        af = 1.0 - 0.5 ** (1.0 / P["fast_hl"])
        as_ = 1.0 - 0.5 ** (1.0 / P["slow_hl"])
        vf = 0.0
        vs = 0.0
        w = P["winsor"]
        prev = prices[0]
        for p in prices[1:]:
            d = p - prev
            prev = p
            if d > w:
                d = w
            elif d < -w:
                d = -w
            d2 = d * d
            vf += af * (d2 - vf)
            vs += as_ * (d2 - vs)
        if vf > 0.0 and vs > 0.0:
            sigma1 = sigma1 * (math.sqrt(vf) / math.sqrt(vs)) ** e_vt
    # median targets
    r60 = x - prices[-61] if n >= 61 else x - prices[0]
    up = r60 if r60 > 0.0 else 0.0
    dn = r60 if r60 < 0.0 else 0.0
    # round-5: regime-scaled give-back (gb_regime=0 reproduces v4)
    gb_up_eff = P["gb_up"] * (1.0 + P.get("gb_regime", 0.0) * (rscale - 1.0))
    gb_dn_eff = P["gb_dn"] * (1.0 + P.get("gb_regime", 0.0) * (rscale - 1.0))
    rows = []
    b = P.get("z_blend", 0.0)
    zlo = P.get("z_lo", 1.0)
    zhi = P.get("z_hi", 1.0)
    for h in range(1, horizon + 1):
        # round-5 two-timescale pull (pull_fast_w=0 reproduces v4)
        w_f = P.get("pull_fast_w", 0.0)
        if P.get("pull_fast_regime", 0.0) != 0.0:
            w_f = w_f * min(1.0, max(0.0, P.get("pull_fast_gate_k", 1.0) * (rscale - 1.0)))
        pull = P["pull_max"] * rscale * (
            w_f * (1.0 - math.exp(-h / P["pull_tau_fast"]))
            + (1.0 - w_f) * (1.0 - math.exp(-h / P["pull_tau"])))
        # round-5 two-timescale give-back (gb_fast_w=0 reproduces v4)
        w_g = P.get("gb_fast_w", 0.0)
        gb = (w_g * (1.0 - math.exp(-h / P["gb_tau_fast"]))
              + (1.0 - w_g) * (1.0 - math.exp(-h / P["gb_tau"])))
        gb_disp = gb * (gb_up_eff * up + gb_dn_eff * dn)
        sh = sigma1 * math.sqrt(h) / math.sqrt(1.0 + h / P["h_sat"])
        # R10: horizon-linear fan scale (0 = v9 exactly)
        sh = sh * (1.0 + P.get("fan_h_lin", 0.0) * h / 240.0)
        ze = _z_emp(h)
        if P.get("zb_on", 0):
            _d = _zb_delta(x)
            _w = P.get("zb_w", 0.5)
            ze = [a + _w * dd for a, dd in zip(ze, _d)]
        row = []
        for j, z in enumerate(Z):
            if j in (0, 4):
                w = P["tail_wide"] * (1.0 + P["tail_lin"] * h / 240.0)
            else:
                w = P["mid_wide"]
            # round-5 blend: effective z and width interpolate toward the
            # empirical table as z_blend -> 1 (width -> 1.0 there)
            zj = (1.0 - b) * z + b * ze[j]
            wj = (1.0 - b) * w + b * 1.0
            if j < 2:
                zj = zj * zlo
            elif j > 2:
                zj = zj * zhi
            # pull tilt: lower tail moves more with the pull than upper tail
            pd = pull * adj * (1.0 - P["kappa"] * z)
            row.append(price6(x + pd - gb_disp + zj * wj * sh))
        # enforce non-decreasing after rounding
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


# TRACK B: conditional z deltas by price level (x = last price), from v8-residual
# z quantiles pooled over 6 practice cases (see /tmp/b_eda2.py sec C/D).
# LOCO-stable signals: lo markets q25 = 0.00 in EVERY fold & horizon (they
# essentially never move down: floor + no trading), q05 ~-0.4 vs pooled ~-1.5;
# mid markets q25 ~-0.53 vs pooled ~-0.4; hi markets q05 ~-0.55 vs pooled ~-1.5.
# q95 deltas are sign-flipping across h (outlier-driven, n small) -> set to 0.
# Deltas are constant across h (smoothed); blended 50% toward pooled table.
ZB_DELTA = {
    "lo":  [1.2, 0.35, 0.0, 0.0, 0.0],   # x < 0.01
    "mid": [0.0, -0.15, 0.0, -0.05, 0.0],# 0.01 <= x < 0.1
    "hi":  [0.5, 0.15, 0.0, 0.2, 0.0],   # x >= 0.1
}
def _zb_delta(x):
    if x < 0.01: return ZB_DELTA["lo"]
    if x < 0.1: return ZB_DELTA["mid"]
    return ZB_DELTA["hi"]


def _apply_deadband(out, case, P):
    """Deadband + fan compression: for each market/h, if the median's
    displacement from the last price is < db_eps, set the median to the
    last price exactly and compress the fan around it by db_spread."""
    eps = P["db_eps"]
    s_db = P["db_spread"]
    xs = {m["id"]: (m["prices"][-1] if m["prices"] else 0.5)
          for m in case["markets"]}
    # round-5 per-market tick deadband (Gemini idea 2)
    eps_map = {}
    if P.get("db_mode", "flat") == "sigma":
        sigs = [_sigma_capped(m["prices"], P) if m["prices"] else 0.0
                for m in case["markets"]]
        ss = sorted(s for s in sigs if s > 0.0)
        smed = ss[len(ss) // 2] if ss else 0.0
        for m, s in zip(case["markets"], sigs):
            eps_map[m["id"]] = eps * s / smed if smed > 0.0 and s > 0.0 else eps
    elif P.get("db_mode", "flat") == "tick":
        for m in case["markets"]:
            pr = m["prices"]
            if len(pr) >= 2:
                nz = sorted(abs(b - a) for a, b in zip(pr[-241:], pr[-240:])
                            if b != a)
                tick = nz[len(nz) // 2] if nz else 0.0
                eps_map[m["id"]] = (P.get("db_tick_k", 1.0) * tick
                                    if tick > 0 else eps)
            else:
                eps_map[m["id"]] = eps
    new = {}
    for mid, rows in out.items():
        x = xs[mid]
        e_i = eps_map.get(mid, eps)
        nr = []
        for row in rows:
            med = row[2]
            if abs(med - x) < e_i:
                r2 = [price6(x + (v - med) * s_db) if j != 2 else price6(x)
                      for j, v in enumerate(row)]
                r2[2] = price6(x)
                for j in range(1, 5):
                    if r2[j] < r2[j - 1]:
                        r2[j] = r2[j - 1]
                nr.append(r2)
            else:
                nr.append(row)
        new[mid] = nr
    return new


def _d1_at(h, P):
    """Interpolated d1 response B(h) at horizon h (clamped outside)."""
    hs = P.get("d1_h", [4.5, 19.5, 60.5, 135.5, 210.5])
    bs = P.get("d1_b", [0.387, 0.694, -0.368, -0.515, -0.860])
    if h <= hs[0]:
        return bs[0]
    if h >= hs[-1]:
        return bs[-1]
    for i in range(len(hs) - 1):
        if hs[i] <= h <= hs[i + 1]:
            f = (h - hs[i]) / (hs[i + 1] - hs[i])
            return bs[i] + f * (bs[i + 1] - bs[i])
    return bs[-1]


def _apply_d1(out, case, P, rscale):
    """Round-8 Track A: shift every quantile row by B(h)*d1*g (see docstring).
    Applied AFTER the deadband, so the verified score is the post-deadband
    shift. g = clip(d1_gate_k*(rscale-1),0,1): calm regimes (rscale<=1)
    get g=0 and are bit-identical to v7."""
    if not P.get("d1_on", 0):
        return out
    g = min(1.0, max(0.0, P.get("d1_gate_k", 2.0) * (rscale - 1.0)))
    if g == 0.0:
        return out
    scale = P.get("d1_scale", 1.0)
    new = {}
    for m in case["markets"]:
        pr = m["prices"]
        rows = out[m["id"]]
        if not pr or len(pr) < 2:
            new[m["id"]] = rows
            continue
        d1 = pr[-1] - pr[-2]
        if d1 == 0.0:
            new[m["id"]] = rows
            continue
        nr = []
        for h, row in enumerate(rows, start=1):
            delta = scale * _d1_at(h, P) * d1 * g
            if delta == 0.0:
                nr.append(row)
                continue
            r2 = [price6(v + delta) for v in row]
            for j in range(1, 5):
                if r2[j] < r2[j - 1]:
                    r2[j] = r2[j - 1]
            nr.append(r2)
        new[m["id"]] = nr
    return new


def _apply_gmom(out, case, P, rscale):
    """Round-8 Track D: regime-gated down-momentum, applied AFTER the
    deadband (and after d1 when combined). Shifts every quantile by the
    same displacement, then re-clips/re-sorts."""
    gk = P.get("gmom_k", 0.0)
    if gk == 0.0:
        return out
    g = min(1.0, max(0.0, P.get("gmom_gate_k", 2.0) * (rscale - 1.0)))
    if g == 0.0:
        return out
    win = int(P.get("gmom_win", 30))
    tau = P.get("gmom_tau", 30.0)
    new = dict(out)
    for m in case["markets"]:
        pr = m["prices"]
        if not pr:
            continue
        r30 = pr[-1] - (pr[-(win + 1)] if len(pr) >= win + 1 else pr[0])
        if P.get("gmom_mode", "dn") == "dn":
            r30 = min(r30, 0.0)
        elif P.get("gmom_mode", "dn") == "up":
            r30 = max(r30, 0.0)
        if r30 == 0.0:
            continue
        rows = out[m["id"]]
        nr = []
        for hi, row in enumerate(rows):
            h = hi + 1
            d = g * gk * r30 * (1.0 - math.exp(-h / tau))
            r2 = [price6(v + d) for v in row]
            for j in range(1, 5):
                if r2[j] < r2[j - 1]:
                    r2[j] = r2[j - 1]
            nr.append(r2)
        new[m["id"]] = nr
    return new

def _apply_stale_inner(out, case, P):
    """Round-9 Track F3: compress q25/q75 toward the median for stale markets."""
    c = P.get("stale_inner_c", 1.0)
    if c >= 1.0:
        return out
    new = dict(out)
    for m in case["markets"]:
        pr = m["prices"]
        if len(pr) < 2:
            continue
        age = 0
        for i in range(len(pr) - 1, 0, -1):
            if pr[i] != pr[i - 1]:
                age = len(pr) - 1 - i
                break
        else:
            age = len(pr)
        f = min(1.0, max(0.0, age / P.get("stale_inner_age", 240.0)))
        if f == 0.0:
            continue
        k = 1.0 - (1.0 - c) * f
        # R10: optional outer-quantile compression for very stale markets
        co = P.get("stale_outer_c", 1.0)
        k2 = 1.0 - (1.0 - co) * f if co < 1.0 else 1.0
        rows = out[m["id"]]
        nr = []
        for row in rows:
            med = row[2]
            r2 = [price6(med + (row[0] - med) * k2),
                  price6(med + (row[1] - med) * k), row[2],
                  price6(med + (row[3] - med) * k),
                  price6(med + (row[4] - med) * k2)]
            for j in range(1, 5):
                if r2[j] < r2[j - 1]:
                    r2[j] = r2[j - 1]
            nr.append(r2)
        new[m["id"]] = nr
    return new



# V9 TRACK D: per-x-bucket empirical z of (y - med_v8)/sh, all 6 practice
# cases, h-centres 8/38/90/180/240, windows +-7 (h=8) / +-25 (else).
# See header: the residual shape depends on the last price x.
ZTABLE_X = {
    "x<.005": [
        (8, [-0.2883, 0.0000, 0.0000, 0.0000, 1.7649]),
        (38, [-0.3487, 0.0000, 0.0000, 0.1140, 2.6763]),
        (90, [-0.4598, 0.0000, 0.0000, 0.1552, 3.3613]),
        (180, [-0.4529, 0.0000, 0.0000, 0.3342, 3.3578]),
        (240, [-0.7313, 0.0000, 0.0215, 0.7125, 3.7768]),
    ],
    ".005-.02": [
        (8, [-0.6396, 0.0000, 0.0000, 0.0000, 0.6272]),
        (38, [-1.0281, 0.0000, 0.0000, 0.0887, 0.5628]),
        (90, [-1.0673, -0.1002, 0.0000, 0.1963, 1.7937]),
        (180, [-2.2032, -0.6818, 0.0000, 0.1571, 1.3656]),
        (240, [-2.5761, -0.8185, -0.1453, 0.0000, 1.9693]),
    ],
    ".02-.10": [
        (8, [-1.7096, -0.3877, 0.0000, 0.0000, 0.2976]),
        (38, [-1.6622, -0.6091, -0.1436, 0.0000, 0.7517]),
        (90, [-1.5640, -0.4523, -0.0463, 0.3390, 2.3128]),
        (180, [-1.5580, -0.5177, -0.0553, 0.5953, 2.6798]),
        (240, [-1.9651, -0.6604, -0.1746, 0.4216, 4.6566]),
    ],
    "x>=.10": [
        (8, [-0.9821, -0.1886, 0.0000, 0.3824, 1.8261]),
        (38, [-1.6463, -0.3807, 0.0366, 1.0102, 1.9506]),
        (90, [-0.6655, -0.1220, 0.2948, 0.8712, 2.6287]),
        (180, [-1.3153, -0.3559, 0.3013, 0.6812, 3.1266]),
        (240, [-2.0220, -0.5213, 0.5032, 1.7612, 3.4858]),
    ],
}
# Blend weight toward the per-x-bucket z (LOCO optimum, plateau 0.10-0.35).
XFAN_W = 0.20
XFAN_HC = [8, 38, 90, 180, 240]


def _xbucket(x):
    if x < 0.005:
        return "x<.005"
    if x < 0.02:
        return ".005-.02"
    if x < 0.10:
        return ".02-.10"
    return "x>=.10"


def _z_x_at(xb, h):
    """Interpolated per-x-bucket empirical z vector at horizon h."""
    tab = ZTABLE_X[xb]
    if h <= tab[0][0]:
        return tab[0][1]
    if h >= tab[-1][0]:
        return tab[-1][1]
    for (h0, z0), (h1, z1) in zip(tab, tab[1:]):
        if h0 <= h <= h1:
            f = (h - h0) / (h1 - h0)
            return [a + f * (b - a) for a, b in zip(z0, z1)]
    return tab[-1][1]


def _apply_xfan(out, case, P, fscale):
    """V9 Track D: blend v8's rows toward the per-x-bucket empirical fan.
    q_new = med + (1-w)*(q-med) + w*(z_x(h)*sh), applied AFTER deadband /
    d1 / gmom, with sh recomputed exactly as in forecast_market."""
    w = P.get("xfan_w", XFAN_W)
    if w == 0.0:
        return out
    new = {}
    for m in case["markets"]:
        pr = m["prices"]
        rows = out[m["id"]]
        if not pr:
            new[m["id"]] = rows
            continue
        n = len(pr)
        x = pr[-1]
        sigma1 = _sigma_capped(pr, P) * fscale
        sigma1 = sigma1 * P.get("fan_scale", 1.0)
        yb = P.get("young_boost", 0.0)
        if yb != 0.0:
            sigma1 = sigma1 * (1.0 + yb * math.exp(-n / P.get("young_tau", 100.0)))
        xb = _xbucket(x)
        nr = []
        for hi, row in enumerate(rows):
            h = hi + 1
            med = row[2]
            sh = sigma1 * math.sqrt(h) / math.sqrt(1.0 + h / P["h_sat"])
            # R10: same horizon-linear fan scale as forecast_market
            sh = sh * (1.0 + P.get("fan_h_lin", 0.0) * h / 240.0)
            zb = _z_x_at(xb, h)
            r2 = [price6(med + (1.0 - w) * (v - med) + w * (zz * sh))
                  for v, zz in zip(row, zb)]
            for j in range(1, 5):
                if r2[j] < r2[j - 1]:
                    r2[j] = r2[j - 1]
            nr.append(r2)
        new[m["id"]] = nr
    return new



def forecast_case(case, P=PARAMS):
    """Full forecast for one parsed case dict: {id: rows}."""
    horizon = case["horizon_minutes"]
    markets = case["markets"]
    # Board-sum adjustment, shared across markets in proportion to
    # x_i * sigma_i^pull_b (liquid markets absorb more of the sum gap).
    xs = []
    sigs = []
    for m in markets:
        pr = m["prices"]
        xs.append(pr[-1] if pr else 0.5)
        sigs.append(_sigma_capped(pr, P) if pr else 0.0)
    board_sum = sum(xs)
    if board_sum <= 0.0:
        board_sum = 1.0
    # regime scaling (round 4): V = the board's mean per-minute sigma at the
    # checkpoint; high V = launch/vol regime, low V = calm regime.
    # round-5 v_mode: "median" uses board median sigma; "recent" uses sigma
    # from the last 240 prices only (current regime, not full history).
    if P.get("v_mode", "mean") == "median":
        ss = sorted(sigs)
        vmean = ss[len(ss) // 2] if ss else 0.0
    elif P.get("v_mode", "mean") == "recent":
        rs = []
        for m in markets:
            pr = m["prices"]
            rs.append(_sigma_capped(pr[-240:], P) if pr else 0.0)
        vmean = sum(rs) / len(rs) if rs else 0.0
    else:
        vmean = sum(sigs) / len(sigs) if sigs else 0.0
    vmed = P["regime_vmed"]
    if P.get("rscale_tanh", 0):
        rscale = 1.0 + P["regime_pull"] * math.tanh((vmean - vmed) / vmed) if vmed > 0.0 else 1.0
    else:
        rscale = 1.0 + P["regime_pull"] * (vmean - vmed) / vmed if vmed > 0.0 else 1.0
    rscale = min(2.5, max(P.get("rscale_lo", 0.3), rscale))
    fscale = (vmean / vmed) ** P["regime_fan"] if vmean > 0.0 and vmed > 0.0 else 1.0
    fscale = min(2.0, max(0.5, fscale))
    gap = 1.0 - board_sum
    # gap trend (momentum): extrapolate the gap's last-trend_win-min change
    win = P["trend_win"]
    s_w = 0.0
    for m in markets:
        pr = m["prices"]
        s_w += pr[-(win + 1)] if len(pr) >= win + 1 else pr[0]
    gap_w = 1.0 - s_w
    gap = gap - P["c_trend"] * (gap - gap_w)
    # round-8 Track E: regime-gated pull exponent (gate=0 disables)
    pb_eff = P["pull_b"]
    gate = P.get("pull_b_gate", 0.0)
    if gate and rscale < gate:
        pb_eff = P.get("pull_b_calm", pb_eff)
    # R10: per-x-bucket pull exponent (bucket value >= 0 overrides pb_eff)
    def _pb_for(x):
        if x < 0.01:
            v = P.get("pb_lo", -1.0)
        elif x < 0.1:
            v = P.get("pb_mid", -1.0)
        else:
            v = P.get("pb_hi", -1.0)
        return v if (v is not None and v >= 0.0) else pb_eff
    raw = [max(x, 1e-9) * max(s, 1e-9) ** _pb_for(x)
           for x, s in zip(xs, sigs)]
    # round-5 staleness weights (Gemini idea 1)
    if P.get("stale_w", 0.0) != 0.0:
        for i, m in enumerate(markets):
            pr = m["prices"]
            if len(pr) >= 2:
                win = pr[-241:]
                zf = sum(1 for a, b in zip(win, win[1:]) if a == b) / max(1, len(win) - 1)
                raw[i] = raw[i] * (max(zf, 1e-3) ** P["stale_w"])
    wsum = sum(raw)
    # round-5 pull target modes (Gemini idea 3)
    tmode = P.get("target_mode", "weighted")
    targets = None
    if tmode == "logit":
        def _sig(z):
            return 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0
        lg = []
        for x in xs:
            xc = min(0.999999, max(1e-6, x))
            lg.append(math.log(xc / (1.0 - xc)))
        lo, hi = -3.0, 3.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            s = sum(_sig(g - mid) for g in lg)
            if s > 1.0:
                lo = mid
            else:
                hi = mid
        c = 0.5 * (lo + hi)
        targets = [_sig(g - c) for g in lg]
    elif tmode == "linear":
        targets = [x / board_sum for x in xs]
    out = {}
    adjs = []
    for mi, (m, r) in enumerate(zip(markets, raw)):
        adj_w = (r / wsum) * gap if wsum > 0.0 else 0.0
        if targets is not None:
            adj_t = targets[mi] - xs[mi]
            gk = P.get("target_gate_k", 0.0)
            if gk > 0.0:
                g = min(1.0, max(0.0, gk * (rscale - 1.0)))
                adj = (1.0 - g) * adj_w + g * adj_t
            else:
                adj = adj_t
        else:
            adj = adj_w
        if gap > 0:
            adj = adj * P["k_up"]
        elif gap < 0:
            adj = adj * P["k_down"]
        adjs.append(adj)
    # round-7 size-dependent pull response (off = v6 exactly)
    if P.get("size_mult_on", 0):
        s_pre = sum(adjs)
        for mi in range(len(adjs)):
            xx = xs[mi]
            if xx >= 0.1:
                sm = P.get("size_mult_hi", 1.0)
            elif xx >= 0.01:
                sm = P.get("size_mult_mid", 1.0)
            else:
                lo_u = P.get("size_mult_lo_up", -1.0)
                lo_d = P.get("size_mult_lo_dn", -1.0)
                if gap > 0 and lo_u >= 0.0:
                    sm = lo_u
                elif gap < 0 and lo_d >= 0.0:
                    sm = lo_d
                else:
                    sm = P.get("size_mult_lo", 1.0)
            adjs[mi] = adjs[mi] * sm
        if P.get("size_realloc", 0):
            s_post = sum(adjs)
            if abs(s_post) > 1e-12:
                f = s_pre / s_post
                adjs = [a * f for a in adjs]
    for mi, m in enumerate(markets):
        out[m["id"]] = forecast_market(m["prices"], horizon, adjs[mi], P, rscale, fscale)
    return _apply_stale_inner(_apply_xfan(_apply_gmom(_apply_d1(_apply_deadband(out, case, P), case, P, rscale), case, P, rscale), case, P, fscale), case, P)


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    for fname in sorted(os.listdir(in_dir)):
        if not fname.endswith(".in"):
            continue
        cid = fname[:-3]
        with open(os.path.join(in_dir, fname), "r", encoding="utf-8") as f:
            case = json.load(f)
        fc = forecast_case(case)
        forecasts = [{"id": mid, "q": rows}
                     for mid, rows in fc.items()]
        with open(os.path.join(out_dir, cid + ".out"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"forecasts": forecasts}) + "\n")


if __name__ == "__main__":
    main()
