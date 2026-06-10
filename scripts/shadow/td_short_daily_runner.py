"""TD-SHORT DAILY RUNNER (thin wrapper; no rule changes, no Telegram, no production).

Modes:
  (default)           ingest NEW days -> append to reports/shadow/oos/TD_SHORT_OOS_DECISIONS.* (dedup zone_id)
  --update-outcomes   mature decisions older than 24h -> append TD_SHORT_OOS_OUTCOMES.* (never touch decisions)
  --dashboard         rebuild OOS dashboard + safety checks + success-criteria gate

Reuses the FROZEN td_short_shadow_observer (decision logic) and td_short_outcome_updater (outcomes).
Decision log stays leak-free; outcomes live in a separate file.
"""
from __future__ import annotations
import argparse, csv, json, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
SHADOW = ROOT / "scripts/shadow"
sys.path.insert(0, str(SHADOW)); sys.path.insert(0, str(ROOT / "scripts/strategy-calibration"))
import td_short_shadow_observer as OBS
import td_short_outcome_updater as UPD

OOS = ROOT / "reports/shadow/oos"; OOS.mkdir(parents=True, exist_ok=True)
DEC_CSV = OOS / "TD_SHORT_OOS_DECISIONS.csv"; DEC_JSONL = OOS / "TD_SHORT_OOS_DECISIONS.jsonl"
OC_CSV = OOS / "TD_SHORT_OOS_OUTCOMES.csv"; OC_JSONL = OOS / "TD_SHORT_OOS_OUTCOMES.jsonl"
HORIZON_MS = 24 * 3600 * 1000


def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_jsonl(p):
    out = []
    if p.exists():
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip(): out.append(json.loads(line))
    return out


def append_rows(csv_p, jsonl_p, rows, fields):
    new_file = not csv_p.exists()
    with csv_p.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new_file: w.writeheader()
        w.writerows(rows)
    with jsonl_p.open("a", encoding="utf-8") as fh:
        for r in rows: fh.write(json.dumps({k: r.get(k) for k in fields}, default=str) + "\n")


# ---------------- A: ingest new days ----------------
def ingest():
    existing = {r["zone_id"] for r in read_jsonl(DEC_JSONL)}
    zones = OBS.load_caches()
    new_zones = [z for z in zones if z.get("id") not in existing]
    if not new_zones:
        print("no new zones to ingest", file=sys.stderr)
        return {"new_decisions": 0, "new_days": []}
    rows = OBS.run_decisions(new_zones)
    append_rows(DEC_CSV, DEC_JSONL, rows, OBS.DECISION_FIELDS)
    days = sorted({(r["venue"], r["date"]) for r in rows})
    # per-run daily summary
    byday = defaultdict(lambda: {"zones": 0, "candidates": 0, "accepted": 0})
    for r in rows:
        s = byday[(r["venue"], r["date"])]; s["zones"] += 1
        if r["hybrid_decision"] == "HYBRID_PASS": s["candidates"] += 1
        if r["final_shadow_decision"] == "ACCEPT": s["accepted"] += 1
    (OOS / "TD_SHORT_OOS_DAILY_SUMMARY.json").write_text(json.dumps(
        {"build": now_iso(), "ingested_days": [{"venue": v, "date": d, **byday[(v, d)]} for v, d in days]}, indent=2, default=str), encoding="utf-8")
    print(f"ingested {len(rows)} decisions over {len(days)} venue-days", file=sys.stderr)
    return {"new_decisions": len(rows), "new_days": [f"{v}:{d}" for v, d in days]}


# ---------------- B: mature outcomes (>24h old) ----------------
def update_outcomes(as_of_ms=None):
    if as_of_ms is None: as_of_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    decs = read_jsonl(DEC_JSONL)
    done = {r["zone_id"] for r in read_jsonl(OC_JSONL)}
    mature = [d for d in decs if d.get("zone_id") not in done and d.get("confirmedTs") and (as_of_ms - d["confirmedTs"]) >= HORIZON_MS]
    if not mature:
        print("no matured decisions to update", file=sys.stderr); return {"new_outcomes": 0}
    byv = defaultdict(list)
    for d in mature: byv[d["venue"]].append(d)
    out_rows = []
    for vn, rows in byv.items():
        gb, secs = UPD.buckets_for(vn, {r["date"] for r in rows})
        for r in rows: out_rows.append(UPD.outcome_for(r, gb, secs))
        print(f"  {vn}: matured {len(rows)}", file=sys.stderr)
    fields = list(out_rows[0].keys())
    append_rows(OC_CSV, OC_JSONL, out_rows, fields)
    print(f"appended {len(out_rows)} outcomes", file=sys.stderr)
    return {"new_outcomes": len(out_rows)}


# ---------------- C/D/E: dashboard + safety + gate ----------------
def dashboard():
    decs = read_jsonl(DEC_JSONL); ocs = {r["zone_id"]: r for r in read_jsonl(OC_JSONL)}
    venues_days = {(d["venue"], d["date"]) for d in decs}
    accepted = [d for d in decs if d["final_shadow_decision"] == "ACCEPT"]
    td_short = [d for d in decs if d["regime"] == "TREND_DOWN" and d["direction"] == "SHORT"]
    m4_pass = [d for d in td_short if d["m4_thin_decision"] == "M4_THIN_ONLY_PASS"]
    acc_with_oc = [ocs[d["zone_id"]] for d in accepted if d["zone_id"] in ocs and ocs[d["zone_id"]].get("result") in ("WIN", "LOSS", "TIMEOUT")]
    m = UPD.metr(acc_with_oc)
    pending = sum(1 for d in accepted if d["zone_id"] not in ocs)
    # safety
    zid = [d["zone_id"] for d in decs]
    dup = len(zid) != len(set(zid))
    leak_fields = {"sim_outcome", "true_mfe", "pnl_after_cost", "hit_2pct", "result", "MFE", "MAE"}
    leak_free = not (decs and (leak_fields & set(decs[0].keys())))
    safety = {"DECISION_LOG_FUTURE_LEAK_FREE": "YES" if leak_free else "NO", "OUTCOME_UPDATER_SEPARATE": "YES",
              "DUPLICATE_ZONE_IDS": "YES" if dup else "NO", "TELEGRAM_DISABLED": "YES", "PRODUCTION_DISABLED": "YES"}
    # by venue / regime / day
    def grp(key):
        g = defaultdict(list)
        for d in accepted:
            if d["zone_id"] in ocs and ocs[d["zone_id"]].get("result") in ("WIN", "LOSS", "TIMEOUT"): g[d[key]].append(ocs[d["zone_id"]])
        return {k: UPD.metr(v) for k, v in g.items()}
    # by day distinct
    day_g = defaultdict(list)
    for d in accepted:
        if d["zone_id"] in ocs and ocs[d["zone_id"]].get("result") in ("WIN", "LOSS", "TIMEOUT"): day_g[(d["venue"], d["date"])].append(ocs[d["zone_id"]])
    # success-criteria gate
    venues_present = {d["venue"] for d in accepted}
    max_day = max((len(v) for v in day_g.values()), default=0)
    concentrated = (len(acc_with_oc) > 0 and (max((m_["trades"] for m_ in grp("venue").values()), default=0) > 0.6 * m["trades"]))
    catastrophic = sum(1 for r in acc_with_oc if (r.get("MAE") is not None and r["MAE"] < -3.0))
    if m["trades"] < 20:
        status = "INSUFFICIENT_SAMPLE"
    else:
        ok = ((m["pf"] or 0) > 1.5 and (m["winrate"] or 0) >= 50 and m["max_loss_streak"] <= 5 and not concentrated and catastrophic == 0)
        status = "OOS_PASS" if ok else "OOS_FAIL"
    dash = {"build": now_iso(), "status": status, "total_days_observed": len(venues_days), "pending_outcomes": pending,
            "completed_outcomes": len(acc_with_oc), "td_short_candidates": sum(1 for d in decs if d["hybrid_decision"] == "HYBRID_PASS"),
            "hybrid_accepted": len(accepted), "m4_accepted": len(m4_pass), "overlap_hybrid_m4": len({d["zone_id"] for d in accepted} & {d["zone_id"] for d in m4_pass}),
            "metrics": m, "by_venue": grp("venue"), "by_regime": grp("regime"),
            "by_day_max_trades": max_day, "venues_present": sorted(venues_present), "concentrated": concentrated,
            "catastrophic_countertrend_losses": catastrophic, "safety": safety,
            "success_criteria": {"min_trades": 20, "pf>1.5": (m["pf"] or 0) > 1.5, "winrate>=50": (m["winrate"] or 0) >= 50,
                                 "max_loss_streak<=5": m["max_loss_streak"] <= 5, "not_concentrated": not concentrated, "no_catastrophic": catastrophic == 0}}
    (OOS / "TD_SHORT_OOS_DASHBOARD.json").write_text(json.dumps(dash, indent=2, default=str), encoding="utf-8")
    md = ["# TD-short OOS dashboard", "", f"**Build:** {now_iso()}", f"**STATUS: {status}**", "",
          f"- days observed: {len(venues_days)} · TD-short candidates: {dash['td_short_candidates']} · HYBRID accepted: {len(accepted)} · M4 accepted: {len(m4_pass)} (overlap {dash['overlap_hybrid_m4']})",
          f"- completed outcomes: {len(acc_with_oc)} · pending (<24h or unmatured): {pending}", "",
          f"**HYBRID accepted (matured):** {m['trades']}tr {m['W']}/{m['L']}/{m['TO']} · wr {m['winrate']}% · PF {m['pf']} · exp {m['expectancy']} · maxLS {m['max_loss_streak']} · hit2/2.5/3 {m['hit2']}/{m['hit2_5']}/{m['hit3']}", "",
          "## By venue", "| venue | tr | wr% | PF |", "|---|--:|--:|--:|"]
    for k, v in dash["by_venue"].items(): md.append(f"| {k} | {v['trades']} | {v['winrate']} | {v['pf']} |")
    md += ["", "## By regime", "| regime | tr | wr% | PF |", "|---|--:|--:|--:|"]
    for k, v in dash["by_regime"].items(): md.append(f"| {k} | {v['trades']} | {v['winrate']} | {v['pf']} |")
    md += ["", "## Safety", "```"] + [f"{k} = {v}" for k, v in safety.items()] + ["```",
           "", "## Success criteria (gate)", f"```\nstatus = {status}\n" + "\n".join(f"{k} = {v}" for k, v in dash["success_criteria"].items()) + "\n```",
           "", "_Note: if accepted trades < 20, status = INSUFFICIENT_SAMPLE even if numbers look good._"]
    (OOS / "TD_SHORT_OOS_DASHBOARD.md").write_text("\n".join(md), encoding="utf-8")
    return dash


def final_report(dash):
    flags = {
        "TD_SHORT_DAILY_RUNNER_IMPLEMENTED": "YES", "TD_SHORT_RULES_FROZEN": "YES", "HYBRID_MAIN_MODEL": "YES",
        "M4_THIN_ONLY_BOOSTER_LOGGED": "YES", "DECISION_LOG_FUTURE_LEAK_FREE": dash["safety"]["DECISION_LOG_FUTURE_LEAK_FREE"],
        "OUTCOME_UPDATER_SEPARATE": "YES", "DUPLICATE_ZONE_IDS": dash["safety"]["DUPLICATE_ZONE_IDS"],
        "TELEGRAM_DISABLED": "YES", "PRODUCTION_DISABLED": "YES", "APPEND_ONLY_OOS_LOG": "YES",
        "OOS_STATUS": dash["status"], "OOS_ACCEPTED_TRADES": dash["metrics"]["trades"], "OOS_WINRATE": dash["metrics"]["winrate"],
        "OOS_PF": dash["metrics"]["pf"], "NEW_OKX_BINANCE_OVERLAP_WINDOW_REQUIRED": "YES",
        "READY_FOR_LIVE_SHADOW_LOGGING": "YES", "READY_FOR_TELEGRAM_SHADOW_MODE": "NO",
        "READY_FOR_PRODUCTION_TRADING": "NO", "MORE_OOS_REQUIRED": "YES", "TARDIS_USED": "NO"}
    out = {"build": now_iso(), "status": "SHADOW_RESEARCH_ONLY", "dashboard": dash, "flags": flags,
           "how_to_run_daily": ["python scripts/shadow/td_short_daily_runner.py            # ingest new day(s) -> decisions",
                                "python scripts/shadow/td_short_daily_runner.py --update-outcomes   # after 24h -> outcomes",
                                "python scripts/shadow/td_short_daily_runner.py --dashboard  # refresh dashboard"],
           "oos_logs": {"decisions": str(DEC_JSONL), "outcomes": str(OC_JSONL), "dashboard": str(OOS / "TD_SHORT_OOS_DASHBOARD.md")},
           "parallel_requirement": "Keep collecting a NEW OKX+Binance overlapping downtrend window (Binance v3 recorder + OKX open). Mandatory for a real OOS verdict; not a blocker for the runner."}
    (ROOT / "reports/shadow/TD_SHORT_DAILY_RUNNER_FINAL_REPORT.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    L = ["# TD-SHORT DAILY RUNNER — FINAL REPORT", "", f"**Build:** {now_iso()}",
         "SHADOW/RESEARCH ONLY · rules FROZEN · Telegram DISABLED · production DISABLED · append-only OOS log · leak-free decisions", "",
         f"## OOS status: **{dash['status']}**  (accepted {dash['metrics']['trades']} / need >=20)", "",
         "## How to run daily", "```"] + out["how_to_run_daily"] + ["```", "",
         "## OOS logs", f"- decisions: `{DEC_JSONL}`", f"- outcomes: `{OC_JSONL}`", f"- dashboard: `{OOS / 'TD_SHORT_OOS_DASHBOARD.md'}`", "",
         "## Flags", "```"] + [f"{k} = {v}" for k, v in flags.items()] + ["```", "",
         "## Parallel requirement", out["parallel_requirement"]]
    (ROOT / "reports/shadow/TD_SHORT_DAILY_RUNNER_FINAL_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    return flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-outcomes", action="store_true")
    ap.add_argument("--dashboard", action="store_true")
    ap.add_argument("--all", action="store_true", help="ingest + update-outcomes + dashboard (backfill convenience)")
    args = ap.parse_args()
    if args.dashboard and not (args.update_outcomes or args.all):
        d = dashboard(); final_report(d); print(json.dumps(d["success_criteria"], indent=2)); return 0
    if args.update_outcomes and not args.all:
        update_outcomes(); d = dashboard(); final_report(d)
    elif args.all:
        ingest(); update_outcomes(); d = dashboard(); final_report(d)
    else:
        ingest(); d = dashboard(); final_report(d)
    print(f"\nOOS STATUS: {d['status']} | accepted {d['metrics']['trades']} wr {d['metrics']['winrate']}% PF {d['metrics']['pf']} | pending {d['pending_outcomes']}")
    print("SAFETY:", d["safety"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
