#!/usr/bin/env python3
"""
research_validation.py  --  Stage 1 §5.2: the "imbalance duel" (v2).

WHAT IT DOES
    Given 1-second day CSV(s) carrying two continuous order-book imbalance
    versions (`imbalance_inv` ~ 1/(1+d), `imbalance_exp` ~ exp(-d/lambda)), it
    measures which version better separates moments just BEFORE local price
    reversals from volatility-matched neutral controls (Cohen's d).

    v2 adds, on top of v1:
      1. Tautology test — feature at the reversal t* vs at t*-90s (still in the
         directional move, extremum not reached). Three comparisons:
           - Reversals vs Controls       (original)
           - Reversals vs TautologyPoints (specificity of the extremum) -- MAIN
           - TautologyPoints vs Controls  (cross-check)
      2. Multi-day runner — per-day d + pooled d + inter-day std, regime map.
      3. Sanity — top-N reversals per day by |swing_pct|.

WHAT COUNTS AS A "REVERSAL"
    Hybrid sliding-window extremum + min-swing magnitude filter + min separation
    (a ZigZag pivot). direction "up" = a local low that reverses up.

WHY MATCHED CONTROL
    Avoid a false signal that is really just active-vs-quiet market: each
    reversal is compared against random points of the SAME realized volatility.

WHY TAUTOLOGY TEST
    A feature that separates reversals from controls might only be tracking the
    directional flow, not the extremum. If it separates EQUALLY well at t*-90s,
    that is tautological. |d(Reversals vs Tautology)| < 0.20 => TAUTOLOGY.

Usage
    Single day (legacy positional still works):
        python research_validation.py path/to/CSV [output_dir]
        python research_validation.py --single path/to/CSV [--output-dir DIR]
    Multiday:
        python research_validation.py --multiday --input-dir DIR --output-dir DIR
    (--input-dir: every *.csv whose name contains YYYY-MM-DD.)

Verdict (aggregate)
    |d(R vs T)| < 0.20  -> TAUTOLOGY_ARTIFACT (tracks directional flow)
    inter-day std > 0.30 or sign flips -> REGIME_DEPENDENT (defer)
    |d(R vs T)| > 0.30 & stable & sign-consistent -> ROBUST_CONTRARIAN_SIGNAL
    otherwise -> BORDERLINE

Reference: §5.2 of the Stage-1 TZ. Does NOT recompute the imbalances, does NOT
compare to old bucket features (§5.1 ablation), does NOT pass a strategy verdict.
Reproducible given the same CSV(s) and RANDOM_SEED.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

try:
    from scipy import stats as _scipy_stats
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception:
    HAVE_MPL = False

ROOT = next((p for p in Path(__file__).resolve().parents
             if (p / "package.json").exists() and (p / "scripts").exists()),
            Path(__file__).resolve().parent)

CONFIG = {
    "W_REVERSAL_WINDOW_SEC": 60,
    "MIN_SWING_PCT": 0.003,
    "MIN_SEPARATION_SEC": 60,
    "FEATURE_WINDOW_SEC": 30,
    "VOL_WINDOW_SEC": 300,
    "CONTROL_VOL_TOLERANCE": 0.20,
    "CONTROL_VOL_TOLERANCE_FALLBACK": 0.40,
    "N_CONTROL_PER_REVERSAL": 5,
    "MIN_CONTROLS_REQUIRED": 3,
    "RANDOM_SEED": 42,
    "BOOTSTRAP_ITERATIONS": 2000,
    # v2
    "TAUTOLOGY_SHIFT_SEC": 90,
    "TAUTOLOGY_D_THRESHOLD": 0.20,      # |d| < this -> tautology
    "TAUTOLOGY_D_SPECIFIC": 0.30,       # |d| > this -> extremum-specific
    "INTER_DAY_STD_WARN": 0.30,         # std(per-day d) > this -> regime dependence
    "SANITY_TOP_N": 3,
    # logical_name -> actual_csv_column
    "COLUMNS": {
        "timestamp_ms": "ts",
        "mid_price": "mid",
        "imbalance_inv": "imbalance_inv",
        "imbalance_exp": "imbalance_exp",
    },
}

# Read-only, filled by hand from market context (no false automation).
REGIME_MAP = {
    "2025-10-10": "post-ATH distribution",
    "2025-10-11": "post-ATH distribution",
    "2025-10-12": "post-ATH distribution",
    "2026-06-02": "bear continuation",
    "2026-06-03": "bear continuation",
    "2026-06-04": "bear continuation",
    "2026-06-05": "bear continuation",
    "2026-06-06": "bear continuation",
}

FEATS = ("imbalance_inv", "imbalance_exp")
SHORT = {"imbalance_inv": "inv", "imbalance_exp": "exp"}


@dataclass
class Reversal:
    timestamp_ms: int
    idx: int
    price: float
    direction: str            # "up" (low -> reverses up) / "down"
    swing_pct: float


@dataclass
class Control:
    timestamp_ms: int
    idx: int
    parent_reversal_idx: int
    direction: str
    vol: float


# --------------------------------------------------------------------------- #
# Load                                                                        #
# --------------------------------------------------------------------------- #

def load_data(csv_path: str) -> pd.DataFrame:
    col = CONFIG["COLUMNS"]
    df = pd.read_csv(csv_path, usecols=list(col.values()))
    df = df.rename(columns={v: k for k, v in col.items()})
    df = df.sort_values("timestamp_ms").reset_index(drop=True)
    df["timestamp_ms"] = df["timestamp_ms"].astype("int64")
    for c in ("mid_price", "imbalance_inv", "imbalance_exp"):
        df[c] = df[c].astype("float64")
    return df


# --------------------------------------------------------------------------- #
# Step 1 — hybrid reversal labeling                                           #
# --------------------------------------------------------------------------- #

def find_reversals(prices, ts, W, min_swing, min_sep_sec) -> list[Reversal]:
    n = prices.size
    L = 2 * W + 1
    if n < L:
        return []
    win = sliding_window_view(prices, L)
    rmax = win.max(axis=1)
    rmin = win.min(axis=1)
    centers = np.arange(W, n - W)
    pc = prices[centers]
    is_high = pc == rmax
    is_low = pc == rmin
    flat = is_high & is_low

    cands = []
    for k in range(centers.size):
        if flat[k]:
            continue
        c = int(centers[k])
        if is_high[k]:
            cands.append((c, "high", float(prices[c])))
        elif is_low[k]:
            cands.append((c, "low", float(prices[c])))

    pivots: list[list] = []
    for c, typ, price in cands:
        if not pivots:
            pivots.append([c, typ, price])
            continue
        last = pivots[-1]
        if typ == last[1]:
            if (typ == "high" and price > last[2]) or (typ == "low" and price < last[2]):
                pivots[-1] = [c, typ, price]
        else:
            if abs(price - last[2]) / last[2] >= min_swing:
                pivots.append([c, typ, price])

    min_sep_ms = min_sep_sec * 1000
    changed = True
    while changed and len(pivots) >= 3:
        changed = False
        for i in range(len(pivots) - 2):
            a, b = pivots[i], pivots[i + 2]
            if a[1] == b[1] and (ts[b[0]] - ts[a[0]]) < min_sep_ms:
                keep_a = (a[1] == "high" and a[2] >= b[2]) or (a[1] == "low" and a[2] <= b[2])
                if keep_a:
                    del pivots[i + 1:i + 3]
                else:
                    del pivots[i:i + 2]
                changed = True
                break

    reversals: list[Reversal] = []
    for i, (c, typ, price) in enumerate(pivots):
        if i >= 1:
            prev_price = pivots[i - 1][2]
        elif len(pivots) > 1:
            prev_price = pivots[1][2]
        else:
            prev_price = price
        swing_pct = abs(price - prev_price) / prev_price if prev_price else 0.0
        reversals.append(Reversal(int(ts[c]), c, price,
                                  "up" if typ == "low" else "down", swing_pct))
    return reversals


# --------------------------------------------------------------------------- #
# Realized volatility + matched control                                       #
# --------------------------------------------------------------------------- #

def compute_vol_grid(prices, window) -> np.ndarray:
    n = prices.size
    vol = np.full(n, np.nan)
    r = np.diff(np.log(prices))
    if r.size < window:
        return vol
    sw = sliding_window_view(r, window)
    std_sw = sw.std(axis=1, ddof=1)
    vol[window:window + std_sw.size] = std_sw
    return vol


def build_excluded_mask(reversals, n, W) -> np.ndarray:
    excl = np.zeros(n, dtype=bool)
    for r in reversals:
        excl[max(0, r.idx - W):min(n, r.idx + W + 1)] = True
    return excl


def sample_matched_controls(reversals, ts, vol, excluded, n, cfg):
    W = cfg["W_REVERSAL_WINDOW_SEC"]
    VOL = cfg["VOL_WINDOW_SEC"]
    FW = cfg["FEATURE_WINDOW_SEC"]
    n_target = cfg["N_CONTROL_PER_REVERSAL"]
    min_req = cfg["MIN_CONTROLS_REQUIRED"]
    tol0 = cfg["CONTROL_VOL_TOLERANCE"]
    tol1 = cfg["CONTROL_VOL_TOLERANCE_FALLBACK"]
    rng = np.random.default_rng(cfg["RANDOM_SEED"])

    valid = np.zeros(n, dtype=bool)
    valid[VOL:max(VOL, n - FW)] = True
    valid &= np.isfinite(vol)
    base_ok = valid & ~excluded

    used: set[int] = set()
    controls: list[Control] = []
    fallback_count = 0
    skipped: list[dict] = []

    for rev in reversals:
        vol_ref = vol[rev.idx]
        if not np.isfinite(vol_ref) or vol_ref <= 0:
            skipped.append({"timestamp_ms": rev.timestamp_ms, "idx": rev.idx, "reason": "no_vol_ref"})
            continue

        def pool_for(tol):
            lo, hi = (1 - tol) * vol_ref, (1 + tol) * vol_ref
            idxs = np.where(base_ok & (vol >= lo) & (vol <= hi))[0]
            return np.array([int(i) for i in idxs if int(i) not in used], dtype=int)

        pool = pool_for(tol0)
        used_fallback = False
        if pool.size < n_target:
            pool_fb = pool_for(tol1)
            if pool_fb.size > pool.size:
                pool, used_fallback = pool_fb, True

        if pool.size < min_req:
            skipped.append({"timestamp_ms": rev.timestamp_ms, "idx": rev.idx,
                            "reason": f"insufficient_controls({pool.size})"})
            continue

        chosen = rng.choice(pool, size=min(n_target, pool.size), replace=False)
        for ci in chosen:
            ci = int(ci)
            used.add(ci)
            controls.append(Control(int(ts[ci]), ci, rev.idx, rev.direction, float(vol[ci])))
        if used_fallback:
            fallback_count += 1

    return controls, fallback_count, skipped


# --------------------------------------------------------------------------- #
# Features, sign alignment, effect size                                       #
# --------------------------------------------------------------------------- #

def feature_mean(feat, idx, window) -> float:
    w = feat[max(0, idx - window):idx + 1]
    w = w[np.isfinite(w)]                       # ignore NaN seconds (e.g. exp underflow at high price)
    return float(w.mean()) if w.size else float("nan")


def sign_of(direction) -> int:
    return 1 if direction == "up" else -1


def _finite_mean(x) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else float("nan")


def cohen_d(a, b) -> float:
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return float("nan")
    pooled = ((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2)
    s = np.sqrt(pooled)
    return float((np.mean(a) - np.mean(b)) / s) if s else float("nan")


def cohen_d_ci_bootstrap(a, b, n_iter, seed):
    rng = np.random.default_rng(seed)
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return float("nan"), float("nan")
    ds = np.empty(n_iter)
    for i in range(n_iter):
        ds[i] = cohen_d(a[rng.integers(0, na, na)], b[rng.integers(0, nb, nb)])
    ds = ds[np.isfinite(ds)]
    if ds.size == 0:
        return float("nan"), float("nan")
    return float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5))


def t_test(a, b):
    if a.size < 2 or b.size < 2:
        return float("nan"), float("nan")
    if HAVE_SCIPY:
        t, p = _scipy_stats.ttest_ind(a, b, equal_var=True)
        return float(t), float(p)
    na, nb = a.size, b.size
    pooled = ((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2)
    se = np.sqrt(pooled * (1 / na + 1 / nb))
    from math import erfc, sqrt
    t = (np.mean(a) - np.mean(b)) / se if se else float("nan")
    return float(t), float(erfc(abs(t) / sqrt(2.0)))


def compare(a, b, seed, n_iter) -> dict:
    a = np.asarray(a, float); a = a[np.isfinite(a)]     # drop NaN points (undefined feature)
    b = np.asarray(b, float); b = b[np.isfinite(b)]
    d = cohen_d(a, b)
    ci = cohen_d_ci_bootstrap(a, b, n_iter, seed)
    t, p = t_test(a, b)
    return {"d": round(d, 4), "ci": [round(ci[0], 4), round(ci[1], 4)],
            "t": round(t, 4), "p": p, "n_a": int(a.size), "n_b": int(b.size)}


# --------------------------------------------------------------------------- #
# Single day                                                                  #
# --------------------------------------------------------------------------- #

def _date_from(path: str, ts0: int) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    if m:
        return m.group(1)
    return datetime.fromtimestamp(ts0 / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def run_single_day(csv_path: str, out_dir: Path, verbose: bool = True) -> dict:
    cfg = CONFIG
    seed, nb = cfg["RANDOM_SEED"], cfg["BOOTSTRAP_ITERATIONS"]
    FW = cfg["FEATURE_WINDOW_SEC"]
    shift = cfg["TAUTOLOGY_SHIFT_SEC"]

    df = load_data(csv_path)
    n = len(df)
    prices = df["mid_price"].to_numpy()
    ts = df["timestamp_ms"].to_numpy()
    feat_arr = {"imbalance_inv": df["imbalance_inv"].to_numpy(),
                "imbalance_exp": df["imbalance_exp"].to_numpy()}
    date = _date_from(csv_path, int(ts[0]))
    regime = REGIME_MAP.get(date, "unknown")
    out_dir.mkdir(parents=True, exist_ok=True)

    reversals = find_reversals(prices, ts, cfg["W_REVERSAL_WINDOW_SEC"],
                               cfg["MIN_SWING_PCT"], cfg["MIN_SEPARATION_SEC"])
    if not reversals:
        summary = {"date": date, "regime": regime, "input_csv": str(csv_path),
                   "rows": n, "insufficient_data": True, "reason": "no_reversals"}
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if verbose:
            print(f"[{date}] no reversals found — insufficient_data")
        summary["_groups"] = None
        return summary

    n_up = sum(1 for r in reversals if r.direction == "up")
    n_down = sum(1 for r in reversals if r.direction == "down")

    vol = compute_vol_grid(prices, cfg["VOL_WINDOW_SEC"])
    excluded = build_excluded_mask(reversals, n, cfg["W_REVERSAL_WINDOW_SEC"])
    controls, fallback, skipped = sample_matched_controls(reversals, ts, vol, excluded, n, cfg)

    skip_idx = {s["idx"] for s in skipped}
    rev_kept = [r for r in reversals if r.idx not in skip_idx]

    def aligned(points, feat):  # points: list of (idx, direction)
        return np.array([sign_of(d) * feature_mean(feat_arr[feat], i, FW) for i, d in points])

    rev_pts = [(r.idx, r.direction) for r in rev_kept]
    ctl_pts = [(c.idx, c.direction) for c in controls]

    # Tautology points: t*-shift, same direction; skip if no feature tail.
    tauto_pts, tauto_skipped, tauto_in_window = [], 0, 0
    for r in rev_kept:
        ti = r.idx - shift
        if ti < FW:
            tauto_skipped += 1
            continue
        if excluded[ti]:
            tauto_in_window += 1            # allowed, just logged
        tauto_pts.append((ti, r.direction))

    A = {f: aligned(rev_pts, f) for f in FEATS}
    B = {f: aligned(ctl_pts, f) for f in FEATS}
    T = {f: aligned(tauto_pts, f) for f in FEATS}

    # three comparisons x two features
    rvc = {f: compare(A[f], B[f], seed, nb) for f in FEATS}
    rvt = {f: compare(A[f], T[f], seed, nb) for f in FEATS}
    tvc = {f: compare(T[f], B[f], seed, nb) for f in FEATS}

    # ----- v1 "duel" block (Reversals vs Controls), byte-identical shape -----
    d_inv, d_exp = rvc["imbalance_inv"]["d"], rvc["imbalance_exp"]["d"]
    ci_inv, ci_exp = rvc["imbalance_inv"]["ci"], rvc["imbalance_exp"]["ci"]
    duel = {"imbalance_inv": {"d": d_inv, "ci": ci_inv, "t": rvc["imbalance_inv"]["t"], "p": rvc["imbalance_inv"]["p"]},
            "imbalance_exp": {"d": d_exp, "ci": ci_exp, "t": rvc["imbalance_exp"]["t"], "p": rvc["imbalance_exp"]["p"]}}
    ci_overlap = not (ci_inv[1] < ci_exp[0] or ci_exp[1] < ci_inv[0])
    winner_feat = "imbalance_inv" if abs(d_inv) >= abs(d_exp) else "imbalance_exp"
    delta_d = abs(d_inv) - abs(d_exp) if winner_feat == "imbalance_inv" else abs(d_exp) - abs(d_inv)
    winner = "inconclusive" if ci_overlap else winner_feat
    win_abs = max(abs(d_inv), abs(d_exp))
    strength = "strong" if win_abs >= 0.5 else "significant" if win_abs >= 0.3 else "weak"

    # ----- tautology verdict (per-day, on imbalance_inv R-vs-T) -----
    taut_d_inv = rvt["imbalance_inv"]["d"]
    thr, spec = cfg["TAUTOLOGY_D_THRESHOLD"], cfg["TAUTOLOGY_D_SPECIFIC"]
    if abs(taut_d_inv) < thr:
        t_verdict, t_msg = "TAUTOLOGY_CONFIRMED", "feature reflects directional flow, not extremum-specific dynamics"
    elif abs(taut_d_inv) > spec:
        if taut_d_inv < 0:
            t_verdict, t_msg = "EXTREMUM_EXHAUSTION", "pressure exhausts approaching the extremum"
        else:
            t_verdict, t_msg = "EXTREMUM_CULMINATION", "pressure peaks at the extremum"
    else:
        t_verdict, t_msg = "BORDERLINE", "tautology test inconclusive, |d| in [0.2, 0.3]"

    # distribution sanity: |d(TvC)| ~= |d(RvC)| (diff < 0.1) -> strong tautology argument
    dist_warn = abs(abs(tvc["imbalance_inv"]["d"]) - abs(d_inv)) < 0.1

    # ----- top-N sanity -----
    top = sorted(rev_kept, key=lambda r: -abs(r.swing_pct))[:cfg["SANITY_TOP_N"]]
    top_rows = []
    for rank, r in enumerate(top, 1):
        s = sign_of(r.direction)
        m_t = s * feature_mean(feat_arr["imbalance_inv"], r.idx, FW)
        ti = r.idx - shift
        m_t90 = s * feature_mean(feat_arr["imbalance_inv"], ti, FW) if ti >= FW else None
        top_rows.append({
            "rank": rank, "timestamp_ms": r.timestamp_ms,
            "timestamp_utc": datetime.fromtimestamp(r.timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "direction": r.direction.upper(), "swing_pct": round(r.swing_pct * 100, 3),
            "mean_inv_t": round(m_t, 4),
            "mean_inv_t90": round(m_t90, 4) if m_t90 is not None else None,
            "delta": round(m_t - m_t90, 4) if m_t90 is not None else None})
    pd.DataFrame(top_rows).to_csv(out_dir / "top_reversals.csv", index=False)

    # ----- summary.json (v1 keys identical + additive v2 blocks) -----
    summary = {
        "date": date, "regime": regime, "input_csv": str(csv_path), "rows": n,
        "config": cfg,
        "reversals": {"up": n_up, "down": n_down, "total": len(reversals)},
        "controls": {"total": len(controls),
                     "avg_per_reversal": round(len(controls) / max(len(rev_kept), 1), 2),
                     "fallback": fallback, "skipped": len(skipped)},
        "duel": duel,
        "winner": winner, "winner_by_abs_d": winner_feat,
        "delta_d": round(delta_d, 4), "ci_overlap": ci_overlap, "strength": strength,
        "group_means": {
            "reversals": {SHORT[f]: round(_finite_mean(A[f]), 4) for f in FEATS},
            "controls": {SHORT[f]: round(_finite_mean(B[f]), 4) for f in FEATS}},
        "comparisons": {
            "reversals_vs_controls": rvc,
            "reversals_vs_tautology": rvt,
            "tautology_vs_controls": tvc},
        "tautology": {
            "shift_sec": shift, "n_points": len(tauto_pts),
            "skipped": tauto_skipped, "in_other_reversal_window": tauto_in_window,
            "verdict": t_verdict, "message": t_msg,
            "tautology_d_inv": taut_d_inv,
            "distribution_warning": dist_warn,
            "group_mean_tautology": {SHORT[f]: round(_finite_mean(T[f]), 4) for f in FEATS}},
        "scipy": HAVE_SCIPY, "plots": HAVE_MPL,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # labeled_points.csv (v1: reversals + controls)
    rows = []
    for r in rev_kept:
        s = sign_of(r.direction)
        rows.append({"timestamp_ms": r.timestamp_ms, "idx": r.idx, "point_type": "reversal",
                     "direction": r.direction, "parent_reversal_idx": None,
                     "mean_inv": feature_mean(feat_arr["imbalance_inv"], r.idx, FW),
                     "mean_exp": feature_mean(feat_arr["imbalance_exp"], r.idx, FW),
                     "aligned_mean_inv": s * feature_mean(feat_arr["imbalance_inv"], r.idx, FW),
                     "aligned_mean_exp": s * feature_mean(feat_arr["imbalance_exp"], r.idx, FW),
                     "vol_ref": float(vol[r.idx])})
    for c in controls:
        s = sign_of(c.direction)
        rows.append({"timestamp_ms": c.timestamp_ms, "idx": c.idx, "point_type": "control",
                     "direction": c.direction, "parent_reversal_idx": c.parent_reversal_idx,
                     "mean_inv": feature_mean(feat_arr["imbalance_inv"], c.idx, FW),
                     "mean_exp": feature_mean(feat_arr["imbalance_exp"], c.idx, FW),
                     "aligned_mean_inv": s * feature_mean(feat_arr["imbalance_inv"], c.idx, FW),
                     "aligned_mean_exp": s * feature_mean(feat_arr["imbalance_exp"], c.idx, FW),
                     "vol_ref": float(c.vol)})
    pd.DataFrame(rows).to_csv(out_dir / "labeled_points.csv", index=False)

    # attach raw aligned arrays for pooled aggregation (not written to json)
    summary["_groups"] = {"reversals": {SHORT[f]: A[f].tolist() for f in FEATS},
                          "controls": {SHORT[f]: B[f].tolist() for f in FEATS},
                          "tautology": {SHORT[f]: T[f].tolist() for f in FEATS}}

    if verbose:
        _print_single(summary)
    _print_top(date, top_rows)
    return summary


def _print_single(s: dict) -> None:
    d = s["duel"]
    print(f"=== Imbalance Duel — {s['date']} ({s['regime']}) ===\n")
    print(f"Reversals: up {s['reversals']['up']} / down {s['reversals']['down']} / total {s['reversals']['total']}")
    print(f"Controls:  {s['controls']['total']} (avg {s['controls']['avg_per_reversal']}, "
          f"fallback {s['controls']['fallback']}, skipped {s['controls']['skipped']})\n")
    print("Reversals vs Controls — Cohen's d:")
    for f in FEATS:
        b = d[f]
        print(f"  {f}:  d = {b['d']:.2f}  [{b['ci'][0]:.2f}, {b['ci'][1]:.2f}]   (t={b['t']:.2f}, p={b['p']:.2g})")
    print(f"  winner: {s['winner']}  (Δ|d|={s['delta_d']:+.2f}, strength {s['strength']})\n")
    t = s["tautology"]
    print(f"Tautology test (t* vs t*-{t['shift_sec']}s; n={t['n_points']}, skipped {t['skipped']}, "
          f"in-other-window {t['in_other_reversal_window']}):")
    for label, comp in (("Reversals vs Tautology", "reversals_vs_tautology"),
                        ("Tautology vs Controls", "tautology_vs_controls")):
        c = s["comparisons"][comp]
        print(f"  {label:24s} inv d={c['imbalance_inv']['d']:+.2f} [{c['imbalance_inv']['ci'][0]:.2f},{c['imbalance_inv']['ci'][1]:.2f}]"
              f"   exp d={c['imbalance_exp']['d']:+.2f} [{c['imbalance_exp']['ci'][0]:.2f},{c['imbalance_exp']['ci'][1]:.2f}]")
    print(f"  VERDICT: {t['verdict']} — {t['message']}  (d(R vs T) inv = {t['tautology_d_inv']:+.2f})")
    if t["distribution_warning"]:
        print("  WARNING: |d(Tautology vs Controls)| ~= |d(Reversals vs Controls)| "
              "(diff < 0.1) — strong tautology argument: feature tracks directional flow.")
    if not HAVE_MPL:
        print("\n[warn] matplotlib unavailable — PNG plots skipped.")


def _print_top(date: str, top_rows: list[dict]) -> None:
    print(f"\n=== Top {len(top_rows)} reversals by |swing_pct| for {date} ===\n")
    print(f"{'Rank':<5}{'Timestamp':<26}{'Dir':<6}{'Swing%':<9}{'mean_inv(t*)':<14}{'mean_inv(t*-90s)':<18}{'Δ'}")
    for r in top_rows:
        m90 = f"{r['mean_inv_t90']:+.4f}" if r["mean_inv_t90"] is not None else "n/a"
        dl = f"{r['delta']:+.4f}" if r["delta"] is not None else "n/a"
        print(f"{r['rank']:<5}{r['timestamp_utc']:<26}{r['direction']:<6}{r['swing_pct']:<9.3f}"
              f"{r['mean_inv_t']:<+14.4f}{m90:<18}{dl}")


# --------------------------------------------------------------------------- #
# Multi-day aggregation                                                       #
# --------------------------------------------------------------------------- #

COMPARISONS = ("reversals_vs_controls", "reversals_vs_tautology", "tautology_vs_controls")
GROUP_A = {"reversals_vs_controls": "reversals", "reversals_vs_tautology": "reversals",
           "tautology_vs_controls": "tautology"}
GROUP_B = {"reversals_vs_controls": "controls", "reversals_vs_tautology": "tautology",
           "tautology_vs_controls": "controls"}


def aggregate_multiday(per_day: list[dict], output_dir: Path) -> dict:
    cfg = CONFIG
    seed, nb = cfg["RANDOM_SEED"], cfg["BOOTSTRAP_ITERATIONS"]
    valid = [s for s in per_day if s and not s.get("insufficient_data") and s.get("_groups")]

    if not valid:
        agg = {"n_days": len(per_day), "no_data": True,
               "verdict": "NO_DATA", "verdict_reasoning": "no day produced usable groups"}
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "aggregate_summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
        print("\nAGGREGATE: NO_DATA — no usable days.")
        return agg

    comparisons_out: dict = {}
    for comp in COMPARISONS:
        ga, gb = GROUP_A[comp], GROUP_B[comp]
        comparisons_out[comp] = {}
        for f in FEATS:
            sf = SHORT[f]
            per = []
            pooled_a, pooled_b = [], []
            for s in valid:
                a = np.array(s["_groups"][ga][sf])
                b = np.array(s["_groups"][gb][sf])
                per.append({"date": s["date"], "regime": s["regime"],
                            "d": s["comparisons"][comp][f]["d"],
                            "ci": s["comparisons"][comp][f]["ci"],
                            "n": int(a.size)})
                pooled_a.append(a)
                pooled_b.append(b)
            pa, pb = np.concatenate(pooled_a), np.concatenate(pooled_b)
            pooled = compare(pa, pb, seed, nb)
            per_d = np.array([p["d"] for p in per if np.isfinite(p["d"])])
            inter_std = float(np.std(per_d)) if per_d.size else float("nan")
            comparisons_out[comp][f] = {
                "per_day": per,
                "pooled": {"d": pooled["d"], "ci": pooled["ci"], "n_a": pooled["n_a"], "n_b": pooled["n_b"]},
                "inter_day_std": round(inter_std, 4),
                "regime_dependence_warning": bool(np.isfinite(inter_std) and inter_std > cfg["INTER_DAY_STD_WARN"])}

    # ----- overall verdict -----
    rvt_inv = comparisons_out["reversals_vs_tautology"]["imbalance_inv"]
    rvc_inv = comparisons_out["reversals_vs_controls"]["imbalance_inv"]
    taut_d = rvt_inv["pooled"]["d"]
    std_main = rvc_inv["inter_day_std"]
    signs = [np.sign(p["d"]) for p in rvc_inv["per_day"] if np.isfinite(p["d"]) and p["d"] != 0]
    sign_consistent = len(set(signs)) <= 1 and len(signs) > 0
    thr, spec, std_warn = cfg["TAUTOLOGY_D_THRESHOLD"], cfg["TAUTOLOGY_D_SPECIFIC"], cfg["INTER_DAY_STD_WARN"]

    if not np.isfinite(taut_d) or abs(taut_d) < thr:
        verdict = "TAUTOLOGY_ARTIFACT"
        reason = f"|d(R vs T)| pooled inv = {taut_d:.2f} < {thr}: feature tracks directional flow, not the extremum."
    elif (np.isfinite(std_main) and std_main > std_warn) or not sign_consistent:
        verdict = "REGIME_DEPENDENT"
        reason = (f"inter-day std (R vs C inv) = {std_main:.2f} > {std_warn} or per-day sign flips "
                  f"(signs={[int(x) for x in signs]}); pooled d misleading.")
    elif abs(taut_d) > spec:
        kind = "CONTRARIAN" if taut_d < 0 else "CULMINATION"
        verdict = "ROBUST_CONTRARIAN_SIGNAL" if taut_d < 0 else "ROBUST_CULMINATION_SIGNAL"
        reason = (f"|d(R vs T)| pooled inv = {taut_d:.2f} > {spec} ({kind}); inter-day std {std_main:.2f} "
                  f"<= {std_warn}; sign consistent across {len(signs)} days.")
    else:
        verdict = "BORDERLINE"
        reason = f"|d(R vs T)| pooled inv = {taut_d:.2f} in [{thr}, {spec}]; inconclusive."

    agg = {"n_days": len(per_day), "n_valid_days": len(valid),
           "regime_map": {s["date"]: s["regime"] for s in valid},
           "comparisons": comparisons_out, "verdict": verdict, "verdict_reasoning": reason}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregate_summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")

    table_txt = _render_multiday_tables(comparisons_out, valid, cfg)
    (output_dir / "per_day_table.txt").write_text(table_txt, encoding="utf-8")
    print("\n" + table_txt)
    print(f"\n=== AGGREGATE VERDICT: {verdict} ===\n{reason}")
    return agg


def _render_multiday_tables(comp_out: dict, valid: list[dict], cfg: dict) -> str:
    lines = []
    for comp in COMPARISONS:
        for f in FEATS:
            blk = comp_out[comp][f]
            lines.append(f"=== Multi-day — {f} ({comp.replace('_', ' ')}) ===\n")
            lines.append(f"{'Day':<13}{'Regime':<24}{'N':<7}{'d':<9}{'CI'}")
            for p in blk["per_day"]:
                lines.append(f"{p['date']:<13}{p['regime']:<24}{p['n']:<7}{p['d']:<+9.2f}"
                             f"[{p['ci'][0]:+.2f}, {p['ci'][1]:+.2f}]")
            pl = blk["pooled"]
            lines.append("-" * 70)
            lines.append(f"{'Pooled':<13}{'':<24}{pl['n_a']:<7}{pl['d']:<+9.2f}[{pl['ci'][0]:+.2f}, {pl['ci'][1]:+.2f}]")
            std = blk["inter_day_std"]
            tag = "  <- HIGH (regime-dependent)" if blk["regime_dependence_warning"] else "  <- stable"
            lines.append(f"{'Inter-day std':<13}{'':<24}{'':<7}{std:<+9.2f}{tag}")
            if blk["regime_dependence_warning"]:
                ds = [p["d"] for p in blk["per_day"]]
                lines.append(f"WARNING: high inter-day variance for {comp}/{f}:")
                lines.append(f"  per-day d range: [{min(ds):+.2f}, {max(ds):+.2f}]  std: {std:.2f}")
                lines.append(f"  -> pooled d ({pl['d']:+.2f}) misleading; feature is regime-dependent.")
            lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def run_multiday(input_dir: str, output_dir: str) -> dict:
    out = Path(output_dir)
    csvs = sorted(Path(input_dir).glob("*.csv"))
    if not csvs:
        print(f"ERROR: no *.csv in {input_dir}", file=sys.stderr)
        return aggregate_multiday([], out)
    print(f"[multiday] {len(csvs)} files in {input_dir}\n")
    results = []
    for p in csvs:
        try:
            date = _date_from(str(p), 0)
            s = run_single_day(str(p), out / date, verbose=False)
            results.append(s)
        except Exception as e:
            print(f"ERROR: failed on {p.name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
    return aggregate_multiday(results, out)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # console may be cp1251
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Stage 1 §5.2 imbalance duel (v2)")
    ap.add_argument("--single", metavar="CSV")
    ap.add_argument("--multiday", action="store_true")
    ap.add_argument("--input-dir")
    ap.add_argument("--output-dir")
    ap.add_argument("legacy", nargs="*", help="legacy positional: CSV [OUTPUT_DIR]")
    args = ap.parse_args(argv)

    if args.multiday:
        if not args.input_dir or not args.output_dir:
            print("usage: --multiday --input-dir DIR --output-dir DIR", file=sys.stderr)
            return 2
        run_multiday(args.input_dir, args.output_dir)
        return 0

    csv_path = args.single or (args.legacy[0] if args.legacy else None)
    if not csv_path:
        print("usage: research_validation.py CSV [OUT] | --single CSV | "
              "--multiday --input-dir DIR --output-dir DIR", file=sys.stderr)
        return 2
    if args.output_dir:
        out_dir = Path(args.output_dir)
    elif len(args.legacy) > 1:
        out_dir = Path(args.legacy[1])
    else:
        df0 = pd.read_csv(csv_path, usecols=[CONFIG["COLUMNS"]["timestamp_ms"]], nrows=1)
        d0 = _date_from(csv_path, int(df0.iloc[0, 0]))
        out_dir = ROOT / "reports" / "stage1" / f"imbalance_duel_{d0}"
    s = run_single_day(csv_path, out_dir, verbose=True)
    print(f"\n[out] {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
