#!/usr/bin/env python3
"""
test_vectors_gen.py  --  Stage 1 §6: feature_test_vectors.json generator.

Emits the bit-exact geometry contract handed to Участник А (the TS engine).
For each book snapshot it runs the REFERENCE implementation
features_geometry.book_geometry_snapshot and records the eight §6 fields rounded
to 6 decimals. The TS port must reproduce these to 6 decimals (DoD §7.1).

Why SYNTHETIC books: the contract must be regenerable/verifiable without the
multi-GB recorder dataset. The cases cover the §6 scenario list **by book SHAPE**
(geometry depends only on the book, not on liquidations/funding) plus the
numerically dangerous edge cases the TS side is most likely to get wrong:
window-boundary inclusion (`<=`), out-of-window exclusion, <3 levels, a single
level, one empty side (NaN mid), and both sides empty.

Real-book parity is proven separately: book_reconstruction's built-in
batch-vs-reference guard == 2.18e-11 over 86,401 live snapshots (2026-06-02
perp). So these synthetic vectors are the cross-LANGUAGE (Python<->TS) contract;
the cross-IMPLEMENTATION (reference vs vectorized) parity is already covered.

Contract conventions (also written into metadata):
  - window rule: keep level iff |price - mid| / mid <= max_depth_pct  (INCLUSIVE)
  - NaN  ->  JSON null  (JS JSON.parse rejects the bare token NaN). null means an
    UNDEFINED side: mass == 0, empty book, or a zero imbalance denominator.
  - tick_size 0.1, max_depth_pct 0.005, exp_decay_lambda 10, size_multiplier 1.0.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "package.json").exists() and (p / "scripts").exists())
sys.path.insert(0, str(Path(__file__).resolve().parent))
import features_geometry as geo  # noqa: E402

TICK = 0.1
MAX_DEPTH_PCT = geo.DEFAULT_MAX_DEPTH_PCT      # 0.005
EXP_LAMBDA = geo.DEFAULT_EXP_LAMBDA            # 10.0
T0 = 1759104000000                             # 2025-10-11T00:00:00Z (ms), base stamp

FIELDS = ["mass_bid", "com_bid_ticks", "variance_bid",
          "mass_ask", "com_ask_ticks", "variance_ask",
          "imbalance_inv", "imbalance_exp"]


def ladder(start: float, step: float, sizes, up: bool):
    """Build [[price, size], ...] stepping by +/- `step` from `start`."""
    out, p = [], start
    for s in sizes:
        out.append([round(p, 1), float(s)])
        p = p + step if up else p - step
    return out


# Each case: a book SHAPE. timestamp is synthetic; expected_features are filled
# from the reference at generation time. Mid is implied by best bid/ask.
CASES = [
    dict(case_id="symmetric_book_quiet",
         scenario="§6.1 symmetric book, quiet -> imbalance ~ 0 (exactly 0 here)",
         bids=ladder(60000.0, 0.1, [1.5, 2.3, 1.0, 0.8], up=False),
         asks=ladder(60000.1, 0.1, [1.5, 2.3, 1.0, 0.8], up=True)),
    dict(case_id="strong_bid_skew",
         scenario="§6.2 massive bid defense below -> imbalance_inv >> 0",
         bids=ladder(60000.0, 0.1, [50, 40, 30, 20], up=False),
         asks=ladder(60000.1, 0.1, [2.0, 1.5, 1.0, 0.8], up=True)),
    dict(case_id="strong_ask_skew",
         scenario="§6.3 massive ask resistance above -> imbalance_inv << 0",
         bids=ladder(60000.0, 0.1, [2.0, 1.5, 1.0, 0.8], up=False),
         asks=ladder(60000.1, 0.1, [50, 40, 30, 20], up=True)),
    dict(case_id="empty_bid_side",
         scenario="§6.4 bids empty -> best_bid NaN -> mid NaN -> all fields undefined",
         bids=[], asks=ladder(60000.1, 0.1, [1.8, 2.1, 1.0], up=True)),
    dict(case_id="empty_ask_side",
         scenario="§6.4 mirror: asks empty -> mid NaN -> all fields undefined",
         bids=ladder(60000.0, 0.1, [1.8, 2.1, 1.0], up=False), asks=[]),
    dict(case_id="narrow_spread_1tick",
         scenario="§6.5 very narrow spread (1 tick)",
         bids=ladder(60000.0, 0.1, [3.0, 2.0, 1.0], up=False),
         asks=ladder(60000.1, 0.1, [3.0, 2.0, 1.0], up=True)),
    dict(case_id="wide_spread_200ticks",
         scenario="§6.6 wide spread (200 ticks), mid 60000",
         bids=ladder(59990.0, 0.1, [3.0, 2.0, 1.0], up=False),
         asks=ladder(60010.0, 0.1, [3.0, 2.0, 1.0], up=True)),
    dict(case_id="post_liquidation_proxy",
         scenario="§6.7 thinned ask after a sweep (SHAPE proxy; no liquidations feed on disk)",
         bids=ladder(60000.0, 0.1, [8, 6, 5, 4, 3], up=False),
         asks=ladder(60000.1, 0.1, [0.3, 0.2, 0.1], up=True)),
    dict(case_id="fast_move_up_proxy",
         scenario="§6.8 fast up-move, asks pulled, spread gapped (SHAPE proxy)",
         bids=ladder(60000.0, 0.1, [5, 4, 3], up=False),
         asks=ladder(60000.5, 0.1, [0.5, 0.4, 0.3], up=True)),
    dict(case_id="funding_flip_proxy",
         scenario="§6.9 neutral active book (SHAPE only; no derivative_ticker/funding feed on disk)",
         bids=ladder(60000.0, 0.1, [2.0, 3.5, 1.0, 0.7], up=False),
         asks=ladder(60000.1, 0.1, [1.8, 3.2, 1.4, 0.9], up=True)),
    dict(case_id="active_midday_mixed",
         scenario="§6.10 active mid-day mixed book",
         bids=ladder(60000.0, 0.1, [1.2, 4.5, 0.3, 2.8, 1.1, 0.6], up=False),
         asks=ladder(60000.2, 0.1, [0.9, 3.1, 1.7, 0.4, 2.2, 1.0], up=True)),
    # ---------- contract-critical edge cases ----------
    dict(case_id="boundary_level_inclusive",
         scenario="mid 60000, window 300.0: level at 59700.0 (|d|/mid==0.5%) IN, 59699.9 OUT",
         bids=[[59999.9, 1.0], [59700.0, 5.0], [59699.9, 9.9]],
         asks=[[60000.1, 1.0], [60300.0, 5.0], [60300.1, 9.9]]),
    dict(case_id="far_levels_excluded",
         scenario="huge levels far beyond the window must be dropped, not summed",
         bids=ladder(60000.0, 0.1, [1.0, 1.0], up=False) + [[58000.0, 9999.0]],
         asks=ladder(60000.1, 0.1, [1.0, 1.0], up=True) + [[62000.0, 9999.0]]),
    dict(case_id="two_levels_lowcount",
         scenario="§4.1 <3 levels: variance still computed (low-count, documented)",
         bids=ladder(60000.0, 0.1, [2.0, 1.0], up=False),
         asks=ladder(60000.1, 0.1, [2.0, 1.0], up=True)),
    dict(case_id="single_level_side",
         scenario="single bid level -> variance_bid == 0 (one point)",
         bids=[[60000.0, 3.0]],
         asks=ladder(60000.1, 0.1, [1.0, 1.0, 1.0], up=True)),
    dict(case_id="huge_spread_empty_window",
         scenario="spread so wide both best levels fall outside the 0.5% window -> both mass 0, imbalance null",
         bids=[[59000.0, 5.0]], asks=[[61000.0, 5.0]]),
    dict(case_id="empty_both_sides",
         scenario="both sides empty -> every field null",
         bids=[], asks=[]),
]


def _clean(v) -> float | None:
    """NaN -> None (JSON null); normalize -0.0 -> 0.0; otherwise a plain float."""
    if v is None:
        return None
    f = float(v)
    if math.isnan(f):
        return None
    return 0.0 if f == 0.0 else f  # collapse signed zero for a clean contract


def compute_expected(bids, asks, ts: int) -> dict:
    snap = geo.book_geometry_snapshot(
        bids, asks, tick_size=TICK, ts=ts,
        max_depth_pct=MAX_DEPTH_PCT, exp_lambda=EXP_LAMBDA, size_multiplier=1.0)
    tv = snap.to_test_vector(6)
    return {k: _clean(tv[k]) for k in FIELDS}


def build() -> dict:
    test_cases = []
    for i, c in enumerate(CASES):
        ts = T0 + i * 1000
        test_cases.append({
            "case_id": c["case_id"],
            "scenario": c["scenario"],
            "timestamp_ms": ts,
            "book_snapshot": {"bids": c["bids"], "asks": c["asks"]},
            "expected_features": compute_expected(c["bids"], c["asks"], ts),
        })
    return {
        "metadata": {
            "schema_version": 1,
            "source_file": "(synthetic)",
            "instrument": "Bybit BTCUSDT perpetual (synthetic books)",
            "reference_impl": "scripts/research/stage1/features_geometry.py::book_geometry_snapshot",
            "generated_by": "scripts/research/stage1/test_vectors_gen.py",
            "tick_size": TICK,
            "max_depth_pct": MAX_DEPTH_PCT,
            "exp_decay_lambda": EXP_LAMBDA,
            "size_multiplier": 1.0,
            "decimals": 6,
            "fields": FIELDS,
            "window_rule": "keep level iff |price - mid| / mid <= max_depth_pct (boundary INCLUSIVE)",
            "null_means": "NaN: undefined side (mass==0 / empty book / zero imbalance denominator)",
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "polars_version": None,
            "real_book_parity_note": (
                "Cross-implementation parity verified separately: book_reconstruction "
                "batch-vs-reference maxdiff == 2.18e-11 over 86,401 live snapshots "
                "(2026-06-02 BTCUSDT perp)."),
        },
        "test_cases": test_cases,
    }


def self_check(doc: dict) -> int:
    """Round-trip: reparse JSON, recompute from each book_snapshot, assert match."""
    reparsed = json.loads(json.dumps(doc))
    n = 0
    for case in reparsed["test_cases"]:
        bs = case["book_snapshot"]
        got = compute_expected(bs["bids"], bs["asks"], case["timestamp_ms"])
        exp = case["expected_features"]
        for k in FIELDS:
            a, b = got[k], exp[k]
            if a is None or b is None:
                assert a is None and b is None, f"{case['case_id']}.{k}: {a!r} vs {b!r}"
            else:
                assert abs(a - b) < 1e-12, f"{case['case_id']}.{k}: {a} vs {b}"
        n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate §6 feature_test_vectors.json")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "feature_test_vectors.json"))
    args = ap.parse_args(argv)

    doc = build()
    n = self_check(doc)

    out = Path(args.out)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    n_null = sum(1 for c in doc["test_cases"]
                 for v in c["expected_features"].values() if v is None)
    print(f"[test-vectors] {len(doc['test_cases'])} cases -> {out.name}", file=sys.stderr)
    print(f"[test-vectors] self-check PASSED on {n} cases "
          f"(reparse+recompute, 6-decimal contract); {n_null} null fields", file=sys.stderr)
    print(json.dumps({
        "cases": len(doc["test_cases"]),
        "self_check_passed": n,
        "null_fields": n_null,
        "out": str(out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
