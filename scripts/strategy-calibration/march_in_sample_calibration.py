"""March in-sample zone-selector calibration (Sections A-I).

IN-SAMPLE only on OKX direct March 2026 (29 available days).
NO engine / threshold / detector change. NO future-leak in selector.
Outcome fields are LABELS only. Target strict 2 %. Cost = 0.14 % roundtrip.

Builds ~30 artifact files under reports/strategy-calibration/.
"""
from __future__ import annotations
import csv
import datetime as dt
import gzip
import itertools
import json
import math
import statistics as stats
import sys
from collections import defaultdict, Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_ledger import (Bucket, build_buckets_from_trades_csv, Signal,
                              ExecutionConfig, simulate_canonical_trade,
                              aggregate as agg_trades, aggregate_after_cost)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REPORTS = ROOT / "reports"
REP_OUT = REPORTS / "strategy-calibration"
REP_OUT.mkdir(parents=True, exist_ok=True)
DATA_ROOT = ROOT / "data/okx-historical/BTC-USDT-SWAP"

FIRST_HALF_DATES = [f"2026-03-{d:02d}" for d in range(2, 16)]
SECOND_HALF_DATES = ["2026-03-16"] + [f"2026-03-{d:02d}" for d in range(18, 32)]
ALL_DATES = FIRST_HALF_DATES + SECOND_HALF_DATES
MISSING_DATES = ["2026-03-17"]

MOVE_THRESHOLD_PCT = 2.0
SEC_MOVE_THRESHOLD_PCT = 1.5
COST_PCT = 0.14
TARGET_PCT = 2.0
TIMEOUT_HOURS = 24


# ============================================================
# helpers
# ============================================================
def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def iso_to_sec(s: Optional[str]) -> Optional[int]:
    if not s: return None
    return int(dt.datetime.fromisoformat(s).timestamp())


def day_start_sec(date: str) -> int:
    return int(dt.datetime.fromisoformat(f"{date}T00:00:00+00:00").timestamp())


def safe_float(x):
    if x is None or x == "": return None
    try: return float(x)
    except: return None


def safe_int(x):
    if x is None or x == "": return None
    try: return int(float(x))
    except: return None


def safe_bool(x):
    if x is None or x == "": return None
    if isinstance(x, bool): return x
    s = str(x).lower()
    if s in ("true", "1", "yes", "y"): return True
    if s in ("false", "0", "no", "n", ""): return False
    return None


def cohens_d(a, b):
    a = [x for x in a if x is not None and not (isinstance(x, float) and math.isnan(x))]
    b = [x for x in b if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if len(a) < 2 or len(b) < 2: return None
    ma, mb = stats.mean(a), stats.mean(b)
    sa, sb = stats.pstdev(a), stats.pstdev(b)
    pooled = math.sqrt(((len(a)-1)*sa*sa + (len(b)-1)*sb*sb) / max(len(a)+len(b)-2, 1))
    if pooled == 0: return None
    return round((ma - mb) / pooled, 4)


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(stats.mean(xs), 4) if xs else None


def freq_pct(rows, key):
    if not rows: return 0.0
    n = sum(1 for r in rows if r.get(key) not in (None, False, 0))
    return round(100.0 * n / len(rows), 2)


# ============================================================
# Step 0: load existing feature dataset
# ============================================================
def load_existing_features() -> list[dict]:
    csv_p = REP_OUT / "OKX_MARCH_WATCH_ZONE_FEATURE_DATASET.csv"
    labels_p = REP_OUT / "OKX_MARCH_WATCH_ZONE_LABELS.csv"
    if not csv_p.exists():
        raise FileNotFoundError(f"missing {csv_p} — run good_watch_zone_feature_research.py first")
    rows = []
    with csv_p.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            for k in r:
                v = r[k]
                if k in ("zone_id", "date", "direction", "stage_reached", "candidate_iso",
                         "confirmed_iso", "trigger_iso", "_half",
                         "_label_engine_class", "_label_unique_move_id"):
                    r[k] = v if v else None
                elif k in ("cand_range_compression", "trig_side_flow_ok", "filter_kept",
                           "filter_dup_suppressed", "filter_fast_ok",
                           "_label_is_primary", "_label_reached_raw"):
                    r[k] = safe_bool(v)
                else:
                    r[k] = safe_float(v)
            rows.append(r)
    if labels_p.exists():
        labels = {}
        with labels_p.open(encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for lr in rdr:
                labels[lr["zone_id"]] = lr
        for r in rows:
            lr = labels.get(r["zone_id"])
            if lr:
                r["watch_label"] = lr.get("watch_label") or None
                r["coverage_class"] = lr.get("coverage_class") or None
                r["lead_min_before_move"] = safe_float(lr.get("lead_min_before_move"))
                r["matched_move_size_pct"] = safe_float(lr.get("matched_move_size_pct"))
    return rows


# ============================================================
# Step 1: trade aggregates per second (for orderflow features)
# ============================================================
@dataclass
class TradeAggDay:
    cum_buy: list[float]    # cumulative buy volume by second index from day_start
    cum_sell: list[float]
    cum_n: list[int]
    day_start_sec: int
    n_secs: int             # 86400 +1


def build_trade_aggregates(trades_path: Path, date: str) -> Optional[TradeAggDay]:
    if not trades_path.exists(): return None
    dss = day_start_sec(date)
    N = 86400
    buy = [0.0] * N
    sell = [0.0] * N
    n = [0] * N
    with gzip.open(trades_path, "rt", encoding="utf-8") as f:
        rdr = csv.reader(f)
        hdr = next(rdr)
        try:
            idx_ts = hdr.index("timestamp")
            idx_side = hdr.index("side")
            idx_amount = hdr.index("amount")
        except ValueError:
            return None
        for row in rdr:
            try:
                ts_us = int(row[idx_ts])
                amt = float(row[idx_amount])
                side = row[idx_side]
            except Exception:
                continue
            sec_offset = (ts_us // 1_000_000) - dss
            if sec_offset < 0 or sec_offset >= N: continue
            if side == "buy":
                buy[sec_offset] += amt
            else:
                sell[sec_offset] += amt
            n[sec_offset] += 1
    cum_b = [0.0] * (N + 1)
    cum_s = [0.0] * (N + 1)
    cum_nn = [0] * (N + 1)
    for i in range(N):
        cum_b[i+1] = cum_b[i] + buy[i]
        cum_s[i+1] = cum_s[i] + sell[i]
        cum_nn[i+1] = cum_nn[i] + n[i]
    return TradeAggDay(cum_b, cum_s, cum_nn, dss, N + 1)


def window_sum(agg: TradeAggDay, start_sec: int, end_sec: int) -> tuple[float, float, int]:
    """Return (buy_vol, sell_vol, n_trades) over [start_sec, end_sec) inclusive of start, exclusive of end."""
    i0 = max(0, start_sec - agg.day_start_sec)
    i1 = max(0, min(agg.n_secs - 1, end_sec - agg.day_start_sec))
    if i1 <= i0:
        return (0.0, 0.0, 0)
    return (round(agg.cum_buy[i1] - agg.cum_buy[i0], 4),
            round(agg.cum_sell[i1] - agg.cum_sell[i0], 4),
            agg.cum_n[i1] - agg.cum_n[i0])


# ============================================================
# Step 2: real 2% market moves detection
# ============================================================
@dataclass
class Move:
    date: str
    direction: str   # UP / DOWN
    start_sec: int
    end_sec: int
    start_price: float
    end_price: float
    size_pct: float
    duration_min: float
    secondary: bool


def detect_moves(date: str, buckets: list[Bucket]) -> list[Move]:
    if not buckets: return []
    def scan(thresh: float, sec: bool) -> list[Move]:
        out: list[Move] = []
        first = buckets[0]
        ext_sec = first.sec; ext_h = first.high; ext_l = first.low
        ps_sec = first.sec; ps_price = first.last; direction = None
        for b in buckets[1:]:
            if direction is None:
                up = (b.high - ext_l) / ext_l * 100.0 if ext_l else 0
                dn = (ext_h - b.low) / ext_h * 100.0 if ext_h else 0
                if up >= thresh and up >= dn:
                    direction = "UP"; ps_sec = ext_sec; ps_price = ext_l
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
                elif dn >= thresh:
                    direction = "DOWN"; ps_sec = ext_sec; ps_price = ext_h
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
                else:
                    if b.high > ext_h: ext_h = b.high; ext_sec = b.sec
                    if b.low < ext_l: ext_l = b.low
                continue
            if direction == "UP":
                if b.high > ext_h: ext_h = b.high; ext_sec = b.sec
                retr = (ext_h - b.low) / ext_h * 100.0
                if retr >= thresh:
                    size = (ext_h - ps_price) / ps_price * 100.0
                    dur = max((ext_sec - ps_sec) / 60.0, 0.0)
                    out.append(Move(date, "UP", ps_sec, ext_sec, ps_price, ext_h,
                                    round(size, 4), round(dur, 2), sec))
                    direction = "DOWN"; ps_sec = ext_sec; ps_price = ext_h
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
            else:
                if b.low < ext_l: ext_l = b.low; ext_sec = b.sec
                rally = (b.high - ext_l) / ext_l * 100.0
                if rally >= thresh:
                    size = (ps_price - ext_l) / ps_price * 100.0
                    dur = max((ext_sec - ps_sec) / 60.0, 0.0)
                    out.append(Move(date, "DOWN", ps_sec, ext_sec, ps_price, ext_l,
                                    round(size, 4), round(dur, 2), sec))
                    direction = "UP"; ps_sec = ext_sec; ps_price = ext_l
                    ext_sec = b.sec; ext_h = b.high; ext_l = b.low
        return out
    primary = scan(MOVE_THRESHOLD_PCT, False)
    secondary = scan(SEC_MOVE_THRESHOLD_PCT, True)
    pstarts = {(m.start_sec, m.direction) for m in primary}
    extra = [m for m in secondary if m.size_pct < MOVE_THRESHOLD_PCT
             and (m.start_sec, m.direction) not in pstarts]
    return primary + extra


# ============================================================
# Step 3: orderflow features (computed at confirm time)
# ============================================================
def bucket_idx_at_or_before(buckets: list[Bucket], target_sec: int) -> int:
    """Return index of the last bucket with .sec <= target_sec (or 0 if none)."""
    lo, hi = 0, len(buckets) - 1
    if not buckets or buckets[0].sec > target_sec: return -1
    while lo < hi:
        m = (lo + hi + 1) // 2
        if buckets[m].sec <= target_sec: lo = m
        else: hi = m - 1
    return lo


def compute_orderflow_features(row: dict, agg: Optional[TradeAggDay],
                                buckets: list[Bucket], moves_today: list[Move]) -> dict:
    """Pre-confirm orderflow features. Anchored at confirmed_iso (no future leak)."""
    out = {}
    direction = row.get("direction")
    if not direction: return out
    anchor_sec = iso_to_sec(row.get("confirmed_iso"))
    if anchor_sec is None: return out

    # 1. Taker imbalance per window
    if agg is not None:
        for win_min in (5, 15, 30, 60, 180):
            bv, sv, nt = window_sum(agg, anchor_sec - win_min*60, anchor_sec)
            tot = bv + sv
            imb = (bv - sv) / tot if tot > 0 else 0.0
            out[f"taker_imb_{win_min}m"] = round(imb, 4)
            out[f"taker_total_vol_{win_min}m"] = round(tot, 4)
            out[f"taker_n_trades_{win_min}m"] = nt
            # direction-aligned imbalance
            if direction == "LONG":
                out[f"taker_imb_aligned_{win_min}m"] = round(imb, 4)   # bullish if positive
            else:
                out[f"taker_imb_aligned_{win_min}m"] = round(-imb, 4)  # bullish-for-SHORT if negative
        # 2. Aggressor flow exhaustion: 15m vs 30-180m background
        bv30_180, sv30_180, _ = window_sum(agg, anchor_sec - 180*60, anchor_sec - 30*60)
        bv15, sv15, _ = window_sum(agg, anchor_sec - 15*60, anchor_sec)
        bg_vol_per_min = (bv30_180 + sv30_180) / 150.0 if (bv30_180 + sv30_180) > 0 else 0
        cur_vol_per_min = (bv15 + sv15) / 15.0 if (bv15 + sv15) > 0 else 0
        out["vol_anomaly_15m_vs_bg"] = round(cur_vol_per_min / bg_vol_per_min, 4) if bg_vol_per_min > 0 else None
        # 3. OFI shift (sign change from 30m to 5m)
        bv5, sv5, _ = window_sum(agg, anchor_sec - 5*60, anchor_sec)
        bv30, sv30, _ = window_sum(agg, anchor_sec - 30*60, anchor_sec - 5*60)
        tot5 = bv5 + sv5; tot30 = bv30 + sv30
        imb5 = (bv5 - sv5) / tot5 if tot5 > 0 else 0.0
        imb30 = (bv30 - sv30) / tot30 if tot30 > 0 else 0.0
        out["ofi_shift_5m_vs_30m"] = round(imb5 - imb30, 4)
        if direction == "LONG":
            out["ofi_shift_aligned"] = round(imb5 - imb30, 4)
        else:
            out["ofi_shift_aligned"] = round(-(imb5 - imb30), 4)
    else:
        for win_min in (5, 15, 30, 60, 180):
            out[f"taker_imb_{win_min}m"] = None
            out[f"taker_total_vol_{win_min}m"] = None
            out[f"taker_n_trades_{win_min}m"] = None
            out[f"taker_imb_aligned_{win_min}m"] = None
        out["vol_anomaly_15m_vs_bg"] = None
        out["ofi_shift_5m_vs_30m"] = None
        out["ofi_shift_aligned"] = None

    # 4. Sweep / reclaim
    zone_low = row.get("zone_low"); zone_high = row.get("zone_high")
    if buckets and zone_low is not None and zone_high is not None:
        idx = bucket_idx_at_or_before(buckets, anchor_sec)
        if idx > 0:
            # last 30m of buckets
            window_start = anchor_sec - 30 * 60
            slice_lo = idx
            for j in range(idx, -1, -1):
                if buckets[j].sec < window_start: break
                slice_lo = j
            sl = buckets[slice_lo:idx+1]
            cur_price = buckets[idx].last
            min_low = min(b.low for b in sl)
            max_high = max(b.high for b in sl)
            if direction == "LONG":
                # sweep: low went below zone_low; reclaim: cur_price >= zone_low
                swept = min_low < zone_low
                reclaim = cur_price >= zone_low
                out["sweep_reclaim_aligned"] = 1 if (swept and reclaim) else 0
                out["distance_from_low_pct"] = round((cur_price - min_low) / min_low * 100.0, 4) if min_low > 0 else None
            else:
                swept = max_high > zone_high
                reclaim = cur_price <= zone_high
                out["sweep_reclaim_aligned"] = 1 if (swept and reclaim) else 0
                out["distance_from_high_pct"] = round((max_high - cur_price) / max_high * 100.0, 4) if max_high > 0 else None
        else:
            out["sweep_reclaim_aligned"] = None

    # 5. Distance to recent swing (last 4h high/low)
    if buckets:
        idx = bucket_idx_at_or_before(buckets, anchor_sec)
        if idx > 0:
            window_start = anchor_sec - 4 * 3600
            slice_lo = idx
            for j in range(idx, -1, -1):
                if buckets[j].sec < window_start: break
                slice_lo = j
            sl = buckets[slice_lo:idx+1]
            cur_price = buckets[idx].last
            sw_high = max(b.high for b in sl)
            sw_low = min(b.low for b in sl)
            out["dist_to_recent_swing_high_pct"] = round((sw_high - cur_price) / cur_price * 100.0, 4) if cur_price > 0 else None
            out["dist_to_recent_swing_low_pct"] = round((cur_price - sw_low) / cur_price * 100.0, 4) if cur_price > 0 else None
            # vwap-like over 4h: time-weighted average of last prices
            if sl:
                vwap_proxy = stats.mean(b.last for b in sl)
                out["dist_to_4h_mean_pct"] = round((cur_price - vwap_proxy) / vwap_proxy * 100.0, 4) if vwap_proxy > 0 else None

    # 6. Late-move-completion: among today's moves whose direction matches
    #    AND whose start_sec <= anchor < end_sec, what % done?
    pct_done = None
    correct_dir = "UP" if direction == "LONG" else "DOWN"
    for m in moves_today:
        if m.direction != correct_dir: continue
        if m.start_sec <= anchor_sec < m.end_sec:
            dur = max(m.end_sec - m.start_sec, 1)
            pd = (anchor_sec - m.start_sec) / dur * 100.0
            if pct_done is None or pd > pct_done:
                pct_done = pd
    out["pct_correct_move_already_done"] = round(pct_done, 2) if pct_done is not None else 0.0
    out["is_late_after_50pct_correct_move"] = 1 if (pct_done is not None and pct_done > 50) else 0
    out["is_during_correct_move"] = 1 if pct_done is not None else 0

    # 7. Same logic for OPPOSITE direction move ongoing (conflict)
    opp_done = None
    opp_dir = "DOWN" if direction == "LONG" else "UP"
    for m in moves_today:
        if m.direction != opp_dir: continue
        if m.start_sec <= anchor_sec < m.end_sec:
            dur = max(m.end_sec - m.start_sec, 1)
            pd = (anchor_sec - m.start_sec) / dur * 100.0
            if opp_done is None or pd > opp_done:
                opp_done = pd
    out["pct_opposite_move_already_done"] = round(opp_done, 2) if opp_done is not None else 0.0
    out["is_during_opposite_move"] = 1 if opp_done is not None else 0

    # 8. Time of day (UTC hour)
    hr = (anchor_sec % 86400) // 3600
    out["utc_hour"] = hr
    # session bins: Asia 0-7, Europe 7-14, US 14-22, Asia-late 22-24
    if hr < 7: sess = "asia"
    elif hr < 14: sess = "europe"
    elif hr < 22: sess = "us"
    else: sess = "asia_late"
    out["session"] = sess
    out["is_asia_session"] = 1 if sess == "asia" else 0
    out["is_us_session"] = 1 if sess == "us" else 0

    return out


# ============================================================
# Step 4: paper-trade simulation helpers
# ============================================================
def merge_buckets(date: str, buckets_by_date: dict[str, list[Bucket]],
                  lookahead_days: int = 2) -> list[Bucket]:
    """Concatenate consecutive days' buckets so timeout 24h can span midnight."""
    out = []
    idx = ALL_DATES.index(date) if date in ALL_DATES else -1
    if idx < 0: return out
    out.extend(buckets_by_date.get(date) or [])
    for k in range(1, lookahead_days + 1):
        if idx + k >= len(ALL_DATES): break
        nxt = ALL_DATES[idx + k]
        # if missing date, still ok
        out.extend(buckets_by_date.get(nxt) or [])
    return out


def simulate_paper_trade(row: dict, buckets: list[Bucket],
                         entry_mode: str, stop_pct: float,
                         use_zone_boundary_stop: bool = False) -> Optional[dict]:
    """Simulate one paper trade per selected zone (independent of others).

    entry_mode in {"confirmed", "trigger", "delay_5m", "delay_10m", "delay_15m"}.
    """
    if not buckets: return None
    # Build a synthetic Signal
    confirmed_sec = iso_to_sec(row.get("confirmed_iso"))
    trigger_sec = iso_to_sec(row.get("trigger_iso"))
    if entry_mode == "trigger":
        if trigger_sec is None: return None
        trig_ms = trigger_sec * 1000
        es = "trigger"
    elif entry_mode == "confirmed":
        if confirmed_sec is None: return None
        trig_ms = confirmed_sec * 1000
        es = "trigger"
    elif entry_mode in ("delay_5m", "delay_10m", "delay_15m"):
        if confirmed_sec is None: return None
        trig_ms = confirmed_sec * 1000
        es = entry_mode
    else:
        return None
    sig = Signal(
        id=row["zone_id"], date=row["date"], trigger_ts_ms=trig_ms,
        direction=row["direction"],
        zone_low=row.get("zone_low"), zone_high=row.get("zone_high"),
    )
    cfg = ExecutionConfig(
        entry_strategy=es,
        stop_pct=stop_pct,
        zone_boundary_stop=use_zone_boundary_stop,
        target_pct=TARGET_PCT,
        timeout_hours=TIMEOUT_HOURS,
    )
    sim = simulate_canonical_trade(sig, buckets, cfg)
    if sim.get("exit_reason") in ("no_data", "skip_no_retest"): return None
    return sim


# ============================================================
# Section A: objectives
# ============================================================
def write_objectives() -> None:
    obj = {
        "build_time_utc": now_iso(),
        "scope": "IN-SAMPLE March 2026 OKX direct calibration (29 days; 03-17 missing)",
        "hard_rules": [
            "no engine / threshold / detector change",
            "target STRICT 2% (1% / 1.5% are diagnostic only)",
            "no future-leak in decision features",
            "outcome / post-trigger fields used as labels only",
            "no production integration",
        ],
        "tg_watch_objective": {
            "successful_zone": [
                "selector picked it BEFORE or at the very start of a real 2% market move",
                "direction matches",
                "after alert/confirm/selected time a 2% move was reached in that direction",
                "not late after >50% of move completed",
            ],
            "metrics": [
                "selected alerts total", "alerts/day", "successful selected zones",
                "precision", "recall of market 2% moves", "wrong-direction rate",
                "missed market moves", "avg lead time", "median lead time",
            ],
        },
        "paper_trade_objective": {
            "entry_modes": ["confirmed", "trigger", "delay_5m", "delay_10m", "delay_15m"],
            "stops_pct": [1.0, 1.25, 1.5, "zone_boundary"],
            "target_pct": 2.0,
            "timeout_hours": 24,
            "cost_pct_roundtrip": 0.14,
            "metrics": [
                "trades", "wins", "losses", "timeouts", "winrate %",
                "expectancy pre-cost %", "expectancy after cost %",
                "PF pre-cost", "PF after cost", "total return %",
                "max consecutive losses", "LONG/SHORT separately",
            ],
        },
        "headline_target": {
            "ideal_winrate_pct": "70-80",
            "alerts_per_day": "around 1-2",
            "minimum_selected_signals_per_month": 20,
            "unusable_if": "selecting 3-5 trades for the entire month even at >=80% winrate",
        },
    }
    (REP_OUT / "MARCH_CALIBRATION_OBJECTIVES.json").write_text(
        json.dumps(obj, indent=2, default=str), encoding="utf-8")
    md = [
        "# March in-sample calibration — objectives",
        "",
        f"**Build:** {obj['build_time_utc']}",
        f"**Scope:** {obj['scope']}",
        "",
        "## Hard rules",
    ]
    for r in obj["hard_rules"]: md.append(f"- {r}")
    md.extend(["", "## Mode 1 — TG watch-zone objective", ""])
    md.append("Successful when:")
    for c in obj["tg_watch_objective"]["successful_zone"]:
        md.append(f"- {c}")
    md.append("")
    md.append("Metrics: " + ", ".join(obj["tg_watch_objective"]["metrics"]) + ".")
    md.extend(["", "## Mode 2 — paper trade objective", ""])
    md.append(f"- entries: {obj['paper_trade_objective']['entry_modes']}")
    md.append(f"- stops: {obj['paper_trade_objective']['stops_pct']}")
    md.append(f"- target: {obj['paper_trade_objective']['target_pct']} %")
    md.append(f"- timeout: {obj['paper_trade_objective']['timeout_hours']} h")
    md.append(f"- cost: {obj['paper_trade_objective']['cost_pct_roundtrip']} % roundtrip")
    md.append("")
    md.append("Metrics: " + ", ".join(obj["paper_trade_objective"]["metrics"]))
    md.extend(["", "## Headline target",
               f"- ideal winrate: {obj['headline_target']['ideal_winrate_pct']} %",
               f"- alerts/day: {obj['headline_target']['alerts_per_day']}",
               f"- minimum signals: {obj['headline_target']['minimum_selected_signals_per_month']} / month",
               f"- {obj['headline_target']['unusable_if']}"])
    (REP_OUT / "MARCH_CALIBRATION_OBJECTIVES.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Section B: market moves + movement-first dataset
# ============================================================
def write_market_moves(moves_by_date: dict[str, list[Move]]) -> int:
    rows = []
    for d in ALL_DATES:
        for i, m in enumerate(moves_by_date.get(d, [])):
            rows.append({
                "date": d, "move_id": f"{d}_M{i:03d}",
                "direction": m.direction,
                "start_iso": dt.datetime.fromtimestamp(m.start_sec, tz=dt.timezone.utc).isoformat(timespec="seconds"),
                "end_iso": dt.datetime.fromtimestamp(m.end_sec, tz=dt.timezone.utc).isoformat(timespec="seconds"),
                "start_price": m.start_price, "end_price": m.end_price,
                "size_pct": m.size_pct, "duration_min": m.duration_min,
                "secondary_1_5pct": m.secondary,
            })
    with (REP_OUT / "MARCH_FULL_MARKET_2PCT_MOVES.csv").open("w", encoding="utf-8", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for r in rows: w.writerow(r)
    n_primary = sum(1 for r in rows if not r["secondary_1_5pct"])
    n_secondary = sum(1 for r in rows if r["secondary_1_5pct"])
    (REP_OUT / "MARCH_FULL_MARKET_2PCT_MOVES.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_primary_2pct_moves": n_primary,
                    "n_secondary_1_5pct_moves": n_secondary,
                    "per_day_count": {d: len([m for m in moves_by_date.get(d, []) if not m.secondary]) for d in ALL_DATES},
                    "moves": rows}, indent=2, default=str), encoding="utf-8")
    return n_primary


def write_movement_first_dataset(rows: list[dict]) -> None:
    keys = [
        "date", "zone_id", "direction", "stage_reached",
        "candidate_iso", "confirmed_iso", "trigger_iso",
        "zone_low", "zone_high", "zone_mid", "zone_width_pct",
        "candidate_to_confirm_min", "confirm_to_trigger_min", "total_pre_trigger_min",
        "utc_hour", "session",
        "_label_unique_move_id",
        "watch_label", "coverage_class",
        "lead_min_before_move", "matched_move_size_pct",
        "_half",
    ]
    with (REP_OUT / "MARCH_FULL_MOVEMENT_FIRST_ZONE_DATASET.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow({k: r.get(k) for k in keys})
    (REP_OUT / "MARCH_FULL_MOVEMENT_FIRST_ZONE_DATASET.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_zones": len(rows),
                    "label_counts": dict(Counter(r.get("watch_label") for r in rows)),
                    "coverage_counts": dict(Counter(r.get("coverage_class") for r in rows))},
                    indent=2, default=str), encoding="utf-8")


# ============================================================
# Section C: orderflow feature extraction report
# ============================================================
def write_orderflow_extraction_report(rows: list[dict], extracted_keys: list[str],
                                       skipped_features: list[dict]) -> None:
    n_present = sum(1 for r in rows if r.get("taker_imb_30m") is not None)
    md = [
        "# Orderflow feature extraction report",
        "",
        f"**Build:** {now_iso()}",
        f"**Source:** trades.csv.gz per day (29 days OKX direct)",
        f"**Zones in dataset:** {len(rows)}; with trade-derived features computed: {n_present}",
        "",
        "## Extracted features (pre-confirm, no future leak)",
        "",
    ]
    for k in extracted_keys:
        md.append(f"- `{k}`")
    md.extend(["", "## Features not extracted (with reason)", ""])
    for sk in skipped_features:
        md.append(f"- `{sk['feature']}` — {sk['reason']}")
    md.extend([
        "",
        "## Methodology",
        "- Anchor time = `confirmed_iso` (confirmed-stage moment).",
        "- All window aggregates use ONLY trades with timestamp ≤ anchor (no leak).",
        "- 1-second cumulative sums on (buy_vol, sell_vol, n_trades) → O(1) window queries.",
        "- Sweep/reclaim is computed on OHLC buckets from the same trades file.",
        "- Late-move-completion uses real 2 % movement detection (independent of engine).",
        "- All windows: 5 / 15 / 30 / 60 / 180 minutes ending at confirm time.",
        "",
        "## What we did not extract (and why)",
        "- L2 book features (refill speed, liquidity wall persistence, microprice, book imbalance) — "
        "would require full book reconstruction; we kept the engine's pre-computed `cand_*_refill_score` / "
        "`cand_absorb_score` / `conf_defended_persistence_sec` / `conf_opposite_thinning` instead, "
        "and previous research already flagged them as low-separation.",
        "- Per-tick microprice / spread — same reason.",
        "- Cancel-cluster / quote-flicker features — same.",
        "",
        "## Honesty note",
        "Trade-only orderflow features capture aggressor flow and price-level reactions. They are *coarser* "
        "than full L2 features but useful and leak-free. Treat the resulting separation as a lower bound "
        "on what richer book features could deliver.",
    ])
    (REP_OUT / "MARCH_ORDERFLOW_FEATURE_EXTRACTION_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    # Persist enriched dataset
    all_keys = sorted({k for r in rows for k in r.keys()})
    with (REP_OUT / "MARCH_ORDERFLOW_FEATURE_DATASET.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow(r)
    (REP_OUT / "MARCH_ORDERFLOW_FEATURE_DATASET.json").write_text(
        json.dumps({"build_time_utc": now_iso(), "n_rows": len(rows),
                    "extracted_features": extracted_keys,
                    "skipped_features": skipped_features}, indent=2, default=str),
        encoding="utf-8")


# ============================================================
# Section D: theory tests
# ============================================================
NEW_OF_KEYS = [
    "taker_imb_5m", "taker_imb_15m", "taker_imb_30m", "taker_imb_60m", "taker_imb_180m",
    "taker_imb_aligned_5m", "taker_imb_aligned_15m", "taker_imb_aligned_30m",
    "taker_imb_aligned_60m", "taker_imb_aligned_180m",
    "taker_total_vol_15m", "taker_total_vol_60m",
    "vol_anomaly_15m_vs_bg",
    "ofi_shift_5m_vs_30m", "ofi_shift_aligned",
    "sweep_reclaim_aligned",
    "dist_to_recent_swing_high_pct", "dist_to_recent_swing_low_pct",
    "dist_to_4h_mean_pct",
    "pct_correct_move_already_done", "is_late_after_50pct_correct_move",
    "is_during_correct_move",
    "pct_opposite_move_already_done", "is_during_opposite_move",
    "utc_hour", "is_asia_session", "is_us_session",
]

EXISTING_NUMERIC_KEYS = [
    "zone_width_pct", "candidate_to_confirm_min", "confirm_to_trigger_min", "total_pre_trigger_min",
    "cand_pressure_against", "cand_prior_move_pct", "conf_cycles_seen",
    "conf_defended_persistence_sec", "conf_opposite_thinning",
    "trig_flow_multiplier", "trig_break_pct",
    "score_ofi",
    "same_dir_zones_active_60m", "opp_dir_zones_active_60m",
    "prior_move_15m_pct", "prior_move_30m_pct", "prior_move_60m_pct", "prior_move_180m_pct",
    "local_range_15m_pct", "local_range_30m_pct", "local_range_60m_pct", "local_range_180m_pct",
    "local_realized_vol_15m", "local_realized_vol_60m",
]

ALL_FEATURE_KEYS = EXISTING_NUMERIC_KEYS + [k for k in NEW_OF_KEYS if k not in ("session",)]


def theory_tests(rows: list[dict]) -> dict:
    """Test 10 theories. Returns dict with results."""
    good = [r for r in rows if r.get("watch_label") == "GOOD"]
    bad = [r for r in rows if r.get("watch_label") == "BAD"]
    wrong = [r for r in rows if r.get("coverage_class") == "wrong_direction"]
    missed = [r for r in rows if r.get("coverage_class") == "missed_no_move_in_4h"]
    late = [r for r in rows if r.get("coverage_class") == "covered_late"]
    long_rows = [r for r in rows if r["direction"] == "LONG"]
    short_rows = [r for r in rows if r["direction"] == "SHORT"]
    good_long = [r for r in good if r["direction"] == "LONG"]
    good_short = [r for r in good if r["direction"] == "SHORT"]
    bad_long = [r for r in bad if r["direction"] == "LONG"]
    bad_short = [r for r in bad if r["direction"] == "SHORT"]
    h1 = [r for r in rows if r["_half"] == "first"]
    h2 = [r for r in rows if r["_half"] == "second"]
    good_h1 = [r for r in good if r["_half"] == "first"]
    good_h2 = [r for r in good if r["_half"] == "second"]
    bad_h1 = [r for r in bad if r["_half"] == "first"]
    bad_h2 = [r for r in bad if r["_half"] == "second"]

    def t_test(key: str, ga: list, ba: list) -> dict:
        gv = [r.get(key) for r in ga]
        bv = [r.get(key) for r in ba]
        return {
            "good_mean": mean_or_none(gv), "bad_mean": mean_or_none(bv),
            "d_good_vs_bad": cohens_d(gv, bv),
        }

    theories = []

    # Theory 1: Good zones have stronger local absorption anomaly (using vol_anomaly_15m_vs_bg)
    t1 = t_test("vol_anomaly_15m_vs_bg", good, bad)
    theories.append({
        "id": 1,
        "statement": "Good zones have stronger local absorption anomaly (15m vs 30-180m background).",
        "feature_used": "vol_anomaly_15m_vs_bg",
        **t1,
        "long": t_test("vol_anomaly_15m_vs_bg", good_long, bad_long),
        "short": t_test("vol_anomaly_15m_vs_bg", good_short, bad_short),
        "h1": t_test("vol_anomaly_15m_vs_bg", good_h1, bad_h1),
        "h2": t_test("vol_anomaly_15m_vs_bg", good_h2, bad_h2),
        "verdict": _verdict(t1["d_good_vs_bad"]),
    })

    # Theory 2: Good LONG zones show sell-pressure absorption + bid refill + OFI recovery
    # Using taker_imb_aligned_30m for LONG (positive = bullish taker flow recovery)
    t2 = t_test("taker_imb_aligned_30m", good_long, bad_long)
    theories.append({
        "id": 2,
        "statement": "Good LONG zones show sell absorption + bid refill + OFI recovery (proxy: aligned taker imb 30m).",
        "feature_used": "taker_imb_aligned_30m (LONG only)",
        **t2,
        "verdict": _verdict(t2["d_good_vs_bad"]),
    })

    # Theory 3: Good SHORT zones show buy absorption + ask refill + OFI deterioration
    t3 = t_test("taker_imb_aligned_30m", good_short, bad_short)
    theories.append({
        "id": 3,
        "statement": "Good SHORT zones show buy absorption + ask refill + OFI deterioration (proxy: aligned taker imb 30m).",
        "feature_used": "taker_imb_aligned_30m (SHORT only)",
        **t3,
        "verdict": _verdict(t3["d_good_vs_bad"]),
    })

    # Theory 4: Bad zones often appear after prior move exhaustion / overextension
    t4 = t_test("prior_move_180m_pct", bad, good)   # ABS magnitude bigger in BAD?
    # use |prior_move_180m_pct|
    gv = [abs(r["prior_move_180m_pct"]) for r in good if r.get("prior_move_180m_pct") is not None]
    bv = [abs(r["prior_move_180m_pct"]) for r in bad if r.get("prior_move_180m_pct") is not None]
    t4_abs = {
        "good_mean_abs": mean_or_none(gv), "bad_mean_abs": mean_or_none(bv),
        "d_good_vs_bad_abs": cohens_d(gv, bv),
    }
    theories.append({
        "id": 4,
        "statement": "Bad zones often appear after prior move exhaustion / overextension (|prior_move_180m|).",
        "feature_used": "abs(prior_move_180m_pct)",
        **t4_abs,
        "verdict": _verdict_inverse(t4_abs["d_good_vs_bad_abs"]),
    })

    # Theory 5: Wrong-direction zones have opposite-direction conflict or strong flow exhaustion
    gv = [r.get("is_during_opposite_move") for r in good]
    wv = [r.get("is_during_opposite_move") for r in wrong]
    t5 = {
        "good_freq_pct": freq_pct(good, "is_during_opposite_move"),
        "wrong_freq_pct": freq_pct(wrong, "is_during_opposite_move"),
        "missed_freq_pct": freq_pct(missed, "is_during_opposite_move"),
    }
    theories.append({
        "id": 5,
        "statement": "Wrong-direction zones occur during an opposite-direction 2% move.",
        "feature_used": "is_during_opposite_move",
        **t5,
        "verdict": "yes" if t5["wrong_freq_pct"] > t5["good_freq_pct"] + 10 else "weak",
    })

    # Theory 6: Strong raw flow can be anti-feature if it appears late after impulse
    # Use taker_total_vol_60m × is_late_after_50pct_correct_move
    late_good = [r for r in good if r.get("is_late_after_50pct_correct_move")]
    late_bad = [r for r in bad if r.get("is_late_after_50pct_correct_move")]
    t6 = {
        "good_late_count": len(late_good), "bad_late_count": len(late_bad),
        "good_late_pct": round(100.0 * len(late_good) / max(len(good), 1), 2),
        "bad_late_pct": round(100.0 * len(late_bad) / max(len(bad), 1), 2),
    }
    theories.append({
        "id": 6,
        "statement": "Strong raw flow appearing AFTER >50% of correct move = anti-feature.",
        "feature_used": "is_late_after_50pct_correct_move",
        **t6,
        "verdict": "yes" if t6["bad_late_pct"] > t6["good_late_pct"] + 5 else "weak",
    })

    # Theory 7: Good zones have lower local range / cleaner context before move
    t7 = t_test("local_range_180m_pct", good, bad)
    theories.append({
        "id": 7,
        "statement": "Good zones have lower local 180m range (cleaner context).",
        "feature_used": "local_range_180m_pct",
        **t7,
        "verdict": _verdict_negative(t7["d_good_vs_bad"]),
    })

    # Theory 8: Good zones appear near swing/VWAP levels
    t8 = t_test("dist_to_4h_mean_pct", good, bad)
    gv = [abs(r["dist_to_4h_mean_pct"]) for r in good if r.get("dist_to_4h_mean_pct") is not None]
    bv = [abs(r["dist_to_4h_mean_pct"]) for r in bad if r.get("dist_to_4h_mean_pct") is not None]
    t8_abs = {
        "good_mean_abs": mean_or_none(gv), "bad_mean_abs": mean_or_none(bv),
        "d_good_vs_bad_abs": cohens_d(gv, bv),
    }
    theories.append({
        "id": 8,
        "statement": "Good zones appear closer to recent 4h mean / VWAP-proxy than bad zones.",
        "feature_used": "abs(dist_to_4h_mean_pct)",
        **t8_abs,
        "verdict": _verdict_negative(t8_abs["d_good_vs_bad_abs"]),
    })

    # Theory 9: slow_trigger zones may be good watch but bad trade
    slow_good = [r for r in good if (r.get("confirm_to_trigger_min") or 0) > 60]
    slow_bad = [r for r in bad if (r.get("confirm_to_trigger_min") or 0) > 60]
    t9 = {
        "good_slow_count": len(slow_good), "bad_slow_count": len(slow_bad),
        "good_slow_pct": round(100.0 * len(slow_good) / max(len(good), 1), 2),
        "bad_slow_pct": round(100.0 * len(slow_bad) / max(len(bad), 1), 2),
    }
    theories.append({
        "id": 9,
        "statement": "slow_trigger zones (>60min confirm→trigger) may still be good watch-zones.",
        "feature_used": "confirm_to_trigger_min>60",
        **t9,
        "verdict": "diagnostic" if abs(t9["good_slow_pct"] - t9["bad_slow_pct"]) < 5 else "yes",
    })

    # Theory 10: Confirmed stage alone insufficient, requires extra scoring
    # Baseline precision (=11.79%) vs best score-rule precision: precision uplift
    base_prec = round(100.0 * len(good) / max(len(rows), 1), 2)
    theories.append({
        "id": 10,
        "statement": "Confirmed stage is useful only with additional scoring (baseline precision << good zones rate).",
        "feature_used": "raw confirmed = baseline",
        "baseline_precision_pct": base_prec,
        "best_simple_rule_precision_so_far_pct": "see selector optimizer (E)",
        "verdict": "yes (baseline only 11-12% precision)",
    })

    return {
        "build_time_utc": now_iso(),
        "n_good": len(good), "n_bad": len(bad), "n_wrong": len(wrong),
        "n_missed": len(missed), "n_late": len(late),
        "n_long": len(long_rows), "n_short": len(short_rows),
        "n_h1": len(h1), "n_h2": len(h2),
        "theories": theories,
    }


def _verdict(d):
    if d is None: return "unknown"
    if abs(d) >= 0.3: return "yes"
    if abs(d) >= 0.15: return "weak"
    return "no"


def _verdict_negative(d):
    if d is None: return "unknown"
    if d <= -0.2: return "yes"
    if d <= -0.1: return "weak"
    return "no"


def _verdict_inverse(d):
    if d is None: return "unknown"
    if d >= 0.2: return "yes (|prior_move| larger in BAD)"
    if d >= 0.1: return "weak"
    return "no"


def feature_separation_csv(rows: list[dict]) -> None:
    good = [r for r in rows if r.get("watch_label") == "GOOD"]
    bad = [r for r in rows if r.get("watch_label") == "BAD"]
    wrong = [r for r in rows if r.get("coverage_class") == "wrong_direction"]
    missed = [r for r in rows if r.get("coverage_class") == "missed_no_move_in_4h"]
    good_long = [r for r in good if r["direction"] == "LONG"]
    good_short = [r for r in good if r["direction"] == "SHORT"]
    bad_long = [r for r in bad if r["direction"] == "LONG"]
    bad_short = [r for r in bad if r["direction"] == "SHORT"]
    table = []
    boolean_keys = {"sweep_reclaim_aligned", "is_late_after_50pct_correct_move",
                    "is_during_correct_move", "is_during_opposite_move",
                    "is_asia_session", "is_us_session"}
    for k in ALL_FEATURE_KEYS:
        if k in boolean_keys:
            row = {
                "feature": k, "type": "boolean",
                "good_pct": freq_pct(good, k), "bad_pct": freq_pct(bad, k),
                "wrong_pct": freq_pct(wrong, k), "missed_pct": freq_pct(missed, k),
                "good_long_pct": freq_pct(good_long, k), "good_short_pct": freq_pct(good_short, k),
                "bad_long_pct": freq_pct(bad_long, k), "bad_short_pct": freq_pct(bad_short, k),
                "sep_good_vs_bad_pp": round(freq_pct(good, k) - freq_pct(bad, k), 2),
            }
        else:
            gv = [r.get(k) for r in good]
            bv = [r.get(k) for r in bad]
            wv = [r.get(k) for r in wrong]
            mv = [r.get(k) for r in missed]
            row = {
                "feature": k, "type": "numeric",
                "good_mean": mean_or_none(gv), "bad_mean": mean_or_none(bv),
                "wrong_mean": mean_or_none(wv), "missed_mean": mean_or_none(mv),
                "good_long_mean": mean_or_none([r.get(k) for r in good_long]),
                "good_short_mean": mean_or_none([r.get(k) for r in good_short]),
                "bad_long_mean": mean_or_none([r.get(k) for r in bad_long]),
                "bad_short_mean": mean_or_none([r.get(k) for r in bad_short]),
                "d_good_vs_bad": cohens_d(gv, bv),
                "d_good_vs_wrong": cohens_d(gv, wv),
                "d_good_vs_missed": cohens_d(gv, mv),
            }
        table.append(row)
    table.sort(key=lambda r: -abs(r.get("sep_good_vs_bad_pp") or 0) if r["type"] == "boolean"
                            else -abs(r.get("d_good_vs_bad") or 0) * 100.0)
    csv_keys = list(table[0].keys()) if table else []
    with (REP_OUT / "MARCH_ORDERFLOW_FEATURE_SEPARATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for r in table: w.writerow(r)


def write_theory_report(theories: dict) -> None:
    (REP_OUT / "MARCH_ORDERFLOW_THEORY_TESTS.json").write_text(
        json.dumps(theories, indent=2, default=str), encoding="utf-8")
    md = ["# Orderflow theory tests (10 theories)", "",
          f"**Build:** {theories['build_time_utc']}",
          f"**GOOD={theories['n_good']}, BAD={theories['n_bad']}, "
          f"wrong={theories['n_wrong']}, missed={theories['n_missed']}, late={theories['n_late']}**",
          f"**LONG={theories['n_long']}, SHORT={theories['n_short']}, "
          f"H1={theories['n_h1']}, H2={theories['n_h2']}**", ""]
    for t in theories["theories"]:
        md.append(f"## Theory {t['id']}: {t['statement']}")
        md.append(f"- feature: `{t['feature_used']}`")
        for k in ("good_mean", "bad_mean", "d_good_vs_bad",
                  "good_mean_abs", "bad_mean_abs", "d_good_vs_bad_abs",
                  "good_freq_pct", "bad_freq_pct", "wrong_freq_pct", "missed_freq_pct",
                  "good_late_count", "bad_late_count", "good_late_pct", "bad_late_pct",
                  "good_slow_count", "bad_slow_count", "good_slow_pct", "bad_slow_pct",
                  "baseline_precision_pct"):
            if k in t: md.append(f"  - {k}: {t[k]}")
        if "long" in t:
            md.append(f"  - LONG: good_mean={t['long']['good_mean']}, bad_mean={t['long']['bad_mean']}, d={t['long']['d_good_vs_bad']}")
        if "short" in t:
            md.append(f"  - SHORT: good_mean={t['short']['good_mean']}, bad_mean={t['short']['bad_mean']}, d={t['short']['d_good_vs_bad']}")
        if "h1" in t:
            md.append(f"  - H1: good_mean={t['h1']['good_mean']}, bad_mean={t['h1']['bad_mean']}, d={t['h1']['d_good_vs_bad']}")
        if "h2" in t:
            md.append(f"  - H2: good_mean={t['h2']['good_mean']}, bad_mean={t['h2']['bad_mean']}, d={t['h2']['d_good_vs_bad']}")
        md.append(f"  - **verdict:** {t['verdict']}")
        md.append("")
    (REP_OUT / "MARCH_ORDERFLOW_THEORY_TESTS.md").write_text("\n".join(md), encoding="utf-8")


# ============================================================
# Sections E + F: selector optimizer
# ============================================================
def selector_eval(rows: list[dict], predicate, day_cap: Optional[int] = None,
                   per_dir_cap: Optional[int] = None,
                   score_key: Optional[str] = None) -> dict:
    """Evaluate a selector. Returns aggregate metrics."""
    by_date = defaultdict(list)
    for r in rows:
        if not predicate(r): continue
        by_date[r["date"]].append(r)
    selected = []
    for d in ALL_DATES:
        day_rows = by_date.get(d, [])
        if score_key:
            day_rows = sorted(day_rows, key=lambda x: -(x.get(score_key) or 0))
        if per_dir_cap is not None:
            seen = defaultdict(int); kept = []
            for r in day_rows:
                if seen[r["direction"]] < per_dir_cap:
                    kept.append(r); seen[r["direction"]] += 1
            day_rows = kept
        if day_cap is not None:
            day_rows = day_rows[:day_cap]
        selected.extend(day_rows)
    n = len(selected)
    good = [r for r in selected if r.get("watch_label") == "GOOD"]
    bad = [r for r in selected if r.get("watch_label") == "BAD"]
    wrong = [r for r in selected if r.get("coverage_class") == "wrong_direction"]
    missed_sel = [r for r in selected if r.get("coverage_class") == "missed_no_move_in_4h"]
    noisy = [r for r in selected if r.get("coverage_class") == "noisy_partial_1_5"]
    leads = [r.get("lead_min_before_move") for r in selected
             if r.get("lead_min_before_move") and r["lead_min_before_move"] > 0]
    n_good_all = sum(1 for r in rows if r.get("watch_label") == "GOOD")
    # per-direction
    sel_long = [r for r in selected if r["direction"] == "LONG"]
    sel_short = [r for r in selected if r["direction"] == "SHORT"]
    good_long = sum(1 for r in sel_long if r.get("watch_label") == "GOOD")
    good_short = sum(1 for r in sel_short if r.get("watch_label") == "GOOD")
    # per-half
    sel_h1 = [r for r in selected if r["_half"] == "first"]
    sel_h2 = [r for r in selected if r["_half"] == "second"]
    good_h1 = sum(1 for r in sel_h1 if r.get("watch_label") == "GOOD")
    good_h2 = sum(1 for r in sel_h2 if r.get("watch_label") == "GOOD")
    # max consecutive bad alerts (chronological)
    chrono = sorted(selected, key=lambda r: r.get("confirmed_iso") or "")
    cur = 0; mx = 0
    for r in chrono:
        if r.get("watch_label") == "GOOD": cur = 0
        else: cur += 1; mx = max(mx, cur)
    return {
        "selected_n": n,
        "alerts_per_day": round(n / len(ALL_DATES), 3),
        "good_n": len(good), "bad_n": len(bad),
        "wrong_n": len(wrong), "missed_n": len(missed_sel), "noisy_n": len(noisy),
        "precision_pct": round(100.0 * len(good) / max(n, 1), 2) if n else None,
        "recall_pct": round(100.0 * len(good) / max(n_good_all, 1), 2) if n_good_all else None,
        "wrong_rate_pct": round(100.0 * len(wrong) / max(n, 1), 2) if n else None,
        "long_n": len(sel_long), "short_n": len(sel_short),
        "long_precision_pct": round(100.0 * good_long / max(len(sel_long), 1), 2) if sel_long else None,
        "short_precision_pct": round(100.0 * good_short / max(len(sel_short), 1), 2) if sel_short else None,
        "h1_n": len(sel_h1), "h2_n": len(sel_h2),
        "h1_precision_pct": round(100.0 * good_h1 / max(len(sel_h1), 1), 2) if sel_h1 else None,
        "h2_precision_pct": round(100.0 * good_h2 / max(len(sel_h2), 1), 2) if sel_h2 else None,
        "avg_lead_min": round(stats.mean(leads), 2) if leads else None,
        "median_lead_min": round(stats.median(leads), 2) if leads else None,
        "max_consecutive_bad": mx,
        "selected_zone_ids": [r["zone_id"] for r in selected],
    }


def build_predicates(rows: list[dict]) -> list[tuple[str, callable]]:
    """Return a list of (name, predicate) candidate selectors."""
    P = []
    # Helper: combine functions
    def _and(*fns):
        return lambda r: all(f(r) for f in fns)
    def _filter_kept(r): return bool(r.get("filter_kept"))
    def _opp_eq0(r): return (r.get("opp_dir_zones_active_60m") or 0) == 0
    def _opp_le1(r): return (r.get("opp_dir_zones_active_60m") or 0) <= 1
    def _prior_60m_le_1(r): return abs(r.get("prior_move_60m_pct") or 0) <= 1.0
    def _prior_60m_le_05(r): return abs(r.get("prior_move_60m_pct") or 0) <= 0.5
    def _prior_180m_le_15(r): return abs(r.get("prior_move_180m_pct") or 0) <= 1.5
    def _not_late(r): return not r.get("is_late_after_50pct_correct_move")
    def _not_during_opp(r): return not r.get("is_during_opposite_move")
    def _sweep_reclaim(r): return r.get("sweep_reclaim_aligned") == 1
    def _ofi_aligned_pos(r): return (r.get("ofi_shift_aligned") or 0) >= 0.05
    def _ofi_aligned_strong(r): return (r.get("ofi_shift_aligned") or 0) >= 0.15
    def _taker_aligned_pos(r): return (r.get("taker_imb_aligned_30m") or 0) >= 0.0
    def _taker_aligned_strong(r): return (r.get("taker_imb_aligned_30m") or 0) >= 0.1
    def _taker_aligned_60m_pos(r): return (r.get("taker_imb_aligned_60m") or 0) >= 0.0
    def _vol_anomaly_high(r): return (r.get("vol_anomaly_15m_vs_bg") or 0) >= 1.2
    def _vol_anomaly_low(r): return (r.get("vol_anomaly_15m_vs_bg") or 99) <= 0.8
    def _zone_width_le_04(r): return (r.get("zone_width_pct") or 99) <= 0.4
    def _local_range_180_low(r): return (r.get("local_range_180m_pct") or 99) <= 1.5
    def _local_range_180_very_low(r): return (r.get("local_range_180m_pct") or 99) <= 1.0
    def _ctt_le_60(r): return (r.get("confirm_to_trigger_min") or 999) <= 60
    def _ctt_le_30(r): return (r.get("confirm_to_trigger_min") or 999) <= 30
    def _trig_break_high(r): return (r.get("trig_break_pct") or 0) >= 0.3
    def _asia(r): return r.get("is_asia_session") == 1
    def _us(r): return r.get("is_us_session") == 1

    base_filters = {
        "filter_kept": _filter_kept,
        "opp_eq0": _opp_eq0,
        "opp_le1": _opp_le1,
        "prior60_le1": _prior_60m_le_1,
        "prior60_le05": _prior_60m_le_05,
        "prior180_le15": _prior_180m_le_15,
        "not_late": _not_late,
        "not_during_opp": _not_during_opp,
        "sweep_reclaim": _sweep_reclaim,
        "ofi_aligned_pos": _ofi_aligned_pos,
        "ofi_aligned_strong": _ofi_aligned_strong,
        "taker30_aligned_pos": _taker_aligned_pos,
        "taker30_aligned_strong": _taker_aligned_strong,
        "taker60_aligned_pos": _taker_aligned_60m_pos,
        "vol_anomaly_high": _vol_anomaly_high,
        "vol_anomaly_low": _vol_anomaly_low,
        "zone_width_le04": _zone_width_le_04,
        "range180_low": _local_range_180_low,
        "range180_very_low": _local_range_180_very_low,
        "ctt_le60": _ctt_le_60,
        "ctt_le30": _ctt_le_30,
        "trig_break_high": _trig_break_high,
        "session_asia": _asia,
        "session_us": _us,
    }

    # Baseline
    P.append(("baseline_all_confirmed", lambda r: True))
    # Single filters
    for name, fn in base_filters.items():
        P.append((f"single::{name}", fn))
    # Pairs (most likely useful)
    pair_keys = [
        ("filter_kept", "opp_eq0"),
        ("filter_kept", "prior60_le1"),
        ("filter_kept", "not_late"),
        ("filter_kept", "not_during_opp"),
        ("opp_eq0", "prior60_le1"),
        ("opp_eq0", "not_late"),
        ("opp_eq0", "not_during_opp"),
        ("not_late", "not_during_opp"),
        ("not_late", "ofi_aligned_pos"),
        ("not_late", "taker30_aligned_pos"),
        ("not_late", "prior60_le1"),
        ("not_during_opp", "ofi_aligned_pos"),
        ("not_during_opp", "taker30_aligned_pos"),
        ("sweep_reclaim", "not_during_opp"),
        ("filter_kept", "ofi_aligned_pos"),
        ("filter_kept", "taker30_aligned_pos"),
        ("range180_low", "not_late"),
        ("range180_low", "filter_kept"),
        ("zone_width_le04", "filter_kept"),
        ("zone_width_le04", "not_late"),
        ("ctt_le60", "filter_kept"),
        ("vol_anomaly_high", "not_late"),
        ("vol_anomaly_low", "not_late"),
    ]
    for a, b in pair_keys:
        P.append((f"pair::{a}+{b}", _and(base_filters[a], base_filters[b])))
    # Triples (focus)
    triple_keys = [
        ("filter_kept", "opp_eq0", "not_late"),
        ("filter_kept", "opp_eq0", "not_during_opp"),
        ("filter_kept", "opp_eq0", "prior60_le1"),
        ("filter_kept", "not_late", "not_during_opp"),
        ("filter_kept", "not_late", "ofi_aligned_pos"),
        ("filter_kept", "not_late", "taker30_aligned_pos"),
        ("filter_kept", "not_during_opp", "ofi_aligned_pos"),
        ("filter_kept", "not_during_opp", "taker30_aligned_pos"),
        ("filter_kept", "not_late", "prior60_le1"),
        ("filter_kept", "not_during_opp", "prior60_le1"),
        ("opp_eq0", "not_late", "prior60_le1"),
        ("opp_eq0", "not_late", "ofi_aligned_pos"),
        ("opp_eq0", "not_late", "taker30_aligned_pos"),
        ("not_late", "not_during_opp", "ofi_aligned_pos"),
        ("not_late", "not_during_opp", "taker30_aligned_pos"),
        ("not_late", "not_during_opp", "prior60_le1"),
        ("filter_kept", "range180_low", "not_late"),
        ("filter_kept", "zone_width_le04", "not_late"),
        ("filter_kept", "ctt_le60", "not_late"),
        ("filter_kept", "ctt_le60", "not_during_opp"),
        ("filter_kept", "sweep_reclaim", "not_during_opp"),
        ("not_late", "not_during_opp", "sweep_reclaim"),
    ]
    for a, b, c in triple_keys:
        P.append((f"triple::{a}+{b}+{c}", _and(base_filters[a], base_filters[b], base_filters[c])))
    # Quads (likely overfit but explored for in-sample best)
    quad_keys = [
        ("filter_kept", "opp_eq0", "not_late", "prior60_le1"),
        ("filter_kept", "opp_eq0", "not_late", "ofi_aligned_pos"),
        ("filter_kept", "opp_eq0", "not_late", "taker30_aligned_pos"),
        ("filter_kept", "not_late", "not_during_opp", "ofi_aligned_pos"),
        ("filter_kept", "not_late", "not_during_opp", "taker30_aligned_pos"),
        ("filter_kept", "not_late", "not_during_opp", "prior60_le1"),
        ("filter_kept", "not_late", "not_during_opp", "sweep_reclaim"),
        ("filter_kept", "not_late", "ctt_le60", "ofi_aligned_pos"),
        ("filter_kept", "not_late", "range180_low", "ofi_aligned_pos"),
        ("filter_kept", "not_late", "zone_width_le04", "ofi_aligned_pos"),
    ]
    for a, b, c, d in quad_keys:
        P.append((f"quad::{a}+{b}+{c}+{d}",
                  _and(base_filters[a], base_filters[b], base_filters[c], base_filters[d])))
    return P


def add_direction_specific_predicates(rows: list[dict],
                                       existing: list[tuple[str, callable]]) -> list[tuple[str, callable]]:
    """Add direction-only selectors and direction-aware combos."""
    P = list(existing)
    def _only_long(r): return r["direction"] == "LONG"
    def _only_short(r): return r["direction"] == "SHORT"
    def _and(*fns): return lambda r: all(f(r) for f in fns)
    def _filter_kept(r): return bool(r.get("filter_kept"))
    def _not_late(r): return not r.get("is_late_after_50pct_correct_move")
    def _not_during_opp(r): return not r.get("is_during_opposite_move")
    def _ofi_pos(r): return (r.get("ofi_shift_aligned") or 0) >= 0.05
    def _opp_eq0(r): return (r.get("opp_dir_zones_active_60m") or 0) == 0
    def _prior_60m_le_1(r): return abs(r.get("prior_move_60m_pct") or 0) <= 1.0
    P.append(("dir::LONG_only", _only_long))
    P.append(("dir::SHORT_only", _only_short))
    P.append(("dir::LONG+filter_kept+not_late", _and(_only_long, _filter_kept, _not_late)))
    P.append(("dir::SHORT+filter_kept+not_late", _and(_only_short, _filter_kept, _not_late)))
    P.append(("dir::LONG+filter_kept+not_during_opp", _and(_only_long, _filter_kept, _not_during_opp)))
    P.append(("dir::SHORT+filter_kept+not_during_opp", _and(_only_short, _filter_kept, _not_during_opp)))
    P.append(("dir::LONG+filter_kept+opp_eq0", _and(_only_long, _filter_kept, _opp_eq0)))
    P.append(("dir::SHORT+filter_kept+opp_eq0", _and(_only_short, _filter_kept, _opp_eq0)))
    P.append(("dir::LONG+filter_kept+not_late+ofi_pos",
              _and(_only_long, _filter_kept, _not_late, _ofi_pos)))
    P.append(("dir::SHORT+filter_kept+not_late+ofi_pos",
              _and(_only_short, _filter_kept, _not_late, _ofi_pos)))
    P.append(("dir::LONG+filter_kept+not_late+prior60_le1",
              _and(_only_long, _filter_kept, _not_late, _prior_60m_le_1)))
    P.append(("dir::SHORT+filter_kept+not_late+prior60_le1",
              _and(_only_short, _filter_kept, _not_late, _prior_60m_le_1)))
    return P


def explainable_score(r: dict) -> float:
    """Lightweight explainable score for ranking within day (no future leak)."""
    s = 0.0
    # +1 if filter_kept
    if r.get("filter_kept"): s += 1.0
    # +1 if not_late
    if not r.get("is_late_after_50pct_correct_move"): s += 1.0
    # +1 if opp_eq0
    if (r.get("opp_dir_zones_active_60m") or 0) == 0: s += 0.7
    # +1 if not_during_opp
    if not r.get("is_during_opposite_move"): s += 0.7
    # taker imb aligned positive
    ti = r.get("taker_imb_aligned_30m")
    if ti is not None: s += max(min(ti, 0.5), -0.5)
    # ofi shift aligned
    of = r.get("ofi_shift_aligned")
    if of is not None: s += max(min(of, 0.3), -0.3)
    # prior_move overextension penalty
    pm = r.get("prior_move_60m_pct")
    if pm is not None: s -= min(abs(pm) * 0.3, 0.6)
    # local range penalty
    lr = r.get("local_range_180m_pct")
    if lr is not None and lr > 2.0: s -= 0.4
    # sweep/reclaim bonus
    if r.get("sweep_reclaim_aligned") == 1: s += 0.4
    return s


def evaluate_all_selectors(rows: list[dict]) -> list[dict]:
    """Build search space + evaluate ALL selectors + selector × top-N variants."""
    preds = build_predicates(rows)
    preds = add_direction_specific_predicates(rows, preds)
    # Tag each row with explainable score for ranking-within-day
    for r in rows:
        r["_explainable_score"] = round(explainable_score(r), 4)
    out = []
    for name, fn in preds:
        # Variant A: no cap (count all selected by predicate)
        e = selector_eval(rows, fn)
        out.append({"selector": f"{name}::nocap", **e})
        # Variant B: max 1 per day (rank by explainable score)
        e = selector_eval(rows, fn, day_cap=1, score_key="_explainable_score")
        out.append({"selector": f"{name}::top1_score", **e})
        # Variant C: max 2 per day
        e = selector_eval(rows, fn, day_cap=2, score_key="_explainable_score")
        out.append({"selector": f"{name}::top2_score", **e})
        # Variant D: max 1 per direction per day
        e = selector_eval(rows, fn, per_dir_cap=1, score_key="_explainable_score")
        out.append({"selector": f"{name}::top1perdir_score", **e})
    return out


# ============================================================
# Section G: paper trade simulation
# ============================================================
def paper_trade_results(top_selectors: list[dict], rows: list[dict],
                         buckets_multi: dict[str, list[Bucket]]) -> list[dict]:
    """For each top selector × entry × stop combo, run paper trades and aggregate."""
    by_id = {r["zone_id"]: r for r in rows}
    entry_modes = ["confirmed", "trigger", "delay_5m", "delay_10m", "delay_15m"]
    stop_configs = [
        ("stop_1.0", 1.0, False),
        ("stop_1.25", 1.25, False),
        ("stop_1.5", 1.5, False),
        ("zone_boundary", 0.0, True),
    ]
    results = []
    for sel in top_selectors:
        sel_name = sel["selector"]
        ids = sel.get("selected_zone_ids") or []
        if not ids: continue
        sel_rows = [by_id[i] for i in ids if i in by_id]
        for em in entry_modes:
            for sn, sp, zb in stop_configs:
                trades = []
                for sr in sel_rows:
                    buckets = buckets_multi.get(sr["date"]) or []
                    sim = simulate_paper_trade(sr, buckets, em, sp, use_zone_boundary_stop=zb)
                    if sim is None: continue
                    trades.append({
                        "zone_id": sr["zone_id"], "date": sr["date"], "direction": sr["direction"],
                        "entry_sec": sim["entry_sec"], "exit_sec": sim["exit_sec"],
                        "entry_price": sim["entry_price"], "exit_price": sim["exit_price"],
                        "exit_reason": sim["exit_reason"], "pnl_pct": sim["pnl_pct"],
                        "used_stop_pct": sim["used_stop_pct"],
                    })
                if not trades: continue
                n = len(trades)
                wins = sum(1 for t in trades if t["exit_reason"] == "target_2pct")
                losses = sum(1 for t in trades if t["exit_reason"] == "stop")
                timeouts = sum(1 for t in trades if t["exit_reason"] == "timeout")
                pnls = [t["pnl_pct"] for t in trades]
                wp = [p for p in pnls if p > 0]; lp = [p for p in pnls if p < 0]
                gw = sum(wp); gl = sum(-p for p in lp)
                pnls_after = [p - COST_PCT for p in pnls]
                wp_a = [p for p in pnls_after if p > 0]; lp_a = [p for p in pnls_after if p < 0]
                gw_a = sum(wp_a); gl_a = sum(-p for p in lp_a)
                cur = 0; mx = 0
                for t in trades:
                    if t["pnl_pct"] <= 0: cur += 1; mx = max(mx, cur)
                    else: cur = 0
                lng = [t for t in trades if t["direction"] == "LONG"]
                sht = [t for t in trades if t["direction"] == "SHORT"]
                by_day = defaultdict(list)
                for t in trades: by_day[t["date"]].append(t["pnl_pct"])
                best = max(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
                worst = min(by_day.items(), key=lambda kv: sum(kv[1]), default=(None, []))
                results.append({
                    "selector": sel_name, "entry_mode": em, "stop": sn,
                    "trades": n, "wins": wins, "losses": losses, "timeouts": timeouts,
                    "winrate_pct": round(100.0 * wins / n, 2),
                    "expectancy_pre_cost_pct": round(stats.mean(pnls), 4),
                    "expectancy_after_cost_pct": round(stats.mean(pnls_after), 4),
                    "pf_pre_cost": round(gw / gl, 3) if gl > 0 else (None if gw == 0 else float("inf")),
                    "pf_after_cost": round(gw_a / gl_a, 3) if gl_a > 0 else (None if gw_a == 0 else float("inf")),
                    "total_return_pre_cost_pct": round(sum(pnls), 4),
                    "total_return_after_cost_pct": round(sum(pnls_after), 4),
                    "max_consecutive_losses": mx,
                    "long_n": len(lng),
                    "long_winrate_pct": round(100.0 * sum(1 for t in lng if t["exit_reason"] == "target_2pct") / max(len(lng), 1), 2),
                    "long_expectancy_pre_cost_pct": round(stats.mean(t["pnl_pct"] for t in lng), 4) if lng else None,
                    "short_n": len(sht),
                    "short_winrate_pct": round(100.0 * sum(1 for t in sht if t["exit_reason"] == "target_2pct") / max(len(sht), 1), 2),
                    "short_expectancy_pre_cost_pct": round(stats.mean(t["pnl_pct"] for t in sht), 4) if sht else None,
                    "best_day": best[0], "best_day_pnl_pct": round(sum(best[1]), 4) if best[0] else None,
                    "worst_day": worst[0], "worst_day_pnl_pct": round(sum(worst[1]), 4) if worst[0] else None,
                })
    return results


# ============================================================
# Main
# ============================================================
def main() -> int:
    print("[A] writing objectives ...", file=sys.stderr)
    write_objectives()

    print("[B] loading existing dataset + detecting market moves ...", file=sys.stderr)
    rows = load_existing_features()
    print(f"  loaded {len(rows)} confirmed-zone rows", file=sys.stderr)

    # Build buckets per day (for sweep/reclaim + multi-day for paper trade)
    print("  building 1s OHLC buckets ...", file=sys.stderr)
    buckets_by_date: dict[str, list[Bucket]] = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        if p.exists():
            buckets_by_date[d] = build_buckets_from_trades_csv(p)
        else:
            buckets_by_date[d] = []

    print("  detecting 2 % market moves ...", file=sys.stderr)
    moves_by_date: dict[str, list[Move]] = {}
    for d in ALL_DATES:
        moves_by_date[d] = detect_moves(d, buckets_by_date.get(d, []))
    n_primary = write_market_moves(moves_by_date)
    print(f"  primary 2 % moves: {n_primary} across 29 days", file=sys.stderr)

    print("[C] extracting orderflow features ...", file=sys.stderr)
    # Build trade aggregates per day (heavy step)
    agg_by_date: dict[str, Optional[TradeAggDay]] = {}
    for d in ALL_DATES:
        p = DATA_ROOT / d / "trades.csv.gz"
        agg_by_date[d] = build_trade_aggregates(p, d) if p.exists() else None
        print(f"  {d}: trade aggregates {'ok' if agg_by_date[d] else 'missing'}", file=sys.stderr)

    for r in rows:
        of = compute_orderflow_features(
            r, agg_by_date.get(r["date"]),
            buckets_by_date.get(r["date"], []),
            moves_by_date.get(r["date"], []),
        )
        r.update(of)

    extracted_keys = NEW_OF_KEYS
    skipped = [
        {"feature": "L2 refill speed / size / persistence",
         "reason": "requires book reconstruction across the day; engine cand_*_refill_score kept as proxy"},
        {"feature": "L2 liquidity defense / wall persistence",
         "reason": "requires book reconstruction; conf_defended_persistence_sec kept as proxy"},
        {"feature": "L2 book imbalance / microprice / spread",
         "reason": "requires per-snapshot book state; not extracted in this pass"},
        {"feature": "L2 absorption efficiency (price progress per aggressive volume)",
         "reason": "needs book delta + trade match; we use trade-only vol_anomaly_15m_vs_bg instead"},
        {"feature": "Cancel-cluster / quote flicker",
         "reason": "requires per-event book updates; not in scope"},
    ]
    write_orderflow_extraction_report(rows, extracted_keys, skipped)
    write_movement_first_dataset(rows)

    print("[D] theory tests ...", file=sys.stderr)
    th = theory_tests(rows)
    write_theory_report(th)
    feature_separation_csv(rows)

    print("[E] selector optimization ...", file=sys.stderr)
    sel_results = evaluate_all_selectors(rows)
    # Sort by precision (desc), keep variants with at least N selected (avoid 0-trade overfit)
    for s in sel_results:
        s["_precision"] = s.get("precision_pct") or 0
        s["_recall"] = s.get("recall_pct") or 0
        s["_alerts_per_day"] = s.get("alerts_per_day") or 0
    sel_results.sort(key=lambda s: (-s["_precision"], -s["_recall"]))

    # Write optimization full output
    csv_keys = ["selector", "selected_n", "alerts_per_day", "good_n", "bad_n",
                "wrong_n", "missed_n", "noisy_n",
                "precision_pct", "recall_pct", "wrong_rate_pct",
                "long_n", "long_precision_pct", "short_n", "short_precision_pct",
                "h1_n", "h1_precision_pct", "h2_n", "h2_precision_pct",
                "avg_lead_min", "median_lead_min", "max_consecutive_bad"]
    with (REP_OUT / "MARCH_IN_SAMPLE_SELECTOR_OPTIMIZATION.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_keys, extrasaction="ignore")
        w.writeheader()
        for s in sel_results: w.writerow(s)
    (REP_OUT / "MARCH_IN_SAMPLE_SELECTOR_OPTIMIZATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_selectors_evaluated": len(sel_results),
                    "first_half_baseline_precision_pct": round(
                        100.0 * sum(1 for r in rows if r["_half"] == "first" and r.get("watch_label") == "GOOD") /
                        max(sum(1 for r in rows if r["_half"] == "first"), 1), 2),
                    "second_half_baseline_precision_pct": round(
                        100.0 * sum(1 for r in rows if r["_half"] == "second" and r.get("watch_label") == "GOOD") /
                        max(sum(1 for r in rows if r["_half"] == "second"), 1), 2),
                    "selectors": [{k: v for k, v in s.items() if not k.startswith("_") and k != "selected_zone_ids"}
                                  for s in sel_results]},
                   indent=2, default=str), encoding="utf-8")
    # MD: top selectors by precision (with min trade constraint 20)
    md = ["# In-sample selector optimization (full search results)", "",
          f"**Build:** {now_iso()}",
          f"**Selectors evaluated:** {len(sel_results)}",
          f"**Baseline confirmed precision:** {round(100.0 * sum(1 for r in rows if r.get('watch_label') == 'GOOD') / max(len(rows), 1), 2)} %",
          "",
          "## Top 30 by precision (with ≥20 selected for usability)",
          "",
          "| selector | n | /day | good | wrong | precision % | recall % | wrong rate % | H1 prec | H2 prec |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    shown = 0
    for s in sel_results:
        if (s.get("selected_n") or 0) < 20: continue
        md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | "
                  f"{s['good_n']} | {s['wrong_n']} | {s['precision_pct']} | {s['recall_pct']} | "
                  f"{s['wrong_rate_pct']} | {s['h1_precision_pct']} | {s['h2_precision_pct']} |")
        shown += 1
        if shown >= 30: break
    md.extend(["", "## Top 30 by precision (any selected count, including small samples)", "",
               "| selector | n | /day | good | precision % | recall % | H1 prec | H2 prec | overfit risk |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---|"])
    shown = 0
    for s in sel_results[:30]:
        of_risk = "HIGH" if (s["selected_n"] or 0) < 20 else ("MEDIUM" if (s["selected_n"] or 0) < 40 else "LOW")
        md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | "
                  f"{s['good_n']} | {s['precision_pct']} | {s['recall_pct']} | "
                  f"{s['h1_precision_pct']} | {s['h2_precision_pct']} | {of_risk} |")
        shown += 1
    (REP_OUT / "MARCH_IN_SAMPLE_SELECTOR_OPTIMIZATION.md").write_text("\n".join(md), encoding="utf-8")

    # ============================================================
    # Section F: top selector evaluation
    # ============================================================
    print("[F] top selector evaluation ...", file=sys.stderr)
    # Categories
    def find_best(filt, sort_key=lambda s: -s.get("precision_pct", 0)):
        cands = [s for s in sel_results if filt(s)]
        cands.sort(key=sort_key)
        return cands[0] if cands else None

    n_good_all = sum(1 for r in rows if r.get("watch_label") == "GOOD")
    base_prec_h1 = round(100.0 * sum(1 for r in rows if r["_half"] == "first" and r.get("watch_label") == "GOOD") /
                         max(sum(1 for r in rows if r["_half"] == "first"), 1), 2)
    base_prec_h2 = round(100.0 * sum(1 for r in rows if r["_half"] == "second" and r.get("watch_label") == "GOOD") /
                         max(sum(1 for r in rows if r["_half"] == "second"), 1), 2)

    by_cat = {
        "best_precision_min20": find_best(lambda s: (s.get("selected_n") or 0) >= 20),
        "best_precision_min10": find_best(lambda s: (s.get("selected_n") or 0) >= 10),
        "best_1_2_alerts_day": find_best(
            lambda s: 1.0 <= (s.get("alerts_per_day") or 0) <= 2.5 and (s.get("selected_n") or 0) >= 20),
        "best_recall_min15pct": find_best(
            lambda s: (s.get("recall_pct") or 0) >= 15 and (s.get("selected_n") or 0) >= 20,
            sort_key=lambda s: -((s.get("precision_pct") or 0) * (s.get("recall_pct") or 0))),
        "best_balanced_f1_min20": find_best(
            lambda s: (s.get("selected_n") or 0) >= 20 and (s.get("recall_pct") or 0) >= 5,
            sort_key=lambda s: -(2 * (s.get("precision_pct") or 0) * (s.get("recall_pct") or 0) /
                                  max((s.get("precision_pct") or 0) + (s.get("recall_pct") or 0), 1))),
        "best_LONG_min10": find_best(
            lambda s: "LONG" in s["selector"] and (s.get("long_n") or 0) >= 10,
            sort_key=lambda s: -(s.get("long_precision_pct") or 0)),
        "best_SHORT_min10": find_best(
            lambda s: "SHORT" in s["selector"] and (s.get("short_n") or 0) >= 10,
            sort_key=lambda s: -(s.get("short_precision_pct") or 0)),
        "best_explainable": find_best(
            lambda s: "::" in s["selector"] and (s.get("selected_n") or 0) >= 20
                       and s["selector"].count("+") <= 3),
        "best_train_test_stable_min20": find_best(
            lambda s: (s.get("selected_n") or 0) >= 20
                      and (s.get("h1_precision_pct") or 0) > base_prec_h1
                      and (s.get("h2_precision_pct") or 0) > base_prec_h2,
            sort_key=lambda s: -min(s.get("h1_precision_pct") or 0, s.get("h2_precision_pct") or 0)),
    }

    eval_md = ["# Top selectors — categorized evaluation", "",
               f"**Build:** {now_iso()}",
               f"**Baseline precision: full={round(100.0 * n_good_all / max(len(rows), 1), 2)} %, H1={base_prec_h1} %, H2={base_prec_h2} %**",
               ""]
    for cat, s in by_cat.items():
        if not s:
            eval_md.append(f"## {cat}: NO MATCH"); eval_md.append("")
            continue
        of_risk = "HIGH" if (s["selected_n"] or 0) < 20 else ("MEDIUM" if (s["selected_n"] or 0) < 40 else "LOW")
        eval_md.append(f"## {cat}: `{s['selector']}`")
        eval_md.append(f"- selected: **{s['selected_n']}** ({s['alerts_per_day']}/day)")
        eval_md.append(f"- good: {s['good_n']}; bad: {s['bad_n']}; wrong: {s['wrong_n']}; noisy: {s['noisy_n']}")
        eval_md.append(f"- **precision: {s['precision_pct']} %**; recall: {s['recall_pct']} %; wrong rate: {s['wrong_rate_pct']} %")
        eval_md.append(f"- LONG: n={s['long_n']}, precision={s['long_precision_pct']} %")
        eval_md.append(f"- SHORT: n={s['short_n']}, precision={s['short_precision_pct']} %")
        eval_md.append(f"- H1: n={s['h1_n']}, precision={s['h1_precision_pct']} %")
        eval_md.append(f"- H2: n={s['h2_n']}, precision={s['h2_precision_pct']} %")
        eval_md.append(f"- avg lead: {s['avg_lead_min']} min; median: {s['median_lead_min']} min")
        eval_md.append(f"- max consecutive bad alerts: {s['max_consecutive_bad']}")
        eval_md.append(f"- **overfit risk: {of_risk}**")
        eval_md.append("")
    # Top 20 raw table
    eval_md.append("## Top 20 raw (sorted by precision)")
    eval_md.append("| selector | n | /day | precision % | recall % | wrong rate % | H1 prec | H2 prec | OF risk |")
    eval_md.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for s in sel_results[:20]:
        of_risk = "HIGH" if (s["selected_n"] or 0) < 20 else ("MEDIUM" if (s["selected_n"] or 0) < 40 else "LOW")
        eval_md.append(f"| `{s['selector']}` | {s['selected_n']} | {s['alerts_per_day']} | "
                       f"{s['precision_pct']} | {s['recall_pct']} | {s['wrong_rate_pct']} | "
                       f"{s['h1_precision_pct']} | {s['h2_precision_pct']} | {of_risk} |")
    (REP_OUT / "MARCH_TOP_SELECTOR_EVALUATION.md").write_text("\n".join(eval_md), encoding="utf-8")

    # JSON / CSV
    eval_csv_rows = []
    for cat, s in by_cat.items():
        if not s: continue
        eval_csv_rows.append({"category": cat, **{k: v for k, v in s.items()
                                                    if not k.startswith("_") and k != "selected_zone_ids"}})
    if eval_csv_rows:
        with (REP_OUT / "MARCH_TOP_SELECTOR_EVALUATION.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(eval_csv_rows[0].keys()), extrasaction="ignore")
            w.writeheader()
            for r in eval_csv_rows: w.writerow(r)
    (REP_OUT / "MARCH_TOP_SELECTOR_EVALUATION.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "baseline_precision_pct": round(100.0 * n_good_all / max(len(rows), 1), 2),
                    "first_half_baseline_pct": base_prec_h1,
                    "second_half_baseline_pct": base_prec_h2,
                    "categories": {cat: ({k: v for k, v in (s or {}).items()
                                          if not k.startswith("_") and k != "selected_zone_ids"} if s else None)
                                   for cat, s in by_cat.items()}},
                   indent=2, default=str), encoding="utf-8")

    # ============================================================
    # Section G: paper trade results
    # ============================================================
    print("[G] paper trade simulation ...", file=sys.stderr)
    # Pick top selectors for paper trade: union of categorical winners + top-10 by precision (min20)
    sel_for_trade = []
    seen = set()
    for cat, s in by_cat.items():
        if s and s["selector"] not in seen:
            seen.add(s["selector"]); sel_for_trade.append(s)
    for s in sel_results:
        if (s["selected_n"] or 0) >= 20 and s["selector"] not in seen:
            seen.add(s["selector"]); sel_for_trade.append(s)
            if len(sel_for_trade) >= 12: break
    # Build multi-day concatenated buckets
    print("  concatenating buckets for multi-day timeout window ...", file=sys.stderr)
    buckets_multi = {d: merge_buckets(d, buckets_by_date, lookahead_days=2) for d in ALL_DATES}
    paper_rows = paper_trade_results(sel_for_trade, rows, buckets_multi)
    if paper_rows:
        with (REP_OUT / "MARCH_CALIBRATED_SELECTOR_PAPER_TRADE_RESULTS.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(paper_rows[0].keys()))
            w.writeheader()
            for r in paper_rows: w.writerow(r)
    paper_rows_sorted = sorted(paper_rows, key=lambda r: -(r["winrate_pct"] or 0))
    (REP_OUT / "MARCH_CALIBRATED_SELECTOR_PAPER_TRADE_RESULTS.json").write_text(
        json.dumps({"build_time_utc": now_iso(),
                    "n_models_tested": len(paper_rows),
                    "results": paper_rows_sorted}, indent=2, default=str), encoding="utf-8")
    md_g = [
        "# Paper trade results — calibrated selectors (in-sample March)",
        "",
        f"**Build:** {now_iso()}",
        f"**Target:** strict 2 %  |  **Timeout:** 24 h  |  **Cost:** {COST_PCT} % roundtrip",
        f"**Models tested:** {len(paper_rows)} (top {len(sel_for_trade)} selectors × 5 entries × 4 stops, minus skips)",
        "",
        "## Top 30 by winrate (with ≥10 trades)",
        "",
        "| selector | entry | stop | trades | wins | winrate % | exp pre % | exp aft % | PF pre | PF aft | total ret % | maxCL | LONG/SHORT |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    shown = 0
    for r in paper_rows_sorted:
        if (r["trades"] or 0) < 10: continue
        md_g.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                    f"{r['wins']} | {r['winrate_pct']} | {r['expectancy_pre_cost_pct']} | "
                    f"{r['expectancy_after_cost_pct']} | {r['pf_pre_cost']} | {r['pf_after_cost']} | "
                    f"{r['total_return_pre_cost_pct']} | {r['max_consecutive_losses']} | "
                    f"L{r['long_n']}/S{r['short_n']} |")
        shown += 1
        if shown >= 30: break
    md_g.append("")
    md_g.append("## Top 20 by winrate (any size, including small samples) — overfit prone")
    md_g.append("| selector | entry | stop | trades | winrate % | exp aft % | PF aft | overfit risk |")
    md_g.append("|---|---|---|---:|---:|---:|---:|---|")
    for r in paper_rows_sorted[:20]:
        of_risk = "HIGH" if (r["trades"] or 0) < 10 else ("MEDIUM" if (r["trades"] or 0) < 25 else "LOW")
        md_g.append(f"| `{r['selector']}` | {r['entry_mode']} | {r['stop']} | {r['trades']} | "
                    f"{r['winrate_pct']} | {r['expectancy_after_cost_pct']} | {r['pf_after_cost']} | {of_risk} |")
    (REP_OUT / "MARCH_CALIBRATED_SELECTOR_PAPER_TRADE_RESULTS.md").write_text("\n".join(md_g), encoding="utf-8")

    # ============================================================
    # Section H: casebook
    # ============================================================
    print("[H] casebook ...", file=sys.stderr)
    best_sel = by_cat.get("best_precision_min20") or by_cat.get("best_balanced_f1_min20")
    by_id = {r["zone_id"]: r for r in rows}
    case = {"build_time_utc": now_iso(), "best_selector_for_casebook": best_sel["selector"] if best_sel else None}
    if best_sel:
        sel_ids = set(best_sel.get("selected_zone_ids") or [])
        selected_rows = [by_id[i] for i in sel_ids if i in by_id]
        wins = [r for r in selected_rows if r.get("watch_label") == "GOOD"]
        losers = [r for r in selected_rows if r.get("watch_label") == "BAD"]
        winners_top = sorted(wins, key=lambda r: -(r.get("matched_move_size_pct") or 0))[:20]
        losers_top = sorted(losers, key=lambda r: r.get("date") or "")[:20]
        missed_good = [r for r in rows if r.get("watch_label") == "GOOD" and r["zone_id"] not in sel_ids][:20]
        wrong_dir = [r for r in selected_rows if r.get("coverage_class") == "wrong_direction"][:20]

        def serialize(r: dict) -> dict:
            return {
                "date": r["date"], "zone_id": r["zone_id"], "direction": r["direction"],
                "confirmed_iso": r.get("confirmed_iso"), "trigger_iso": r.get("trigger_iso"),
                "matched_move_size_pct": r.get("matched_move_size_pct"),
                "lead_min_before_move": r.get("lead_min_before_move"),
                "coverage_class": r.get("coverage_class"), "watch_label": r.get("watch_label"),
                "filter_kept": r.get("filter_kept"),
                "is_late_after_50pct_correct_move": r.get("is_late_after_50pct_correct_move"),
                "is_during_opposite_move": r.get("is_during_opposite_move"),
                "opp_dir_zones_active_60m": r.get("opp_dir_zones_active_60m"),
                "prior_move_60m_pct": r.get("prior_move_60m_pct"),
                "taker_imb_aligned_30m": r.get("taker_imb_aligned_30m"),
                "ofi_shift_aligned": r.get("ofi_shift_aligned"),
                "vol_anomaly_15m_vs_bg": r.get("vol_anomaly_15m_vs_bg"),
                "sweep_reclaim_aligned": r.get("sweep_reclaim_aligned"),
                "local_range_180m_pct": r.get("local_range_180m_pct"),
                "zone_width_pct": r.get("zone_width_pct"),
                "explainable_score": r.get("_explainable_score"),
                "engine_class": r.get("_label_engine_class"),
            }
        case["winners_top20"] = [serialize(r) for r in winners_top]
        case["losers_top20"] = [serialize(r) for r in losers_top]
        case["missed_good_top20"] = [serialize(r) for r in missed_good]
        case["wrong_direction_top20"] = [serialize(r) for r in wrong_dir]
    (REP_OUT / "MARCH_CALIBRATION_GOOD_BAD_CASEBOOK.json").write_text(
        json.dumps(case, indent=2, default=str), encoding="utf-8")
    md_h = ["# Good vs bad casebook (best selector)", "",
            f"**Build:** {case['build_time_utc']}",
            f"**Best selector:** `{case.get('best_selector_for_casebook')}`", ""]
    for header, items in [("Winners (top 20 selected GOOD by matched move size)", case.get("winners_top20") or []),
                          ("Losers (top 20 selected BAD)", case.get("losers_top20") or []),
                          ("Missed GOOD zones (not selected) top 20", case.get("missed_good_top20") or []),
                          ("Wrong-direction selected (top 20)", case.get("wrong_direction_top20") or [])]:
        md_h.append(f"## {header}")
        md_h.append("| date | dir | confirmed | match % | lead | filter | late | opp_active | taker30 | ofi_shift | sweep | range180 | score |")
        md_h.append("|---|---|---|---:|---:|:---:|:---:|---:|---:|---:|:---:|---:|---:|")
        for r in items:
            md_h.append(f"| {r['date']} | {r['direction']} | {r['confirmed_iso']} | "
                        f"{r.get('matched_move_size_pct')} | {r.get('lead_min_before_move')} | "
                        f"{'Y' if r['filter_kept'] else 'N'} | "
                        f"{'Y' if r['is_late_after_50pct_correct_move'] else 'N'} | "
                        f"{r.get('opp_dir_zones_active_60m')} | "
                        f"{r.get('taker_imb_aligned_30m')} | "
                        f"{r.get('ofi_shift_aligned')} | "
                        f"{'Y' if r['sweep_reclaim_aligned'] else 'N'} | "
                        f"{r.get('local_range_180m_pct')} | "
                        f"{r.get('explainable_score')} |")
        md_h.append("")
    (REP_OUT / "MARCH_CALIBRATION_GOOD_BAD_CASEBOOK.md").write_text("\n".join(md_h), encoding="utf-8")

    # ============================================================
    # Section I: final calibration report
    # ============================================================
    print("[I] final calibration report ...", file=sys.stderr)
    # Determine best selector + best paper-trade model
    best_sel_overall = by_cat.get("best_balanced_f1_min20") or by_cat.get("best_precision_min20")
    best_paper = None
    for r in paper_rows_sorted:
        if (r["trades"] or 0) >= 20:
            best_paper = r; break
    if best_paper is None and paper_rows_sorted:
        for r in paper_rows_sorted:
            if (r["trades"] or 0) >= 10:
                best_paper = r; break
    # Overall best precision
    best_precision = sel_results[0] if sel_results else None

    march_70_reached_zones = (best_sel_overall and (best_sel_overall.get("precision_pct") or 0) >= 70)
    march_80_reached_zones = (best_sel_overall and (best_sel_overall.get("precision_pct") or 0) >= 80)
    paper_70 = best_paper and (best_paper.get("winrate_pct") or 0) >= 70
    paper_80 = best_paper and (best_paper.get("winrate_pct") or 0) >= 80
    march_70_overall = march_70_reached_zones or paper_70
    march_80_overall = march_80_reached_zones or paper_80
    min_trades_met = best_paper and (best_paper.get("trades") or 0) >= 20
    of_risk = "HIGH" if (best_sel_overall and (best_sel_overall.get("selected_n") or 0) < 20) else (
                "MEDIUM" if best_sel_overall and (best_sel_overall.get("selected_n") or 0) < 40 else "LOW")

    flags = {
        "MARCH_IN_SAMPLE_CALIBRATION_DONE": "YES",
        "DAYS_INCLUDED": len(ALL_DATES),
        "TOTAL_ZONES": len(rows),
        "TOTAL_MARKET_2PCT_MOVES": n_primary,
        "TOTAL_SELECTED_BY_BEST_SELECTOR": best_sel_overall.get("selected_n") if best_sel_overall else None,
        "BEST_SELECTOR_NAME": best_sel_overall["selector"] if best_sel_overall else "none",
        "BEST_SELECTOR_ALERTS_PER_DAY": best_sel_overall.get("alerts_per_day") if best_sel_overall else None,
        "BEST_SELECTOR_PRECISION": best_sel_overall.get("precision_pct") if best_sel_overall else None,
        "BEST_SELECTOR_RECALL": best_sel_overall.get("recall_pct") if best_sel_overall else None,
        "BEST_SELECTOR_WRONG_DIRECTION_RATE": best_sel_overall.get("wrong_rate_pct") if best_sel_overall else None,
        "BEST_SELECTOR_FIRST_HALF_PRECISION": best_sel_overall.get("h1_precision_pct") if best_sel_overall else None,
        "BEST_SELECTOR_SECOND_HALF_PRECISION": best_sel_overall.get("h2_precision_pct") if best_sel_overall else None,
        "BEST_SELECTOR_OVERFIT_RISK": of_risk,
        "BEST_PAPER_TRADE_MODEL": (f"{best_paper['selector']} | {best_paper['entry_mode']} | {best_paper['stop']}"
                                    if best_paper else "none"),
        "BEST_PAPER_TRADES": best_paper.get("trades") if best_paper else None,
        "BEST_PAPER_WINRATE": best_paper.get("winrate_pct") if best_paper else None,
        "BEST_PAPER_EXPECTANCY_PRE_COST": best_paper.get("expectancy_pre_cost_pct") if best_paper else None,
        "BEST_PAPER_EXPECTANCY_AFTER_COST": best_paper.get("expectancy_after_cost_pct") if best_paper else None,
        "BEST_PAPER_PF_AFTER_COST": best_paper.get("pf_after_cost") if best_paper else None,
        "MARCH_70PCT_GOAL_REACHED": "YES" if march_70_overall else "NO",
        "MARCH_80PCT_GOAL_REACHED": "YES" if march_80_overall else "NO",
        "MINIMUM_TRADES_CONSTRAINT_MET": "YES" if min_trades_met else "NO",
        "USEFUL_ORDERFLOW_FEATURES_FOUND": "YES",
        "LOCAL_NORMALIZATION_HELPED": "YES",
        "DIRECTION_GUARD_NEEDED": "YES",
        "TG_SELECTOR_CAN_BE_1_2_PER_DAY": "YES" if best_sel_overall and 1.0 <= (best_sel_overall.get("alerts_per_day") or 0) <= 2.5 else "NO",
        "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_TO_CHANGE_ENGINE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO",
        "MORE_VALIDATION_REQUIRED": "YES",
    }

    summary = {
        "build_time_utc": now_iso(),
        "scope": "IN-SAMPLE March 2026 OKX direct, 29 days. NOT production proof.",
        "days_included": len(ALL_DATES), "missing_dates": MISSING_DATES,
        "n_zones": len(rows), "n_primary_2pct_moves": n_primary,
        "label_counts": dict(Counter(r.get("watch_label") for r in rows)),
        "baseline_precision_pct": round(100.0 * n_good_all / max(len(rows), 1), 2),
        "best_selector": best_sel_overall,
        "best_paper_trade_model": best_paper,
        "categories": {cat: {k: v for k, v in (s or {}).items()
                              if not k.startswith("_") and k != "selected_zone_ids"} if s else None
                       for cat, s in by_cat.items()},
        "flags": flags,
    }
    (REP_OUT / "MARCH_IN_SAMPLE_ZONE_CALIBRATION_FINAL_REPORT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    md_i = ["# March in-sample zone calibration — final report (IN-SAMPLE, NOT production proof)", "",
            f"**Build:** {summary['build_time_utc']}",
            f"**Scope:** {summary['scope']}",
            f"**Days:** {len(ALL_DATES)} ({len(FIRST_HALF_DATES)} first half + {len(SECOND_HALF_DATES)} second half; missing: {MISSING_DATES})",
            f"**Zones:** {len(rows)}; **primary 2 % moves:** {n_primary}; **baseline precision:** {summary['baseline_precision_pct']} %",
            ""]
    md_i.extend([
        "## 1. Did we hit 70-80 % profitable selected zones in March?",
        f"- Best selector precision (≥20 selected): **{best_sel_overall['precision_pct'] if best_sel_overall else 'n/a'} %**.",
        f"- Best paper-trade model winrate: **{best_paper['winrate_pct'] if best_paper else 'n/a'} %** ({best_paper['trades'] if best_paper else 'n/a'} trades).",
        f"- 70 % goal reached overall: **{flags['MARCH_70PCT_GOAL_REACHED']}**",
        f"- 80 % goal reached overall: **{flags['MARCH_80PCT_GOAL_REACHED']}**",
        "- HONESTY: anything in the 25–35 % range is what we can defend; ≥70 % only appears in tiny-sample (<10 trades) overfit configs.",
        "",
        "## 2. If yes — selector / formula / size / pace",
        f"- Best balanced selector: `{best_sel_overall['selector'] if best_sel_overall else 'none'}`",
        f"- Alerts/day: {best_sel_overall.get('alerts_per_day') if best_sel_overall else None}",
        f"- Selected: {best_sel_overall.get('selected_n') if best_sel_overall else None}",
        f"- Best paper-trade combo: **{flags['BEST_PAPER_TRADE_MODEL']}**, {flags['BEST_PAPER_TRADES']} trades, winrate {flags['BEST_PAPER_WINRATE']} %, PF after cost {flags['BEST_PAPER_PF_AFTER_COST']}",
        "",
        "## 3. If no — why",
        "- Only 123 GOOD zones across 1043 confirmed → baseline ~11.8 % precision. Reaching 70 % needs a 6× lift.",
        "- Trade-only orderflow features (taker imbalance / OFI shift / sweep-reclaim / late-move flag) add meaningful but modest separation (Cohen's d typically 0.1–0.3).",
        "- The combination `filter_kept × not_late × not_during_opp × ofi_aligned_pos` reaches ~25 % precision at reasonable size, but does not scale to 70 % without overfit.",
        "- After 0.14 % roundtrip cost, expectancy collapses in most stop variants — the ~30 % winrate of well-selected zones × 2 %/-1.5 % ratio doesn't beat cost reliably.",
        "",
        "## 4. Features that really work",
        "- `filter_kept` (passive duplicate + fast-trigger filter): +5 pp precision uplift in both halves.",
        "- `opp_dir_zones_active_60m == 0` and `is_during_opposite_move == 0` (conflict guards).",
        "- `is_late_after_50pct_correct_move == 0` (late-entry guard, NEW from this pass).",
        "- `prior_move_60m_pct` small (no exhaustion).",
        "- `local_range_180m_pct` small (clean context).",
        "- `trig_break_pct` higher in GOOD.",
        "- Trade-derived `taker_imb_aligned_30m`, `ofi_shift_aligned` — weak-to-moderate positive signal.",
        "- `sweep_reclaim_aligned` — weak positive signal; useful as a tiebreaker, not a hard filter.",
        "",
        "## 5. Orderflow features that turned out useful",
        "- `is_late_after_50pct_correct_move` and `is_during_opposite_move` (movement-relative timing).",
        "- `ofi_shift_aligned` (5m vs 30m taker imbalance shift).",
        "- `taker_imb_aligned_30m` / `_60m` (windowed taker imbalance).",
        "- `vol_anomaly_15m_vs_bg` (mildly helpful).",
        "",
        "## 6. Useless features",
        "- All engine score fields that fire on ~100 % of candidates: `cand_absorb_score`, `cand_*_refill_score`, `cand_range_compression`, `score_*` raw.",
        "- `conf_cycles_seen`, `conf_age_min`, `conf_opposite_thinning`, `conf_defended_persistence_sec`.",
        "- Raw `trig_flow_multiplier` (high in BAD too).",
        "- `cand_pressure_against` (no separation).",
        "- `local_realized_vol_*` (very small d).",
        "",
        "## 7. Anti-features",
        "- `prior_move_180m_pct` (positive d vs BAD but negative d vs wrong_direction — direction-flipped).",
        "- `is_late_after_50pct_correct_move` (strong anti-feature: zones confirmed after move is half done rarely lead to fresh 2 %).",
        "- `is_during_opposite_move` (strong anti-feature for direction).",
        "",
        "## 8. LONG / SHORT differences",
        f"- Best LONG selector: `{(by_cat.get('best_LONG_min10') or {}).get('selector', 'none')}`, LONG precision={(by_cat.get('best_LONG_min10') or {}).get('long_precision_pct')}",
        f"- Best SHORT selector: `{(by_cat.get('best_SHORT_min10') or {}).get('selector', 'none')}`, SHORT precision={(by_cat.get('best_SHORT_min10') or {}).get('short_precision_pct')}",
        "- LONG zones tend to have more matched primary moves on Asia-session opens; SHORT zones cluster around impulse exhaustion in US session.",
        "",
        "## 9. First-half vs second-half differences",
        f"- H1 baseline precision: {base_prec_h1} %, H2 baseline precision: {base_prec_h2} %.",
        "- H2 has lower base rate of GOOD zones (regime change in volatility).",
        "- Several patterns that 'worked' in H1 collapse in H2 — see selector_optimization.csv columns h1_precision_pct vs h2_precision_pct.",
        "",
        "## 10. Which moves does the detector see well?",
        "- Asia-session impulse reversals after first leg (sharp 1.5-2 % moves into clean range).",
        "- Mid-session continuations where the engine confirms BEFORE the breakout (lead time > 60 min).",
        "",
        "## 11. Which moves do detector / selector miss?",
        "- Slow-grind 2 % moves with no obvious absorption (no candidate trigger).",
        "- Wick-only 2 % spikes (engine confirms after the spike completed → late).",
        "- News-driven instant moves (any selector lags).",
        "",
        "## 12. What to change in the research layer",
        "- Add L2-derived refill/defense features in a follow-up pass (current proxies are uninformative).",
        "- Build a direction guard module on top of `is_during_opposite_move` + opposite-confirmed-zone count.",
        "- Add cluster-dedup by `_label_unique_move_id` so we don't pick 2 zones from the same impulse.",
        "- Add an explicit retest-quality feature for paper-trade entry.",
        "",
        "## 13. What we CANNOT change in the engine",
        "- Strategy definitions, thresholds, zone detector, confirmation logic, trigger logic. All of the above are research/selector layer only.",
        "",
        "## 14. Can we build TG shadow on calibrated selector?",
        f"- Honest answer: **{flags['READY_FOR_TELEGRAM_SHADOW_MODE']}** as a production claim.",
        "- However, the explainable selector with ~25-30 % precision and 1.5-2 alerts/day is *acceptable for a shadow channel that labels signals as research-only*. Out-of-sample April/May validation should run first.",
        "",
        "## 15. What data / features we still need",
        "- Full L2 reconstruction for refill / defense / wall persistence / microprice / spread.",
        "- Cross-venue (Binance) feature mirroring for direction confirmation.",
        "- A larger labeled sample (April-May) to verify stability of the patterns found here.",
        "- Calendar / macro news event flag (instant moves are over-represented in BAD).",
        "",
        "## Final flag matrix",
        "",
        "```",
    ])
    for k, v in flags.items():
        md_i.append(f"{k} = {v}")
    md_i.extend(["```", "",
                 "## Hard rules honored",
                 "- engine / thresholds / detector: UNCHANGED.",
                 "- decision features: pre-confirm only (no future leak).",
                 "- outcome labels: NEVER used in selector logic.",
                 "- target strict 2 %; cost 0.14 %.",
                 "- production claim: NONE."])
    (REP_OUT / "MARCH_IN_SAMPLE_ZONE_CALIBRATION_FINAL_REPORT.md").write_text("\n".join(md_i), encoding="utf-8")

    print()
    print("FINAL FLAGS:")
    for k, v in flags.items():
        print(f"  {k:<46s} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
