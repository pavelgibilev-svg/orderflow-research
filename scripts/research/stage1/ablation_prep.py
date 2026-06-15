#!/usr/bin/env python3
"""
ablation_prep.py — Stage 1 §5.1 ablation infrastructure.

Tests whether `imbalance_inv` carries information INDEPENDENT of the legacy
bucket-based features in the TS engine (orderflowImbalance, buyAbsorption,
sellAbsorption, refillScore, thinningScore, liquidityVoid).

Two complementary tests:
  1. Correlation matrix (Pearson + Spearman) — surface-level redundancy.
  2. Conditional Cohen's d — predictive independence within strata of each
     legacy feature. This is the *real* ablation: if the within-bin d (reversals
     vs controls on imbalance_inv) collapses toward 0 inside quantile bins of a
     legacy feature, then imbalance_inv is largely a function of that feature,
     not new information. Tautology points are EXCLUDED from this test (it is
     about predicting the reversal, not the extremum's specificity).

Until Participant A's feature dump exists this script runs in STUB MODE: it
prints the expected input schema and exits 0 (a normal waiting state, not an
error). Once the dump exists, the SAME command runs the full ablation.

Feature columns used (documented choices):
  - correlation:      raw `mean_inv` vs raw legacy features (direction-agnostic
                      linear redundancy).
  - conditional d:    `aligned_mean_inv` (sign-aligned, the predictive quantity
                      that produced the -0.44 duel result), binned by the RAW
                      legacy feature.

Run:  python ablation_prep.py [--legacy PATH] [--output-dir DIR]
Deps: pandas (merge_asof), numpy, scipy.stats. No new dependency vs the repo.
Reproducible: conditional d is deterministic (quantile bins, closed-form d).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

ROOT = next((p for p in Path(__file__).resolve().parents
             if (p / "package.json").exists() and (p / "scripts").exists()),
            Path(__file__).resolve().parent)

CONFIG = {
    "LABELED_POINTS_DIR": "reports/stage1/multiday/",     # per-day subdirs w/ labeled_points.csv
    "LEGACY_FEATURES_PATH": "data/participant_a/legacy_features_all_days.csv",
    "MERGE_TOLERANCE_MS": 1000,
    "N_BINS_FOR_CONDITIONAL_D": 3,
    "MIN_POINTS_PER_BIN": 20,
    "OUTPUT_DIR": "reports/stage1/ablation/",
    "RANDOM_SEED": 42,
}

LEGACY_FEATURES = ["orderflowImbalance", "buyAbsorption", "sellAbsorption",
                   "refillScore", "thinningScore", "liquidityVoid"]
REQUIRED_LEGACY_COLUMNS = ["timestamp_ms"] + LEGACY_FEATURES
SCHEMA_HELP = ("timestamp_ms (int64), orderflowImbalance (float64), "
               "buyAbsorption (float64), sellAbsorption (float64), "
               "refillScore (float64), thinningScore (float64), "
               "liquidityVoid (float64)")


def _resolve(p: str) -> Path:
    pp = Path(p)
    return pp if pp.is_absolute() else (ROOT / pp)


# --------------------------------------------------------------------------- #
# Loading                                                                     #
# --------------------------------------------------------------------------- #

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
        df = pd.read_parquet(p)                       # needs pyarrow/fastparquet
    else:
        df = pd.read_csv(p)
    missing = [c for c in REQUIRED_LEGACY_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Legacy feature dump missing column: {missing[0]}. "
                         f"Expected: {REQUIRED_LEGACY_COLUMNS}")
    df["timestamp_ms"] = df["timestamp_ms"].astype("int64")
    return df.sort_values("timestamp_ms").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Merge                                                                       #
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Analysis 1 — correlation matrix                                             #
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Analysis 2 — conditional Cohen's d (the real ablation)                       #
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

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


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Stage 1 §5.1 ablation (stub until dump arrives)")
    ap.add_argument("--legacy", default=CONFIG["LEGACY_FEATURES_PATH"])
    ap.add_argument("--labeled-dir", default=CONFIG["LABELED_POINTS_DIR"])
    ap.add_argument("--output-dir", default=CONFIG["OUTPUT_DIR"])
    args = ap.parse_args(argv)

    legacy_path = _resolve(args.legacy)
    if not legacy_path.exists():
        return _stub(legacy_path, args.labeled_dir)

    # ---- full ablation ----
    out = _resolve(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    labeled = load_all_labeled_points(args.labeled_dir)
    legacy = load_legacy_features(args.legacy)
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


if __name__ == "__main__":
    sys.exit(main())
