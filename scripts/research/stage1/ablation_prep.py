#!/usr/bin/env python3
"""
ablation_prep.py — Stage 1 ablation infrastructure (§5.1 legacy + Tier-2 zones).

Two independent use-cases share this script:

USE-CASE 1 (§5.1, --mode legacy): does `imbalance_inv` carry information
INDEPENDENT of the TS engine's legacy bucket features (orderflowImbalance,
buyAbsorption, sellAbsorption, refillScore, thinningScore, liquidityVoid)?
  - Correlation matrix (Pearson + Spearman) — surface redundancy.
  - Conditional Cohen's d — within quantile bins of each legacy feature, does
    imbalance_inv still separate reversals from controls? Tautology points
    excluded. Needs Participant A's legacy_features_all_days.csv.

USE-CASE 2 (Tier-2, --mode tier2): do the secondary features (funding, OI)
separate REACHED from FAILED zones? Needs Participant A's zone_features.csv.
  - merge_asof the per-second funding/OI features (from fetch_funding_oi.py /
    features_funding.py / features_oi.py) onto each zone with a LOOK-AHEAD GUARD
    (trigger_ts - 1s) and tolerance (5min funding, 1min OI).
  - pooled + bootstrap-CI + direction-split + binned reach-rate Cohen's d.
  imbalance_inv is NOT merged this iteration (variant b — needs a 1s-grid
  generation, done later).

Either dump missing -> that use-case runs in STUB MODE (prints what it expects,
exits 0). Default --mode both runs whichever data is present.

Run:  python ablation_prep.py [--mode legacy|tier2|both] [--zone-features P]
                              [--legacy P] [--funding-dir D] [--oi-dir D]
Deps: pandas (merge_asof), numpy, scipy.stats. No new repo dependency.
Reproducible: conditional d is deterministic; Tier-2 bootstrap uses RANDOM_SEED.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

ROOT = next((p for p in Path(__file__).resolve().parents
             if (p / "package.json").exists() and (p / "scripts").exists()),
            Path(__file__).resolve().parent)

# External data root (where fetch_funding_oi.py wrote derived/), env-overridable.
DATA_BYBIT_ROOT = Path(os.environ.get("DATA_BYBIT_DIR", r"C:\orderflow-recoder module\data_bybit"))

CONFIG = {
    # === §5.1 legacy keys (unchanged) ===
    "LABELED_POINTS_DIR": "reports/stage1/multiday/",
    "LEGACY_FEATURES_PATH": "data/participant_a/legacy_features_all_days.csv",
    "MERGE_TOLERANCE_MS": 1000,
    "N_BINS_FOR_CONDITIONAL_D": 3,
    "MIN_POINTS_PER_BIN": 20,
    "OUTPUT_DIR": "reports/stage1/ablation/",
    "RANDOM_SEED": 42,
    # === Tier-2 keys ===
    "ZONE_FEATURES_PATH": "data/participant_a/zone_features.csv",
    "TIER2_FUNDING_DIR": str(DATA_BYBIT_ROOT / "derived" / "features_funding"),
    "TIER2_OI_DIR": str(DATA_BYBIT_ROOT / "derived" / "features_oi"),
    "TIER2_IMBALANCE_DIR": "reports/stage1/multiday/",
    "LOOK_AHEAD_GUARD_SEC": 1,
    "TOLERANCE_FUNDING_SEC": 300,    # 5 min
    "TOLERANCE_OI_SEC": 60,          # 1 min
    "OUTCOME_HORIZON": "4h",
    "BOOTSTRAP_ITERATIONS": 2000,
}

LEGACY_FEATURES = ["orderflowImbalance", "buyAbsorption", "sellAbsorption",
                   "refillScore", "thinningScore", "liquidityVoid"]
REQUIRED_LEGACY_COLUMNS = ["timestamp_ms"] + LEGACY_FEATURES
SCHEMA_HELP = ("timestamp_ms (int64), orderflowImbalance (float64), "
               "buyAbsorption (float64), sellAbsorption (float64), "
               "refillScore (float64), thinningScore (float64), "
               "liquidityVoid (float64)")

# Tier-2 secondary features tested against the zone outcome (those that exist
# after the merge are used; binary funding_sign_flip is excluded from Cohen's d).
TIER2_SECONDARY_FEATURES = ["funding_current", "funding_24h_avg",
                            "delta_oi_60s_pct", "delta_oi_5m_pct", "delta_oi_30m_pct"]


def _resolve(p: str) -> Path:
    pp = Path(p)
    return pp if pp.is_absolute() else (ROOT / pp)


# =========================================================================== #
# §5.1 legacy use-case — existing functions (UNCHANGED)                       #
# =========================================================================== #

def load_all_labeled_points(reports_dir: str) -> pd.DataFrame:
    """Concatenate labeled_points.csv from every per-day subdir; add `date`."""
    base = _resolve(reports_dir)
    files = sorted(base.glob("*/labeled_points.csv"))
    if not files:
        raise FileNotFoundError(
            f"No */labeled_points.csv under {base}. Run research_validation.py "
            f"--multiday first.")
    frames = []
    for f in files:
        d = pd.read_csv(f)
        d["date"] = f.parent.name
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    return df.sort_values("timestamp_ms").reset_index(drop=True)


def load_legacy_features(path: str) -> pd.DataFrame:
    """Load Participant A's dump (CSV or Parquet by extension). Validate schema."""
    p = _resolve(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Legacy features dump not found at {p}.\n"
            f"Expected schema: see scripts/research/stage1/ablation_prep.py docstring.\n"
            f"Waiting for Participant A's delivery.")
    if p.suffix.lower() in (".parquet", ".pq"):
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p)
    missing = [c for c in REQUIRED_LEGACY_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Legacy feature dump missing column: {missing[0]}. "
                         f"Expected: {REQUIRED_LEGACY_COLUMNS}")
    df["timestamp_ms"] = df["timestamp_ms"].astype("int64")
    return df.sort_values("timestamp_ms").reset_index(drop=True)


def merge_features(labeled: pd.DataFrame, legacy: pd.DataFrame, tolerance_ms: int) -> pd.DataFrame:
    """merge_asof backward on timestamp_ms (last known legacy value at the point)."""
    left = labeled.sort_values("timestamp_ms")
    right = legacy.sort_values("timestamp_ms")
    merged = pd.merge_asof(left, right, on="timestamp_ms", direction="backward",
                           tolerance=int(tolerance_ms))
    n = len(merged)
    for f in LEGACY_FEATURES:
        pct = 100.0 * merged[f].isna().mean() if n else 0.0
        if pct >= 5.0:
            print(f"WARNING: {f} is {pct:.1f}% NaN after merge_asof "
                  f"(tolerance {tolerance_ms}ms) — alignment gaps.", file=sys.stderr)
    return merged


def correlation_matrix(df: pd.DataFrame, new_feature: str, legacy_features: list[str]) -> pd.DataFrame:
    rows = []
    x_all = df[new_feature].to_numpy()
    for lf in legacy_features:
        y_all = df[lf].to_numpy()
        ok = np.isfinite(x_all) & np.isfinite(y_all)
        x, y = x_all[ok], y_all[ok]
        if x.size < 3:
            rows.append({"legacy_feature": lf, "n": int(x.size), "pearson_r": np.nan,
                         "pearson_p": np.nan, "spearman_r": np.nan, "spearman_p": np.nan})
            continue
        pr, pp = sstats.pearsonr(x, y)
        sr, sp = sstats.spearmanr(x, y)
        rows.append({"legacy_feature": lf, "n": int(x.size),
                     "pearson_r": round(float(pr), 4), "pearson_p": float(pp),
                     "spearman_r": round(float(sr), 4), "spearman_p": float(sp)})
    return pd.DataFrame(rows)


def _redundancy_label(r: float) -> str:
    a = abs(r)
    if a > 0.85:
        return "high_redundancy"
    if a >= 0.5:
        return "partial_overlap"
    return "weak_linear"


def cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return float("nan")
    pooled = ((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2)
    s = np.sqrt(pooled)
    return float((np.mean(a) - np.mean(b)) / s) if s else float("nan")


def conditional_cohen_d(df: pd.DataFrame, new_feature: str, legacy_feature: str,
                        label_col: str = "point_type", n_bins: int = 3,
                        min_points_per_bin: int = 20) -> dict:
    """Within quantile bins of `legacy_feature`, Cohen's d of `new_feature`
    between reversals and controls (tautology points excluded). Compare to the
    un-binned pooled d to decide if `new_feature` adds independent information."""
    d = df[df[label_col].isin(("reversal", "control"))].copy()
    d = d[np.isfinite(d[new_feature]) & np.isfinite(d[legacy_feature])]

    def _split(sub):
        rev = sub.loc[sub[label_col] == "reversal", new_feature].to_numpy()
        ctl = sub.loc[sub[label_col] == "control", new_feature].to_numpy()
        return rev, ctl

    rev_all, ctl_all = _split(d)
    pooled_d = cohen_d(rev_all, ctl_all)

    try:
        bins = pd.qcut(d[legacy_feature], n_bins, labels=False, duplicates="drop")
    except Exception:
        bins = pd.Series(np.zeros(len(d), dtype=int), index=d.index)

    per_bin, skipped = [], []
    for b in sorted(pd.unique(bins.dropna())):
        sub = d[bins == b]
        rev, ctl = _split(sub)
        rng = (float(sub[legacy_feature].min()), float(sub[legacy_feature].max()))
        if rev.size < min_points_per_bin or ctl.size < min_points_per_bin:
            skipped.append({"bin_idx": int(b), "bin_range": [round(rng[0], 4), round(rng[1], 4)],
                            "n_rev": int(rev.size), "n_ctrl": int(ctl.size), "reason": "below_min_points"})
            continue
        per_bin.append({"bin_idx": int(b), "bin_range": [round(rng[0], 4), round(rng[1], 4)],
                        "n_rev": int(rev.size), "n_ctrl": int(ctl.size),
                        "d": round(cohen_d(rev, ctl), 4)})

    abs_bins = [abs(x["d"]) for x in per_bin if np.isfinite(x["d"])]
    max_within = max(abs_bins) if abs_bins else float("nan")
    pooled_abs = abs(pooled_d) if np.isfinite(pooled_d) else float("nan")
    drop = pooled_abs - max_within if np.isfinite(max_within) and np.isfinite(pooled_abs) else float("nan")

    if not np.isfinite(drop):
        verdict = "INSUFFICIENT_DATA"
    elif drop < 0.1:
        verdict = "INDEPENDENT_INFORMATION"
    elif drop > pooled_abs * 0.7:
        verdict = "REDUNDANT"
    else:
        verdict = "PARTIAL_OVERLAP"

    return {"legacy_feature": legacy_feature, "new_feature": new_feature,
            "pooled_d": round(pooled_d, 4) if np.isfinite(pooled_d) else None,
            "per_bin": per_bin, "skipped_bins": skipped,
            "max_within_bin_abs_d": round(max_within, 4) if np.isfinite(max_within) else None,
            "drop_from_pooled": round(drop, 4) if np.isfinite(drop) else None,
            "verdict": verdict}


def _stub(legacy_path: Path, labeled_dir: str) -> int:
    print(f"[STUB MODE] Legacy features dump not found at {legacy_path}.")
    print("Expected schema:")
    print(f"    {SCHEMA_HELP}")
    print(f"    (covering the same 8 days as our labeled_points.csv)")
    try:
        lp = load_all_labeled_points(labeled_dir)
        dates = sorted(lp["date"].unique())
        print(f"\nOur side is ready: {len(lp)} labeled points across "
              f"{len(dates)} days {dates}.")
    except FileNotFoundError as e:
        print(f"\n[note] our labeled points not found yet: {e}")
    print("\nAblation pipeline is ready. Awaiting Participant A's delivery.")
    return 0


def run_legacy_ablation(legacy_path: str, labeled_dir: str, output_dir: str) -> int:
    """§5.1 ablation; graceful stub if the legacy dump is absent."""
    lp = _resolve(legacy_path)
    if not lp.exists():
        return _stub(lp, labeled_dir)

    out = _resolve(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    labeled = load_all_labeled_points(labeled_dir)
    legacy = load_legacy_features(legacy_path)
    merged = merge_features(labeled, legacy, CONFIG["MERGE_TOLERANCE_MS"])

    corr = correlation_matrix(merged, "mean_inv", LEGACY_FEATURES)
    corr["redundancy"] = corr["spearman_r"].apply(
        lambda r: _redundancy_label(r) if np.isfinite(r) else "n/a")
    corr.to_csv(out / "correlation_matrix.csv", index=False)

    cond = [conditional_cohen_d(merged, "aligned_mean_inv", lf,
                                n_bins=CONFIG["N_BINS_FOR_CONDITIONAL_D"],
                                min_points_per_bin=CONFIG["MIN_POINTS_PER_BIN"])
            for lf in LEGACY_FEATURES]
    (out / "conditional_d.json").write_text(json.dumps({"results": cond}, indent=2), encoding="utf-8")

    verdicts = {c["legacy_feature"]: c["verdict"] for c in cond}
    independent = all(v == "INDEPENDENT_INFORMATION" for v in verdicts.values())
    redundant_any = any(v == "REDUNDANT" for v in verdicts.values())
    overall = ("INDEPENDENT_OF_ALL_LEGACY" if independent else
               "REDUNDANT_WITH_SOME_LEGACY" if redundant_any else "PARTIAL_OVERLAP")
    summary = {"n_points": int(len(merged)),
               "correlation": corr.to_dict(orient="records"),
               "conditional_verdicts": verdicts, "overall_verdict": overall}
    (out / "ablation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"=== §5.1 Ablation — {len(merged)} points ===\n")
    print("Correlation (imbalance_inv vs legacy):")
    for _, r in corr.iterrows():
        print(f"  {r['legacy_feature']:20s} pearson {r['pearson_r']:+.3f}  "
              f"spearman {r['spearman_r']:+.3f}  [{r['redundancy']}]")
    print("\nConditional Cohen's d (reversals vs controls within legacy bins):")
    for c in cond:
        print(f"  {c['legacy_feature']:20s} pooled {c['pooled_d']}  "
              f"max_within {c['max_within_bin_abs_d']}  drop {c['drop_from_pooled']}  -> {c['verdict']}")
    print(f"\nOVERALL: {overall}")
    print(f"\n[out] {out}")
    return 0


# =========================================================================== #
# Tier-2 use-case — zone outcome vs secondary features (funding, OI)          #
# =========================================================================== #

ZONE_REQUIRED_COLUMNS = ["zone_id", "direction", "trigger_ts_ms", "final_status", "reached_4h"]


def load_zone_features(path: str) -> pd.DataFrame:
    """Load Participant A's zone dump. Keeps ALL final_status (filter at analysis)."""
    p = _resolve(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Zone features dump not found at {p}. Expected delivery from "
            f"Participant A. See plan_for_partner_stage1.md.")
    df = pd.read_parquet(p) if p.suffix.lower() in (".parquet", ".pq") else pd.read_csv(p)
    missing = [c for c in ZONE_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Zone features missing required columns: {missing}. "
                         f"Required: {ZONE_REQUIRED_COLUMNS}. Got: {list(df.columns)}")
    df["trigger_ts_ms"] = df["trigger_ts_ms"].astype("int64")
    return df.sort_values("trigger_ts_ms").reset_index(drop=True)


def load_tier2_features(funding_dir: str, oi_dir: str, imbalance_dir: str,
                        date_range: tuple[str, str]) -> dict:
    """Load per-day funding/OI feature CSVs within [start,end]; concat+dedup."""
    start, end = date_range

    def load(directory: str, prefix: str, label: str) -> pd.DataFrame:
        d = _resolve(directory)
        files = sorted(d.glob(f"{prefix}_*.csv")) if d.exists() else []
        frames, dates = [], []
        for f in files:
            date = f.stem[len(prefix) + 1:]
            if start <= date <= end:
                frames.append(pd.read_csv(f)); dates.append(date)
        if not frames:
            print(f"[tier2] WARNING: no {label} files under {d} in [{start},{end}] -> empty",
                  file=sys.stderr)
            return pd.DataFrame()
        out = (pd.concat(frames, ignore_index=True)
               .drop_duplicates("timestamp_ms", keep="last")
               .sort_values("timestamp_ms").reset_index(drop=True))
        out["timestamp_ms"] = out["timestamp_ms"].astype("int64")
        print(f"[tier2] loaded {label}: {len(out)} rows over {len(dates)} day(s)", file=sys.stderr)
        return out

    funding = load(funding_dir, "features_funding", "funding")
    oi = load(oi_dir, "features_oi", "oi")
    # variant (b): imbalance needs a 1s-grid generation (windows on reversals, not
    # zones) -> skipped this iteration; merged as empty without failing.
    print("[tier2] imbalance: skipped (variant b — 1s-grid generation pending)", file=sys.stderr)
    return {"funding": funding, "oi": oi, "imbalance": pd.DataFrame()}


def merge_tier2_to_zones(zones: pd.DataFrame, tier2: dict, look_ahead_guard_sec: int,
                         tolerance_funding_sec: int, tolerance_oi_sec: int) -> pd.DataFrame:
    """merge_asof each feed onto zones at guarded_ts = trigger - guard (look-ahead safe)."""
    z = zones.copy()
    z["guarded_ts_ms"] = z["trigger_ts_ms"].astype("int64") - look_ahead_guard_sec * 1000

    def merge_one(zdf: pd.DataFrame, feed_df: pd.DataFrame, feed: str, tol_ms: int) -> pd.DataFrame:
        if feed_df is None or feed_df.empty:
            zdf = zdf.copy()
            zdf[f"{feed}_timestamp_ms"] = np.nan
            zdf[f"{feed}_stale"] = True
            return zdf
        zz = zdf.sort_values("guarded_ts_ms")
        ff = feed_df.sort_values("timestamp_ms").rename(columns={"timestamp_ms": f"{feed}_timestamp_ms"})
        m = pd.merge_asof(zz, ff, left_on="guarded_ts_ms", right_on=f"{feed}_timestamp_ms",
                          direction="backward", tolerance=int(tol_ms))
        m[f"{feed}_stale"] = m[f"{feed}_timestamp_ms"].isna()
        return m

    enr = merge_one(z, tier2.get("funding"), "funding", tolerance_funding_sec * 1000)
    enr = merge_one(enr, tier2.get("oi"), "oi", tolerance_oi_sec * 1000)

    n = len(enr)
    nf = int(enr["funding_stale"].sum()); no = int(enr["oi_stale"].sum())
    both = int((~enr["funding_stale"] & ~enr["oi_stale"]).sum())
    print(f"[tier2] merge: {n} zones | both fresh {both} | funding stale {nf} | oi stale {no}",
          file=sys.stderr)
    return enr


def _verify_look_ahead(enr: pd.DataFrame, guard_sec: int) -> None:
    """A5: each fresh feed timestamp must be < trigger_ts - guard (no look-ahead)."""
    for feed in ("funding", "oi"):
        col = f"{feed}_timestamp_ms"
        if col not in enr.columns:
            continue
        fresh = enr[~enr[f"{feed}_stale"]]
        if fresh.empty:
            print(f"[tier2] look-ahead ({feed}): all stale, nothing to check", file=sys.stderr)
            continue
        bound = fresh["trigger_ts_ms"].to_numpy() - guard_sec * 1000
        bad = int((fresh[col].to_numpy() >= bound).sum())
        assert bad == 0, f"LOOK-AHEAD VIOLATION: {bad} {feed} ts >= trigger - {guard_sec}s"
        print(f"[tier2] look-ahead guard OK ({feed}): all {len(fresh)} fresh ts "
              f"< trigger - {guard_sec}s", file=sys.stderr)


def _bootstrap_d_ci(a: np.ndarray, b: np.ndarray, n_iter: int, seed: int):
    a = a[np.isfinite(a)]; b = b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    ds = np.empty(n_iter)
    for i in range(n_iter):
        ds[i] = cohen_d(a[rng.integers(0, a.size, a.size)], b[rng.integers(0, b.size, b.size)])
    ds = ds[np.isfinite(ds)]
    if ds.size == 0:
        return float("nan"), float("nan")
    return float(np.percentile(ds, 2.5)), float(np.percentile(ds, 97.5))


def tier2_analysis(enriched: pd.DataFrame, secondary_features: list[str],
                   outcome_col: str = "reached_4h", n_bins: int = 3,
                   min_points_per_bin: int = 20, output_dir: str = "reports/stage1/ablation/",
                   seed: int = 42, n_boot: int = 2000) -> dict:
    """Do secondary features separate reached from failed zones? (pooled + CI +
    direction-split + binned reach-rate Cohen's d.)"""
    resolved = enriched[enriched["final_status"].isin(("RESOLVED_REACHED", "RESOLVED_FAILED"))].copy()
    reached = resolved[outcome_col].astype(float).to_numpy() > 0.5
    n_res = len(resolved); n_reach = int(reached.sum()); n_fail = n_res - n_reach
    base = n_reach / n_res if n_res else float("nan")
    direction = resolved["direction"].to_numpy() if "direction" in resolved.columns else np.array([""] * n_res)

    feats = [f for f in secondary_features if f in resolved.columns]
    feat_out = {}
    for f in feats:
        vals = resolved[f].to_numpy(dtype=float)
        fin = np.isfinite(vals)
        a = vals[reached & fin]; b = vals[(~reached) & fin]
        d = cohen_d(a, b)
        lo, hi = _bootstrap_d_ci(a, b, n_boot, seed)

        def dir_d(name):
            m = (direction == name)
            return cohen_d(vals[m & reached & fin], vals[m & (~reached) & fin])
        long_d, short_d = dir_d("LONG"), dir_d("SHORT")

        prof = []
        try:
            bins = pd.qcut(pd.Series(vals[fin]), n_bins, labels=False, duplicates="drop")
            sub = pd.DataFrame({"v": vals[fin], "r": reached[fin].astype(float), "bin": bins.to_numpy()})
            for bi in sorted(sub["bin"].dropna().unique()):
                g = sub[sub["bin"] == bi]
                prof.append({"bin_idx": int(bi),
                             "bin_range": [round(float(g["v"].min()), 6), round(float(g["v"].max()), 6)],
                             "n": int(len(g)),
                             "reach_rate": round(float(g["r"].mean()), 4) if len(g) >= min_points_per_bin else None})
        except Exception:
            pass

        if np.isfinite(d) and abs(d) >= 0.30 and np.isfinite(lo) and np.isfinite(hi) and (lo > 0) == (hi > 0):
            verdict = "INFORMATIVE"
        elif np.isfinite(d) and 0.15 <= abs(d) < 0.30:
            verdict = "WEAK"
        else:
            verdict = "NOISE"

        feat_out[f] = {"pooled_d": round(d, 4) if np.isfinite(d) else None,
                       "ci_low": round(lo, 4) if np.isfinite(lo) else None,
                       "ci_high": round(hi, 4) if np.isfinite(hi) else None,
                       "long_d": round(long_d, 4) if np.isfinite(long_d) else None,
                       "short_d": round(short_d, 4) if np.isfinite(short_d) else None,
                       "binned_profile": prof, "verdict": verdict}

    corrs = []
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            fa, fb = feats[i], feats[j]
            xa = resolved[fa].to_numpy(float); xb = resolved[fb].to_numpy(float)
            ok = np.isfinite(xa) & np.isfinite(xb)
            if ok.sum() >= 3:
                pr = float(sstats.pearsonr(xa[ok], xb[ok])[0])
                sr = float(sstats.spearmanr(xa[ok], xb[ok])[0])
            else:
                pr = sr = float("nan")
            corrs.append({"feature_a": fa, "feature_b": fb,
                          "pearson": round(pr, 4) if np.isfinite(pr) else None,
                          "spearman": round(sr, 4) if np.isfinite(sr) else None})

    result = {"n_zones_resolved": n_res, "n_reached": n_reach, "n_failed": n_fail,
              "base_rate_reached": round(base, 4) if np.isfinite(base) else None,
              "outcome_col": outcome_col,
              "secondary_features": feat_out, "secondary_correlations": corrs}

    out = _resolve(output_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "tier2_analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"\n=== Tier-2 analysis — {n_res} resolved zones "
          f"({n_reach} reached / {n_fail} failed, base rate {base:.3f}) ===")
    print(f"  {'feature':20s}{'pooled_d':>9s}{'95% CI':>18s}{'long_d':>8s}{'short_d':>9s}  verdict")
    for f, o in feat_out.items():
        pd_ = o["pooled_d"] if o["pooled_d"] is not None else float("nan")
        ld = o["long_d"] if o["long_d"] is not None else float("nan")
        sd = o["short_d"] if o["short_d"] is not None else float("nan")
        ci = (f"[{o['ci_low']:+.2f},{o['ci_high']:+.2f}]"
              if o["ci_low"] is not None and o["ci_high"] is not None else "[n/a]")
        print(f"  {f:20s}{pd_:>+9.2f}{ci:>18s}{ld:>+8.2f}{sd:>+9.2f}  {o['verdict']}")
    print(f"[tier2] -> {out / 'tier2_analysis.json'}")
    return result


def _tier2_stub(zone_path: Path, funding_dir: str, oi_dir: str) -> int:
    print(f"[STUB MODE — Tier-2] Zone features dump not found at {zone_path}.")
    print("Expected delivery from Participant A (see plan_for_partner_stage1.md, Part D).")
    print("\nWhen file appears, this script will automatically:")
    print("1. Load zone_features.csv with all outcome labels.")
    print("2. Merge with Tier-2 secondary features (funding, OI) using pd.merge_asof")
    print("   with look-ahead guard (trigger_ts - 1s) and tolerance (5min funding, 1min OI).")
    print("3. Run conditional Cohen's d analysis: do secondary features separate")
    print("   reached from failed zones?")
    print("4. Output to reports/stage1/ablation/tier2_analysis.json.")
    fd, od = _resolve(funding_dir), _resolve(oi_dir)
    nf = len(sorted(fd.glob("features_funding_*.csv"))) if fd.exists() else 0
    no = len(sorted(od.glob("features_oi_*.csv"))) if od.exists() else 0
    print("\nTier-2 secondary features on disk:")
    print(f"- Funding: {fd} ({nf} day files)")
    print(f"- OI:      {od} ({no} day files)")
    return 0


def run_tier2_analysis(zone_path: str, funding_dir: str, oi_dir: str,
                       imbalance_dir: str, output_dir: str, cfg: dict) -> int:
    zp = _resolve(zone_path)
    if not zp.exists():
        return _tier2_stub(zp, funding_dir, oi_dir)
    zones = load_zone_features(zone_path)
    d0 = datetime.fromtimestamp(int(zones["trigger_ts_ms"].min()) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    d1 = datetime.fromtimestamp(int(zones["trigger_ts_ms"].max()) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"[tier2] {len(zones)} zones, trigger dates {d0}..{d1}", file=sys.stderr)
    tier2 = load_tier2_features(funding_dir, oi_dir, imbalance_dir, (d0, d1))
    enr = merge_tier2_to_zones(zones, tier2, cfg["LOOK_AHEAD_GUARD_SEC"],
                               cfg["TOLERANCE_FUNDING_SEC"], cfg["TOLERANCE_OI_SEC"])
    _verify_look_ahead(enr, cfg["LOOK_AHEAD_GUARD_SEC"])
    tier2_analysis(enr, TIER2_SECONDARY_FEATURES,
                   outcome_col=f"reached_{cfg['OUTCOME_HORIZON']}",
                   n_bins=cfg["N_BINS_FOR_CONDITIONAL_D"],
                   min_points_per_bin=cfg["MIN_POINTS_PER_BIN"],
                   output_dir=output_dir, seed=cfg["RANDOM_SEED"], n_boot=cfg["BOOTSTRAP_ITERATIONS"])
    return 0


# --------------------------------------------------------------------------- #
# Synthetic zones for smoke-testing the Tier-2 path (no real dump needed)      #
# --------------------------------------------------------------------------- #

def generate_synthetic_zones(n_zones: int, output_path: str, seed: int = 42) -> Path:
    """Deterministic synthetic zone_features.csv across the 8 geometry days."""
    rng = np.random.default_rng(seed)
    dates = ["2025-10-10", "2025-10-11", "2025-10-12",
             "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05", "2026-06-06"]

    def day_start_ms(d):
        return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    rows = []
    for i in range(n_zones):
        ds = day_start_ms(dates[int(rng.integers(0, len(dates)))])
        # continuous ms within the day (1h..23h) -> guard makes look-ahead strict
        trigger = ds + int(rng.integers(3_600_000, 82_800_000))
        d_dir = "LONG" if rng.random() < 0.5 else "SHORT"
        u = rng.random()
        if u < 0.60:
            status, reached = "RESOLVED_REACHED", 1
        elif u < 0.90:
            status, reached = "RESOLVED_FAILED", 0
        else:
            status, reached = str(rng.choice(["NO_TRIGGER", "EXPIRED", "INVALIDATED"])), 0
        price = float(rng.uniform(60000, 122000))
        rows.append({
            "zone_id": f"Z{i:05d}", "direction": d_dir,
            "candidate_ts_ms": trigger - 600_000, "confirmed_ts_ms": trigger - 180_000,
            "trigger_ts_ms": trigger, "resolution_ts_ms": trigger + int(rng.integers(60_000, 14_400_000)),
            "final_status": status, "zone_low": price * 0.999, "zone_high": price * 1.001,
            "trigger_price": price, "target_price": price * (1.02 if d_dir == "LONG" else 0.98),
            "orderflowImbalance_0.05": float(rng.uniform(-1, 1)),
            "realizedVolPct": float(rng.uniform(0, 0.5)),
            "reached_4h": reached,
            "time_to_target_4h_min": float(rng.uniform(1, 240)) if reached else None,
            "MFE_4h": float(rng.uniform(0, 3)), "MAE_4h": float(-rng.uniform(0, 3)),
        })
    p = _resolve(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


# =========================================================================== #
# CLI                                                                         #
# =========================================================================== #

def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Stage 1 ablation: §5.1 legacy + Tier-2 zones.")
    ap.add_argument("--mode", choices=["legacy", "tier2", "both"], default="both")
    ap.add_argument("--legacy", default=CONFIG["LEGACY_FEATURES_PATH"])
    ap.add_argument("--labeled-dir", default=CONFIG["LABELED_POINTS_DIR"])
    ap.add_argument("--zone-features", default=CONFIG["ZONE_FEATURES_PATH"])
    ap.add_argument("--funding-dir", default=CONFIG["TIER2_FUNDING_DIR"])
    ap.add_argument("--oi-dir", default=CONFIG["TIER2_OI_DIR"])
    ap.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    args = ap.parse_args(argv)

    rc = 0
    if args.mode in ("legacy", "both"):
        rc = run_legacy_ablation(args.legacy, args.labeled_dir, args.output_dir) or rc
    if args.mode in ("tier2", "both"):
        rc = run_tier2_analysis(args.zone_features, args.funding_dir, args.oi_dir,
                                CONFIG["TIER2_IMBALANCE_DIR"], args.output_dir, CONFIG) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
