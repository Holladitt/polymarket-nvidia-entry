#!/usr/bin/env python3
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
  * v5 changes (round 5, practice 0.236538 -> 0.222954; top-10 bar ~0.231;
    calm p04/p05 mean 0.130397 -> 0.128383 — see NOTES.md):
    - REGIME-GATED TWO-TIMESCALE PULL: pull(h) gains a fast component
      (tau ~15 min) gated by regime, w_f_eff = 1.0*clip(2.7*(rscale-1),0,1),
      so only volatile/launch regimes pull fast; calm cases keep v4's
      slow pull exactly (calm score unchanged by this mechanism alone).
      EDA: the true pull response is fast early (OLS slope 0.27 at h<=15)
      while v4's single exp(-h/111) gives only 0.06 there.
    - REGIME-GATED LINEAR SHARE TARGET: in volatile regimes the pull
      converges to the pure board-sum-normalised share (adj = x/sum - x)
      instead of the x*sigma-weighted gap share; blended by regime,
      g = clip(1.93*(rscale-1),0,1). v4's weighted allocation misallocates
      the gap when sigma varies wildly across markets (launch). p00
      improves 0.3486 -> 0.2766; other cases neutral-to-better.
    - EMPIRICAL-Z FAN BLEND (0.56): Gaussian z blended toward the pooled
      empirical quantiles of (y-med)/sigma(h) by horizon bucket; the
      residual distribution is narrower and asymmetric vs Gaussian
      (q25 -0.24 vs -0.674, q75 +0.06 vs +0.674; q95 grows with h).
    - k_down 1.61 -> 1.9, k_up 0.425 -> 0.32.
    Rejected in round 5: vol-trend fan scaling, v_mode median/recent,
    regime-scaled give-back, two-timescale give-back (helps calm only),
    z_lo/z_hi asymmetry, per-market tick deadband (marginal), staleness
    weights >0.5, target logit (similar to linear, slightly worse).
  * v6 changes (round 6, CONSERVATIVE version, practice 0.222954 -> 0.222196;
    calm 0.128383 -> 0.127977). Only three surgical changes on top of v5,
    each with its own out-of-sample evidence; everything else is v5 exactly:
    - rscale floor 0.3 -> 0.6 (sweep 0.45-1.0, optimum ~0.6; nested LOCO:
      train-best lo=0.6 in 4/6 folds (p04: 0.4, p05: 0.7), held-out
      still better at 0.6).
    - Z-table + h=240 row ([-1.96, -0.483, 0, 0.387, 3.405] from v5
      residuals): tails keep growing with h; old table clamped h>180.
      Ablation: removing it costs +0.000173 mean, v6 wins 5/6 folds.
    - trend_win 60 -> 30 (Box LOCO + local sweep 15-90, plateau 25-30):
      gain -0.00046 mean, driven by p01 (-0.0028).
    REJECTED for submission (in-sample only, see NOTES.md): the full
    30-param coordinate-descent polish (0.220954 in-sample). Nested LOCO
    refit: 0.228065 held-out vs v5 0.222763 — the polish overfits and would
    likely score WORSE than v5 on unseen cases. Same verdict independently
    from the Box lane (CD 0.221405 -> LOCO 0.233003).
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
    "h_sat": 14.05249,
    # quantile shape: widen the outer pair for fat tails
    "tail_wide": 1.065585,
    "mid_wide": 0.994842,
    # horizon-linear outer-tail widening (round 4): outer width x (1 + tail_lin*h/240)
    "tail_lin": 0.217931,
    # median: pull toward sum-normalised share, strength pull_max*(1-exp(-h/pull_tau))
    "pull_max": 0.931198,
    "pull_tau": 161.241351,
    # pull weight: w_i propto x_i * sigma_i^pull_b, so liquid markets absorb
    # more of the board-sum adjustment (pull_b=0 is the old x_i-only weight)
    "pull_b": 1.0,
    # asymmetric pull: scale the pull when the board is under-priced
    # (gap > 0, sum < 1) vs over-priced (gap < 0, sum > 1)
    "k_up": 0.318601,
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
    "c_trend": -0.126502,
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
    "db_spread": 0.975461,
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
    # ROUND 5 (Gemini ideas): per-market deadband. "flat" = v4 (global
    # db_eps); "tick" = eps_i = db_tick_k * median nonzero |1-min change|
    # over the market's last 240 prices (fallback: global db_eps).
    "db_mode": "flat",
    "db_tick_k": 1.0,
    # ROUND 5: regime variable definition. "mean" = v4 (board mean sigma);
    # "median" = board median sigma; "recent" = sigma from last 240 prices.
    "v_mode": "mean",
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
        ze = _z_emp(h)
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
    if P.get("db_mode", "flat") == "tick":
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
    raw = [max(x, 1e-9) * max(s, 1e-9) ** P["pull_b"]
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
        out[m["id"]] = forecast_market(m["prices"], horizon, adj, P, rscale, fscale)
    return _apply_deadband(out, case, P)


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
