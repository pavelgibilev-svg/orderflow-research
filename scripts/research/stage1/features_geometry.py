"""
features_geometry.py  --  Stage 1, ТЗ §4.1 / §4.2  (+ deformation speed).

Continuous order-book GEOMETRY features for Bybit / OKX L2 snapshots.

Pure NumPy. Zero-lookahead by construction: every feature uses ONLY the
current snapshot; deformation uses the current vs a strictly PAST snapshot.

Three layers
------------
1. book_geometry_snapshot(...)  - reference, ONE reconstructed snapshot.
   This is the bit-exact contract handed to Participant A (TS engine) and the
   generator for feature_test_vectors.json (§6). Keep this readable, not clever.

2. book_geometry_batch(...)     - vectorized over MANY snapshots (one side) via
   np.add.reduceat. The millions-of-rows path (§7 perf). Must match (1) to 1e-9.

3. book_deformation(...)        - rate-of-change between two snapshots (#4 of the
   Шаг-1 list: "скорость деформации стакана").

Input contract
--------------
A "snapshot" is an ALREADY-RECONSTRUCTED full book slice (snapshot+delta replay
is the separate book_reconstruction.py module). Each side is an array-like of
[price, size] rows. Price in quote (USD). Size in EXCHANGE-NATIVE units.

Units / normalization
---------------------
- Bybit BTCUSDT, spot AND perp: size is already in BTC  -> size_multiplier = 1.0.
- OKX *-SWAP: size is in CONTRACTS -> size_multiplier = contract size in BTC
  (ctVal from GET /api/v5/public/instruments). Math is identical once multiplied.

Timestamps
----------
ts is in MILLISECONDS (this recorder; NOT the microseconds §3.1 assumed).
orderbook.200 on Bybit pushes ~every 100 ms, so a "tick" ~= 100 ms; always use
the real ts delta for deformation, never a fixed cadence (gaps happen).
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

# Numerical floor: below this a side's mass is treated as empty.
EPS = 1e-12

# Defaults from ТЗ §6 metadata.
DEFAULT_MAX_DEPTH_PCT = 0.005   # window half-width = 0.5% of mid
DEFAULT_EXP_LAMBDA = 10.0       # exp-decay scale, in ticks (imbalance B)


@dataclass(frozen=True)
class SideGeometry:
    """Geometry of one side (bid OR ask) within the depth window."""
    mass: float        # M_side : total volume in window, BTC
    com_ticks: float   # mu_side: volume-weighted mean distance from mid, ticks
    variance: float    # sigma^2: volume-weighted variance of distance, ticks^2
    n_levels: int      # number of price levels inside the window
    empty: bool        # True  -> flag empty_book_<side> (M == 0)
    w_inv: float       # Sum v/(1+d)       -> imbalance A numerator term
    w_exp: float       # Sum v*exp(-d/lam) -> imbalance B numerator term


@dataclass(frozen=True)
class BookGeometry:
    """Full per-snapshot geometry result."""
    ts: int
    best_bid: float
    best_ask: float
    mid: float
    spread_ticks: float
    bid: SideGeometry
    ask: SideGeometry
    imbalance_inv: float   # (Wbid - Wask)/(Wbid + Wask), near-weighted  (>0 = bid-heavy)
    imbalance_exp: float   # same, exponential decay weighting

    def to_test_vector(self, ndigits: int = 6) -> dict:
        """Flat dict with the §6 field names, rounded for the JSON contract."""
        def r(x: float) -> float:
            return round(float(x), ndigits)
        return {
            "mass_bid": r(self.bid.mass),
            "com_bid_ticks": r(self.bid.com_ticks),
            "variance_bid": r(self.bid.variance),
            "mass_ask": r(self.ask.mass),
            "com_ask_ticks": r(self.ask.com_ticks),
            "variance_ask": r(self.ask.variance),
            "imbalance_inv": r(self.imbalance_inv),
            "imbalance_exp": r(self.imbalance_exp),
        }


# --------------------------------------------------------------------------- #
# Layer 1 — single-snapshot reference (THE contract)                          #
# --------------------------------------------------------------------------- #

def _side_geometry(
    prices: np.ndarray,
    sizes: np.ndarray,
    mid: float,
    tick_size: float,
    max_depth_pct: float,
    size_multiplier: float,
    exp_lambda: float,
) -> SideGeometry:
    """
    Geometric moments of one side.

        d_i  = |price_i - mid| / tick_size              (distance, ticks)
        v_i  = size_i * size_multiplier                 (volume, BTC)
        M    = Sum v_i
        mu   = Sum d_i v_i / M
        var  = Sum (d_i - mu)^2 v_i / M
             = Sum d_i^2 v_i / M  -  mu^2               (computational form)

    Window: keep level i iff |price_i - mid| / mid <= max_depth_pct.
    Edge: M == 0  -> {mass:0, com:NaN, var:NaN, empty:True}.
    """
    if prices.size == 0:
        return SideGeometry(0.0, np.nan, np.nan, 0, True, 0.0, 0.0)

    v_all = sizes * size_multiplier
    dist_abs = np.abs(prices - mid)
    in_win = dist_abs <= (max_depth_pct * mid)
    n = int(in_win.sum())
    if n == 0:
        return SideGeometry(0.0, np.nan, np.nan, 0, True, 0.0, 0.0)

    d = dist_abs[in_win] / tick_size
    v = v_all[in_win]
    M = float(v.sum())
    if M <= EPS:
        return SideGeometry(0.0, np.nan, np.nan, n, True, 0.0, 0.0)

    com = float((d * v).sum() / M)
    var = float((d * d * v).sum() / M - com * com)
    var = var if var > 0.0 else 0.0  # clamp tiny negative roundoff
    w_inv = float((v / (1.0 + d)).sum())
    w_exp = float((v * np.exp(-d / exp_lambda)).sum())
    return SideGeometry(M, com, var, n, False, w_inv, w_exp)


def book_geometry_snapshot(
    bids,
    asks,
    *,
    tick_size: float,
    ts: int = 0,
    max_depth_pct: float = DEFAULT_MAX_DEPTH_PCT,
    exp_lambda: float = DEFAULT_EXP_LAMBDA,
    size_multiplier: float = 1.0,
) -> BookGeometry:
    """
    Reference geometry for one reconstructed snapshot.

    Parameters
    ----------
    bids, asks : array-like of [price, size] rows (any order; best is found by
                 max bid / min ask). Sizes in exchange-native units.
    tick_size  : instrument tick (Bybit BTCUSDT = 0.1).
    """
    bids = np.asarray(bids, dtype=np.float64).reshape(-1, 2)
    asks = np.asarray(asks, dtype=np.float64).reshape(-1, 2)

    best_bid = float(bids[:, 0].max()) if bids.size else np.nan
    best_ask = float(asks[:, 0].min()) if asks.size else np.nan
    mid = (best_bid + best_ask) / 2.0
    spread_ticks = (best_ask - best_bid) / tick_size if np.isfinite(mid) else np.nan

    bid = _side_geometry(bids[:, 0], bids[:, 1], mid, tick_size,
                         max_depth_pct, size_multiplier, exp_lambda)
    ask = _side_geometry(asks[:, 0], asks[:, 1], mid, tick_size,
                         max_depth_pct, size_multiplier, exp_lambda)

    denom_inv = bid.w_inv + ask.w_inv
    denom_exp = bid.w_exp + ask.w_exp
    imb_inv = (bid.w_inv - ask.w_inv) / denom_inv if denom_inv > EPS else np.nan
    imb_exp = (bid.w_exp - ask.w_exp) / denom_exp if denom_exp > EPS else np.nan

    return BookGeometry(int(ts), best_bid, best_ask, mid, float(spread_ticks),
                        bid, ask, float(imb_inv), float(imb_exp))


# --------------------------------------------------------------------------- #
# Layer 2 — batched, millions of rows (one side per call)                     #
# --------------------------------------------------------------------------- #

def book_geometry_batch(
    prices: np.ndarray,
    sizes: np.ndarray,
    seg_starts: np.ndarray,
    mid: np.ndarray,
    *,
    tick_size: float,
    max_depth_pct: float = DEFAULT_MAX_DEPTH_PCT,
    exp_lambda: float = DEFAULT_EXP_LAMBDA,
    size_multiplier: float = 1.0,
) -> dict:
    """
    Vectorized geometry for ONE side over S snapshots, via np.add.reduceat.

    The levels of all S snapshots are concatenated into flat `prices`/`sizes`;
    `seg_starts[k]` is the row index where snapshot k begins. This is the
    "ragged → flat + segment-reduce" pattern: no Python loop over snapshots,
    O(total_levels) work, which is what the millions-of-rows requirement needs.

    Parameters
    ----------
    prices, sizes : 1D float arrays (length n = total levels across snapshots).
    seg_starts    : 1D int array (length S), strictly increasing, seg_starts[0]==0.
    mid           : 1D float array (length S), mid price per snapshot.

    Returns
    -------
    dict of 1D arrays length S: mass, com_ticks, variance, w_inv, w_exp, n_levels.
    Out-of-window levels are zero-weighted (rows kept so reduceat segments stay
    well-formed). Degenerate segments (M<=EPS) -> mass 0, com/var NaN.

    Call once per side, then combine w_inv / w_exp for the two imbalances:
        imb_inv = (b["w_inv"] - a["w_inv"]) / (b["w_inv"] + a["w_inv"])
    """
    prices = np.asarray(prices, np.float64)
    sizes = np.asarray(sizes, np.float64) * size_multiplier
    seg_starts = np.asarray(seg_starts, np.int64)
    mid = np.asarray(mid, np.float64)
    n = prices.size

    seg_len = np.diff(np.append(seg_starts, n))
    mid_rows = np.repeat(mid, seg_len)

    dist_abs = np.abs(prices - mid_rows)
    in_win = dist_abs <= (max_depth_pct * mid_rows)
    d = np.where(in_win, dist_abs / tick_size, 0.0)
    v = np.where(in_win, sizes, 0.0)

    def seg_sum(a: np.ndarray) -> np.ndarray:
        return np.add.reduceat(a, seg_starts)

    M = seg_sum(v)
    dv = seg_sum(d * v)
    d2v = seg_sum(d * d * v)
    w_inv = seg_sum(v / (1.0 + d))                 # out-of-win: v=0 -> term 0
    w_exp = seg_sum(v * np.exp(-d / exp_lambda))   # out-of-win: v=0 -> term 0
    n_levels = seg_sum(in_win.astype(np.int64))

    Msafe = np.where(M > EPS, M, np.nan)           # -> NaN com/var for empty sides
    com = dv / Msafe
    var = np.maximum(d2v / Msafe - com * com, 0.0)
    mass = np.where(M > EPS, M, 0.0)

    return {"mass": mass, "com_ticks": com, "variance": var,
            "w_inv": w_inv, "w_exp": w_exp, "n_levels": n_levels}


# --------------------------------------------------------------------------- #
# Layer 3 — deformation speed (#4)                                            #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BookDeformation:
    """Per-second rates of change between two consecutive snapshots."""
    dt_s: float
    dmass_bid_dt: float
    dmass_ask_dt: float
    dcom_bid_dt: float
    dcom_ask_dt: float
    dvar_bid_dt: float
    dvar_ask_dt: float
    deformation_speed: float   # ticks/s: Euclidean speed of (com_bid, com_ask)


def book_deformation(prev: BookGeometry, curr: BookGeometry) -> BookDeformation:
    """
    Rate of change of the geometry between a PAST snapshot `prev` and `curr`.

    All rates are per SECOND using the real ts gap (ms -> s). The headline
    `deformation_speed` is the Euclidean speed of the centroid point
    (com_bid, com_ticks ; com_ask, com_ticks) in tick-space:

        speed = sqrt( (d com_bid/dt)^2 + (d com_ask/dt)^2 )   [ticks/s]

    i.e. how fast the bid/ask "walls" slide toward or away from mid. Mass flux
    (dmass_*/dt) and variance rate (dvar_*/dt) are returned separately so the
    ablation in §5.1 can test each channel. NaN propagates from empty sides;
    non-monotonic / duplicate ts -> all-NaN (undefined rate).
    """
    dt_s = (curr.ts - prev.ts) / 1000.0
    if not dt_s > 0.0:
        nan = float("nan")
        return BookDeformation(dt_s, nan, nan, nan, nan, nan, nan, nan)

    dMb = (curr.bid.mass - prev.bid.mass) / dt_s
    dMa = (curr.ask.mass - prev.ask.mass) / dt_s
    dCb = (curr.bid.com_ticks - prev.bid.com_ticks) / dt_s
    dCa = (curr.ask.com_ticks - prev.ask.com_ticks) / dt_s
    dVb = (curr.bid.variance - prev.bid.variance) / dt_s
    dVa = (curr.ask.variance - prev.ask.variance) / dt_s
    speed = float(np.hypot(dCb, dCa))
    return BookDeformation(dt_s, dMb, dMa, dCb, dCa, dVb, dVa, speed)
