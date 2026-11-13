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
    "h_sat": 12.0,
    # quantile shape: widen the outer pair for fat tails
    "tail_wide": 1.35,
    "mid_wide": 0.8,
    # horizon-linear outer-tail widening (round 4): outer width x (1 + tail_lin*h/240)
    "tail_lin": 0.1,
    # median: pull toward sum-normalised share, strength pull_max*(1-exp(-h/pull_tau))
    "pull_max": 0.9,
    "pull_tau": 111.0,
    # pull weight: w_i propto x_i * sigma_i^pull_b, so liquid markets absorb
    # more of the board-sum adjustment (pull_b=0 is the old x_i-only weight)
    "pull_b": 1.0,
    # asymmetric pull: scale the pull when the board is under-priced
    # (gap > 0, sum < 1) vs over-priced (gap < 0, sum > 1)
    "k_up": 0.425,
    "k_down": 1.61,
    # regime scaling (round 4): the board's mean EWMA sigma V measures the
    # volatility regime at the checkpoint; Vmed is its practice median.
    # pull strength x (1 + regime_pull*(V-Vmed)/Vmed), clipped to [0.3, 2.5];
    # sigma x (V/Vmed)^regime_fan, clipped to [0.5, 2.0]. In launch regimes
    # the pull is stronger and the fan wider; in calm regimes both shrink.
    "regime_pull": 1.7,
    "regime_vmed": 0.0026960411939506426,
    "regime_fan": 0.5,
    # gap trend: gap_used = gap - c_trend * (gap - gap_60min_ago);
    # c_trend < 0 EXTRAPOLATES the recent gap change (gap momentum)
    "c_trend": -0.2,
    "trend_win": 60,
    # pull tilt across quantiles: pull displacement x (1 - kappa*z)
    "kappa": 0.15,
    # median: give-back of the last-60-min run-up, strength gb*(1-exp(-h/gb_tau))
    "gb_up": 0.35,           # recent rise gives back
    "gb_dn": 0.0,            # recent fall bounces back ~nothing (measured)
    "gb_tau": 90.0,
    # deadband: median displacement < db_eps is set to exactly the last
    # price, and the fan around it is compressed by db_spread
    "db_eps": 0.001,
    "db_spread": 0.85,
}


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
    # median targets
    r60 = x - prices[-61] if n >= 61 else x - prices[0]
    up = r60 if r60 > 0.0 else 0.0
    dn = r60 if r60 < 0.0 else 0.0
    rows = []
    for h in range(1, horizon + 1):
        pull = P["pull_max"] * rscale * (1.0 - math.exp(-h / P["pull_tau"]))
        gb = (1.0 - math.exp(-h / P["gb_tau"]))
        gb_disp = gb * (P["gb_up"] * up + P["gb_dn"] * dn)
        sh = sigma1 * math.sqrt(h) / math.sqrt(1.0 + h / P["h_sat"])
        row = []
        for j, z in enumerate(Z):
            if j in (0, 4):
                w = P["tail_wide"] * (1.0 + P["tail_lin"] * h / 240.0)
            else:
                w = P["mid_wide"]
            # pull tilt: lower tail moves more with the pull than upper tail
            pd = pull * adj * (1.0 - P["kappa"] * z)
            row.append(price6(x + pd - gb_disp + z * w * sh))
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
    new = {}
    for mid, rows in out.items():
        x = xs[mid]
        nr = []
        for row in rows:
            med = row[2]
            if abs(med - x) < eps:
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
    vmean = sum(sigs) / len(sigs) if sigs else 0.0
    vmed = P["regime_vmed"]
    rscale = 1.0 + P["regime_pull"] * (vmean - vmed) / vmed if vmed > 0.0 else 1.0
    rscale = min(2.5, max(0.3, rscale))
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
    wsum = sum(raw)
    out = {}
    for m, r in zip(markets, raw):
        adj = (r / wsum) * gap if wsum > 0.0 else 0.0
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
