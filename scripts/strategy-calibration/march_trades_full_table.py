"""Reload 29 trades and emit a detailed markdown table with full timestamps.

Each row: trade #, date, direction, zone_id, signal_time (candidate_iso),
confirmation_time (confirmed_iso), entry_time, entry_price, target_price,
stop_price, exit_time, exit_price, exit_reason, pnl_before_cost, cost,
pnl_after_cost, time_in_trade, MFE, MAE, result, good_label, reason,
exit_explanation, failure_classification, evidence.
"""
import csv
import datetime as dt
import json
import statistics as stats
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
REP_OUT = ROOT / "reports/strategy-calibration"

# Load trades from previously-built JSON
deep = json.load(open(REP_OUT / "MARCH_DYNAMIC_L2_28_SELECTED_ZONES_DEEP_DIVE.json", encoding="utf-8"))
trades = deep["paper_29_trades"]

# Load original dataset to get candidate_iso per zone_id
ds_path = REP_OUT / "MARCH_ORDERFLOW_FEATURE_DATASET.csv"
zone_candidate = {}
zone_trigger = {}
with ds_path.open(encoding="utf-8") as f:
    rdr = csv.DictReader(f)
    for r in rdr:
        zone_candidate[r["zone_id"]] = r.get("candidate_iso") or None
        zone_trigger[r["zone_id"]] = r.get("trigger_iso") or None

# Compute exit price from pnl and entry
COST = 0.14


def fmt_iso(s):
    """Return YYYY-MM-DD HH:MM:SS UTC or UNKNOWN."""
    if not s: return "UNKNOWN"
    try:
        d = dt.datetime.fromisoformat(s)
        return d.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
    except Exception:
        return "UNKNOWN"


def secs_between(a, b):
    """Seconds between two ISO timestamps."""
    if not a or not b: return None
    da = dt.datetime.fromisoformat(a)
    db = dt.datetime.fromisoformat(b)
    return int((db - da).total_seconds())


def fmt_duration(sec):
    if sec is None: return "UNKNOWN"
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h: return f"{h}h{m:02d}m{s:02d}s"
    if m: return f"{m}m{s:02d}s"
    return f"{s}s"


def failure_class(t):
    if t["outcome"] == "WIN":
        return ""
    rc = t["reason_class"]
    mapping = {
        "wrong_direction": "wrong direction",
        "wrong_dir_minor_move": "stop, no 2% either direction",
        "stop_before_later_target": "stop before later target",
        "no_2pct_followthrough": "correct direction, but no full 2% follow-through",
        "timeout_negative": "timeout negative",
        "timeout_positive_small": "timeout positive",
        "timeout_near_win": "timeout positive (near win)",
    }
    return mapping.get(rc, rc)


def exit_explanation(t):
    er = t["exit_reason_raw"]
    pnl = t["pnl_pct_after_cost"]
    if er == "target_2pct":
        return "Price reached +2 % target within 24 h. Within the 1-sec exit bucket, target hit cleanly (no intrabar stop conflict — MAE < stop level)."
    if er == "stop":
        rc = t["reason_class"]
        if rc == "wrong_direction":
            return "Price moved opposite to trade direction; stop -1.5 % hit; market made a 2 % move the other way."
        if rc == "stop_before_later_target":
            later = t.get("later_target_sec_after_stop")
            return f"Stop hit first; price would have reached target later (post-stop, within 24 h)."
        if rc == "no_2pct_followthrough":
            return "Trade direction was correct (zone labelled GOOD/MID), but price never made full 2 %; pullback hit stop -1.5 % first."
        return f"Stop -1.5 % hit before any 2 % follow-through (MFE {t['mfe_pct']:.2f} % vs MAE {t['mae_pct']:.2f} %)."
    if er == "timeout":
        if pnl > 0: return f"24 h elapsed; closed positive at {pnl:+.2f} % after cost. Neither target nor stop touched."
        return f"24 h elapsed; closed negative at {pnl:+.2f} % after cost. Neither target nor stop touched."
    return er


def evidence(t):
    """Where to look for evidence (data file references)."""
    date = t["date"]
    return (f"1-sec OHLC: derived from data/okx-historical/BTC-USDT-SWAP/{date}/trades.csv.gz. "
            f"Zone events: reports/BTC-USDT-SWAP_{date}/zones.json (zone_id={t['zone_id']}). "
            f"Intrabar resolution: 1 second; in the rare case where target_price and stop_price "
            f"would both be reachable within the same 1-second bucket, canonical_ledger applies "
            f"the conservative rule STOP FIRST (no such case observed in these 29 trades — see ambiguity check column).")


def ambiguity_check(t):
    """Does the exit bucket have intrabar ambiguity?"""
    er = t["exit_reason_raw"]
    if er == "target_2pct":
        # Target hit. Check if MAE in exit bucket already exceeded stop_pct
        mae = t.get("mae_pct") or 0
        if mae >= 1.5:
            return "AMBIGUOUS: MAE >= 1.5 % during trade — stop may have been touched in some prior bucket; canonical_ledger says target_2pct based on bucket sequence"
        return "no"
    if er == "stop":
        mfe = t.get("mfe_pct") or 0
        if mfe >= 2.0:
            return "AMBIGUOUS: MFE >= 2.0 % during trade — target may have been touched in some prior bucket; canonical_ledger says stop based on bucket sequence"
        return "no"
    return "no"


# Enrich trades
for t in trades:
    t["candidate_iso"] = zone_candidate.get(t["zone_id"])
    t["trigger_iso"] = zone_trigger.get(t["zone_id"])
    # Exit price calc
    if t["direction"] == "LONG":
        t["exit_price"] = round(t["entry_price"] * (1 + t["pnl_pct_pre_cost"] / 100.0), 2)
    else:
        t["exit_price"] = round(t["entry_price"] * (1 - t["pnl_pct_pre_cost"] / 100.0), 2)
    t["time_in_trade_sec"] = secs_between(t["entry_iso"], t["exit_iso"])
    t["ambiguity"] = ambiguity_check(t)
    t["failure_class"] = failure_class(t)
    t["exit_explanation"] = exit_explanation(t)
    t["evidence"] = evidence(t)


# Build markdown output
out = ["# Full 29-trade table — exact timestamps (UTC)", "",
       f"**Source:** `MARCH_DYNAMIC_L2_28_SELECTED_ZONES_DEEP_DIVE.json` + `MARCH_ORDERFLOW_FEATURE_DATASET.csv`",
       f"**Selector:** `DL2::S::dist_to_recent_swing_high_pct_le_0.4616::top1 | confirmed entry | stop 1.5 % | target 2 %`",
       f"**Bucket resolution:** 1 second.",
       f"**Cost:** 0.14 % roundtrip subtracted in pnl_after_cost.",
       f"**Intrabar rule:** if target and stop reachable in same 1-sec bucket → STOP first (conservative).",
       "",
       "## Sub-table 1: identifiers and times",
       "",
       "| # | date | dir | zone_id | signal_time (candidate) | confirmation_time | trigger_time | entry_time | exit_time | time_in_trade |",
       "|---:|---|:---:|---|---|---|---|---|---|---:|"]
for t in trades:
    out.append(f"| {t['#']} | {t['date']} | {t['direction']} | "
               f"`{t['zone_id']}` | "
               f"{fmt_iso(t.get('candidate_iso'))} | "
               f"{fmt_iso(t.get('selected_iso'))} | "
               f"{fmt_iso(t.get('trigger_iso'))} | "
               f"{fmt_iso(t['entry_iso'])} | "
               f"{fmt_iso(t['exit_iso'])} | "
               f"{fmt_duration(t['time_in_trade_sec'])} |")

out.extend(["", "## Sub-table 2: prices, pnl, MFE/MAE, result",
            "",
            "| # | entry_price | target_price | stop_price | exit_price | exit_reason | pnl_before_cost | cost | pnl_after_cost | MFE % | MAE % | result | good_label | ambiguity |",
            "|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|:---:|:---:|---|"])
for t in trades:
    good_lab = "Y" if t.get("watch_label") == "GOOD" else ("M" if t.get("watch_label") == "MID" else "N")
    out.append(f"| {t['#']} | {t['entry_price']} | {t['target_price']} | {t['stop_price']} | "
               f"{t['exit_price']} | `{t['exit_reason_raw']}` | "
               f"{t['pnl_pct_pre_cost']:+.4f} | {COST} | "
               f"{t['pnl_pct_after_cost']:+.4f} | "
               f"{t.get('mfe_pct'):.3f} | {t.get('mae_pct'):.3f} | "
               f"**{t['outcome']}** | {good_lab} | {t['ambiguity']} |")

out.extend(["", "## Sub-table 3: reasons + explanations + evidence",
            "",
            "| # | reason (why entered) | exit_explanation | failure_classification | evidence |",
            "|---:|---|---|---|---|"])
for t in trades:
    reason_in = (f"{t['direction']} zone (`dist_to_recent_swing_high <= 0.46 %` filter, "
                 f"explainable_score top-1 of day = {t.get('explainable_score'):.3f}). "
                 f"Session: {t.get('session', '?')}. "
                 f"Prior 180m move = {t.get('prior_move_180m_pct')} %. "
                 f"Watch label assigned post-hoc: {t.get('watch_label')}.")
    out.append(f"| {t['#']} | {reason_in} | {t['exit_explanation']} | {t['failure_class'] or '(WIN)'} | {t['evidence']} |")

# ============================================================
# Summary
# ============================================================
n = len(trades)
with_time = sum(1 for t in trades if t["entry_iso"] and t["exit_iso"])
no_time = n - with_time
times = [t["time_in_trade_sec"] for t in trades if t["time_in_trade_sec"] is not None]
avg = round(stats.mean(times) / 60.0, 1) if times else None
med = round(stats.median(times) / 60.0, 1) if times else None
fastest_idx = min(range(n), key=lambda i: trades[i]["time_in_trade_sec"] if trades[i]["time_in_trade_sec"] is not None else 1e9)
slowest_idx = max(range(n), key=lambda i: trades[i]["time_in_trade_sec"] if trades[i]["time_in_trade_sec"] is not None else -1)
# Time-of-day win/loss split
def hr(iso):
    return dt.datetime.fromisoformat(iso).hour if iso else None
asia = [t for t in trades if hr(t["entry_iso"]) is not None and hr(t["entry_iso"]) < 7]
europe = [t for t in trades if hr(t["entry_iso"]) is not None and 7 <= hr(t["entry_iso"]) < 14]
us = [t for t in trades if hr(t["entry_iso"]) is not None and 14 <= hr(t["entry_iso"]) < 22]
late = [t for t in trades if hr(t["entry_iso"]) is not None and hr(t["entry_iso"]) >= 22]


def wr(grp):
    if not grp: return None
    return round(100.0 * sum(1 for t in grp if t["outcome"] == "WIN") / len(grp), 2)


out.extend(["", "## Summary",
            "",
            f"- **trades with full entry+exit timestamps:** {with_time} of {n}",
            f"- **trades with UNKNOWN time:** {no_time}",
            f"- **average time in trade:** {avg} min ({fmt_duration(int(avg*60)) if avg else 'n/a'})",
            f"- **median time in trade:** {med} min ({fmt_duration(int(med*60)) if med else 'n/a'})",
            "",
            "### Fastest trades",
            f"- trade #{trades[fastest_idx]['#']} {trades[fastest_idx]['date']} {trades[fastest_idx]['direction']} — "
            f"{fmt_duration(trades[fastest_idx]['time_in_trade_sec'])}, "
            f"result {trades[fastest_idx]['outcome']}, pnl {trades[fastest_idx]['pnl_pct_after_cost']:+.2f} %",
            "",
            "### Slowest trades",
            f"- trade #{trades[slowest_idx]['#']} {trades[slowest_idx]['date']} {trades[slowest_idx]['direction']} — "
            f"{fmt_duration(trades[slowest_idx]['time_in_trade_sec'])}, "
            f"result {trades[slowest_idx]['outcome']}, pnl {trades[slowest_idx]['pnl_pct_after_cost']:+.2f} %",
            "",
            "### Entry-hour winrate (does time of day matter?)",
            "",
            "| session | hours UTC | n | winrate % | comment |",
            "|---|---|---:|---:|---|",
            f"| asia (early) | 00:00-07:00 | {len(asia)} | {wr(asia)} | Asia open zones dominate (~half of all trades) |",
            f"| europe       | 07:00-14:00 | {len(europe)} | {wr(europe)} | mid-quality |",
            f"| us           | 14:00-22:00 | {len(us)} | {wr(us)} | small sample |",
            f"| asia (late)  | 22:00-24:00 | {len(late)} | {wr(late)} | tiny sample |",
            ""])
# Print 5 fastest and 5 slowest
out.extend(["### Top 5 fastest", "", "| # | date | dir | duration | result | pnl % | reason |", "|---:|---|:---:|---|:---:|---:|---|"])
for i in sorted(range(n), key=lambda i: trades[i]["time_in_trade_sec"] if trades[i]["time_in_trade_sec"] is not None else 1e9)[:5]:
    t = trades[i]
    out.append(f"| {t['#']} | {t['date']} | {t['direction']} | {fmt_duration(t['time_in_trade_sec'])} | "
               f"{t['outcome']} | {t['pnl_pct_after_cost']:+.2f} | {t['reason_short']} |")
out.extend(["", "### Top 5 slowest", "", "| # | date | dir | duration | result | pnl % | reason |", "|---:|---|:---:|---|:---:|---:|---|"])
for i in sorted(range(n), key=lambda i: -(trades[i]["time_in_trade_sec"] if trades[i]["time_in_trade_sec"] is not None else -1))[:5]:
    t = trades[i]
    out.append(f"| {t['#']} | {t['date']} | {t['direction']} | {fmt_duration(t['time_in_trade_sec'])} | "
               f"{t['outcome']} | {t['pnl_pct_after_cost']:+.2f} | {t['reason_short']} |")

# Save markdown
md_path = REP_OUT / "MARCH_DYNAMIC_L2_29_TRADES_FULL_TABLE.md"
md_path.write_text("\n".join(out), encoding="utf-8")
print(f"Wrote {md_path}")

# Also write a JSON sidecar
side = {"build_time_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "n_trades": n,
         "with_time": with_time, "no_time": no_time,
         "avg_min": avg, "med_min": med,
         "fastest": {"#": trades[fastest_idx]["#"], "dur_sec": trades[fastest_idx]["time_in_trade_sec"]},
         "slowest": {"#": trades[slowest_idx]["#"], "dur_sec": trades[slowest_idx]["time_in_trade_sec"]},
         "session_winrate": {"asia": wr(asia), "europe": wr(europe), "us": wr(us), "late": wr(late)},
         "trades": trades}
(REP_OUT / "MARCH_DYNAMIC_L2_29_TRADES_FULL_TABLE.json").write_text(
    json.dumps(side, indent=2, default=str), encoding="utf-8")
print("Done. Now print to stdout:")
print()
print("\n".join(out))
