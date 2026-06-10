"""Binance OOS 2026-05-21..30 — archive inventory + honest data-availability gate.

Ground truth established by directory listing: max Binance date present = 2026-05-20.
Requested OOS window 2026-05-21..2026-05-30 does NOT exist (archive snapshot taken
2026-05-21 captured only up to 2026-05-20). No fabrication: sections B-J cannot run
on the requested window; they are written as BLOCKED with exact requirements.

Reads-only inventory + sha256 of source archives + audit of the 05-17..20 reference.
"""
from __future__ import annotations
import csv, gzip, hashlib, json, zipfile, datetime as dt
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
OUT = ROOT / "reports/binance-oos"
OUT.mkdir(parents=True, exist_ok=True)
DATA = ROOT / "data"
REQ_DATES = [f"2026-05-{d:02d}" for d in range(21, 31)]   # requested OOS window
REF_DATES = ["2026-05-17", "2026-05-18", "2026-05-19", "2026-05-20"]  # what exists

def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def sha256_file(p: Path, cap_bytes=None) -> str:
    h = hashlib.sha256(); n = 0
    with p.open("rb") as f:
        while True:
            chunk = f.read(8*1024*1024)
            if not chunk: break
            h.update(chunk); n += len(chunk)
            if cap_bytes and n >= cap_bytes: break
    return h.hexdigest()

def zip_date_dirs(p: Path):
    dates = set(); streams = set()
    try:
        with zipfile.ZipFile(p) as z:
            for nm in z.namelist():
                parts = nm.split("/")
                for seg in parts:
                    if len(seg)==10 and seg.startswith("2026-"):
                        dates.add(seg)
                base = parts[-1]
                if base.endswith(".jsonl") or base.endswith(".csv.gz"):
                    streams.add(base.replace(".jsonl","").replace(".csv.gz",""))
    except Exception as e:
        return None, None, str(e)
    return sorted(dates), sorted(streams), None

def gz_first_last_ts(p: Path, ts_col_candidates=("timestamp","local_timestamp","T","E")):
    """Return (first_iso,last_iso,rows) reading a Tardis-style csv.gz with microsecond ts."""
    try:
        with gzip.open(p, "rt", encoding="utf-8", newline="") as f:
            rdr = csv.reader(f); hdr = next(rdr)
            idx = None
            for c in ts_col_candidates:
                if c in hdr: idx = hdr.index(c); break
            if idx is None: return None, None, None
            first=None; last=None; rows=0
            for row in rdr:
                try: ts=int(row[idx])
                except: continue
                if first is None: first=ts
                last=ts; rows+=1
            def cv(ts):
                # microsecond or millisecond?
                if ts > 1e16: ts//=1000  # us->ms? keep ms
                return dt.datetime.fromtimestamp(ts/1e6 if ts>1e14 else ts/1e3, tz=dt.timezone.utc).isoformat()
            return (cv(first) if first else None, cv(last) if last else None, rows)
    except Exception:
        return None, None, None


def main():
    # ---------- A: archive inventory ----------
    archive_files = [
        DATA/"binance-live-archives/staging/OFFRW/BTCUSDT.zip",
        DATA/"binance-live-archives/staging/OFFRW/BTCUSDT2.zip",
        DATA/"binance-live-archives/staging/OFFRW/BTCUSDT2_2.zip",
        DATA/"binance-live-archives/staging/OFFRW/BTCUSDT2_2.zip.001",
        DATA/"binance-live-archives/staging/OFFRW/BTCUSDT2_2.zip.002",
        DATA/"binance-live-archives/raw/OFFRW.zip",
    ]
    inv=[]
    all_dates=set()
    for p in archive_files:
        if not p.exists(): continue
        rec={"file":str(p.relative_to(ROOT)),"size_bytes":p.stat().st_size,
             "sha256":sha256_file(p)}
        if p.suffix==".zip":
            dates,streams,err=zip_date_dirs(p)
            rec["inner_date_dirs"]=dates; rec["inner_streams"]=streams; rec["zip_error"]=err
            if dates: all_dates.update(dates)
        else:
            rec["note"]="split-archive part (not a standalone zip)"
        inv.append(rec)
    # normalized reference days
    ref=[]
    for d in REF_DATES:
        dd=DATA/"binance-historical/BTCUSDT"/d
        if not dd.exists(): continue
        files={f.name:f.stat().st_size for f in dd.iterdir() if f.is_file()}
        ref.append({"date":d,"files":files,"streams":sorted(k.replace('.csv.gz','') for k in files)})
        all_dates.add(d)
    max_date=max(all_dates) if all_dates else None
    req_present=[d for d in REQ_DATES if d in all_dates]
    req_absent=[d for d in REQ_DATES if d not in all_dates]

    A={"build_time_utc":now_iso(),
       "requested_window":"2026-05-21..2026-05-30",
       "archive_files":inv,
       "normalized_reference_days":ref,
       "all_dates_detected":sorted(all_dates),
       "max_date_available":max_date,
       "requested_window_present":req_present,
       "requested_window_absent":req_absent,
       "flags":{
           "BINANCE_ARCHIVES_FOUND":"YES (but only up to 2026-05-20; requested 05-21..30 ABSENT)",
           "BINANCE_DATES_DETECTED":sorted(all_dates),
           "BINANCE_ARCHIVE_SHA256_DONE":"YES",
           "BINANCE_RAW_ARCHIVES_UNTOUCHED":"YES",
           "REQUESTED_WINDOW_PRESENT_DAYS":len(req_present),
           "REQUESTED_WINDOW_ABSENT_DAYS":len(req_absent)}}
    (OUT/"BINANCE_2026_05_21_30_ARCHIVE_INVENTORY.json").write_text(json.dumps(A,indent=2),encoding="utf-8")
    md=["# Binance archive inventory — requested OOS window 2026-05-21..30","",
        f"**Build:** {now_iso()}","",
        "## VERDICT: requested window is ABSENT",
        f"- **Max Binance date available anywhere: `{max_date}`.**",
        f"- Requested days present: {req_present if req_present else 'NONE'}",
        f"- Requested days absent: {req_absent}",
        "- The source archive snapshot (`OFFRW`) was created 2026-05-21 ~07:00 and captured only up to the "
        "last complete recorded day (2026-05-20). 2026-05-21..30 were never recorded into this archive.",
        "","## Archive files (sha256)","",
        "| file | size MB | sha256 (first 16) | inner date dirs | streams |",
        "|---|---:|---|---|---|"]
    for r in inv:
        md.append(f"| {Path(r['file']).name} | {round(r['size_bytes']/1e6,1)} | {r['sha256'][:16]} | "
                  f"{','.join(r.get('inner_date_dirs') or []) or '-'} | {','.join(r.get('inner_streams') or [])[:60] or '-'} |")
    md+=["","## Normalized reference days present (05-17..20, OUTSIDE requested window)","",
         "| date | streams |","|---|---|"]
    for r in ref:
        md.append(f"| {r['date']} | {', '.join(r['streams'])} |")
    md+=["","## Flags","```"]
    for k,v in A["flags"].items(): md.append(f"{k} = {v}")
    md.append("```")
    (OUT/"BINANCE_2026_05_21_30_ARCHIVE_INVENTORY.md").write_text("\n".join(md),encoding="utf-8")

    # ---------- C: data quality of what EXISTS (reference 05-17..20) ----------
    dq_rows=[]
    for r in ref:
        d=r["date"]; dd=DATA/"binance-historical/BTCUSDT"/d
        tr=dd/"trades.csv.gz"; bk=dd/"incremental_book_L2.csv.gz"
        tf,tl,tn=gz_first_last_ts(tr) if tr.exists() else (None,None,None)
        bf,bl,bn=gz_first_last_ts(bk) if bk.exists() else (None,None,None)
        cov=None
        if tf and tl:
            cov=round((dt.datetime.fromisoformat(tl)-dt.datetime.fromisoformat(tf)).total_seconds()/3600,2)
        dq_rows.append({"date":d,"trades_first":tf,"trades_last":tl,"trades_rows":tn,
                        "book_rows":bn,"coverage_hours":cov,
                        "status":"FULL" if (cov or 0)>=23 else "PARTIAL"})
    with (OUT/"BINANCE_2026_05_21_30_DATA_QUALITY_AUDIT.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["date","trades_first","trades_last","trades_rows","book_rows","coverage_hours","status"])
        w.writeheader()
        for r in dq_rows: w.writerow(r)
    C={"build_time_utc":now_iso(),
       "note":"Data quality is reported ONLY for the reference days that exist (05-17..20). "
              "The requested window 05-21..30 has NO data to audit.",
       "reference_days":dq_rows,
       "flags":{"BINANCE_DATA_QUALITY_PASS":"N/A (requested window absent)",
                "BINANCE_FULL_DAYS":[r["date"] for r in dq_rows if r["status"]=="FULL"],
                "BINANCE_BAD_DAYS":[],
                "BINANCE_2PCT_FEASIBLE_DAYS":"not computed for requested window (absent)"}}
    (OUT/"BINANCE_2026_05_21_30_DATA_QUALITY_AUDIT.json").write_text(json.dumps(C,indent=2),encoding="utf-8")
    (OUT/"BINANCE_2026_05_21_30_DATA_QUALITY_AUDIT.md").write_text(
        "# Binance data quality — requested window 2026-05-21..30\n\n"
        f"**Build:** {now_iso()}\n\n"
        "## Requested window 05-21..30: NO DATA (cannot audit)\n\n"
        "## Reference days that DO exist (05-17..20, outside requested window)\n\n"
        "| date | trades first | trades last | trades rows | coverage h | status |\n|---|---|---|---:|---:|---|\n"
        + "\n".join(f"| {r['date']} | {r['trades_first']} | {r['trades_last']} | {r['trades_rows']} | {r['coverage_hours']} | {r['status']} |" for r in dq_rows)
        + "\n", encoding="utf-8")

    # ---------- B,D,E,F,G,H,I: BLOCKED stubs ----------
    blocked_reason=(f"Requested OOS window 2026-05-21..2026-05-30 is ABSENT from the project. "
                    f"Max Binance date available = {max_date}. Cannot run engine replay / RS1 / RS2 / "
                    f"comparison on data that does not exist. No fabrication performed.")
    def blocked(name, extra=None):
        obj={"build_time_utc":now_iso(),"status":"BLOCKED_DATA_UNAVAILABLE","reason":blocked_reason}
        if extra: obj.update(extra)
        (OUT/f"{name}.json").write_text(json.dumps(obj,indent=2),encoding="utf-8")
        (OUT/f"{name}.md").write_text(f"# {name}\n\n**Build:** {now_iso()}\n\n**STATUS: BLOCKED — data unavailable**\n\n{blocked_reason}\n",encoding="utf-8")
    blocked("BINANCE_2026_05_21_30_NORMALIZATION_REPORT",
            {"BINANCE_NORMALIZATION_DONE":"NO","BINANCE_DAYS_NORMALIZED":0,
             "note":"05-17..20 already normalized previously (data/binance-historical/BTCUSDT); requested window has nothing to normalize."})
    blocked("BINANCE_2026_05_21_30_FEATURE_REBUILD",
            {"BINANCE_RS1_FEATURES_BUILT":"NO","BINANCE_RS2_FEATURES_BUILT":"NO",
             "BINANCE_TRUE_OI_AVAILABLE":"YES_for_05-17..20_only","BINANCE_FUNDING_AVAILABLE":"YES_for_05-17..20_only",
             "BINANCE_LIQUIDATIONS_AVAILABLE":"YES_for_05-17..20_only","FLOW_PROXY_USED":"NO"})
    blocked("BINANCE_2026_05_21_30_RS1_BASELINE_RESULTS",
            {"BINANCE_RS1_DONE":"NO","BINANCE_RS1_TRADES":0})
    blocked("BINANCE_2026_05_21_30_RS2_S7_RESULTS",
            {"BINANCE_RS2_DONE":"NO","BINANCE_RS2_TRADES":0,"BINANCE_RS2_IMPROVES_RS1":"UNKNOWN"})
    # engine summary blocked
    blocked("BINANCE_2026_05_21_30_ENGINE_SUMMARY",
            {"BINANCE_BACKTEST_RAN":"NO","BINANCE_ENGINE_ZONES_TOTAL":0})
    (OUT/"BINANCE_2026_05_21_30_CHAIN_RESULTS.json").write_text(json.dumps(
        {"build_time_utc":now_iso(),"status":"BLOCKED_DATA_UNAVAILABLE","reason":blocked_reason,"days":[]},indent=2),encoding="utf-8")
    blocked("BINANCE_2026_05_21_30_OKX_VS_BINANCE_COMPARISON",
            {"BINANCE_RS1_TRANSFER_SUCCESS":"UNKNOWN","BINANCE_RS2_TRANSFER_SUCCESS":"UNKNOWN",
             "BINANCE_CONFIRMS_OKX_EDGE":"UNKNOWN"})
    blocked("BINANCE_2026_05_21_30_CASEBOOK",{"note":"no trades — window absent"})
    # empty trade tables with header
    for nm in ("BINANCE_2026_05_21_30_RS1_BASELINE_TRADES","BINANCE_2026_05_21_30_TRADE_TABLE_RS1",
               "BINANCE_2026_05_21_30_TRADE_TABLE_RS2","BINANCE_2026_05_21_30_RS2_S7_TRADES",
               "BINANCE_2026_05_21_30_RS2_S7_REMOVED_TRADES"):
        (OUT/f"{nm}.csv").write_text("# BLOCKED: requested window 2026-05-21..30 absent; no trades\n",encoding="utf-8")

    # ---------- J: final report ----------
    flags={
        "BINANCE_OOS_DONE":"NO (requested window absent)",
        "BINANCE_DATES_PROCESSED":[],
        "BINANCE_FULL_DAYS":[],"BINANCE_PARTIAL_DAYS":[],"BINANCE_BAD_DAYS":[],
        "BINANCE_ARCHIVES_FOUND":"YES_but_only_to_2026-05-20",
        "MAX_BINANCE_DATE_AVAILABLE":max_date,
        "REQUESTED_WINDOW_ABSENT_DAYS":req_absent,
        "BINANCE_RS1_DONE":"NO","BINANCE_RS1_TRADES":0,"BINANCE_RS1_WINS":0,"BINANCE_RS1_LOSSES":0,
        "BINANCE_RS1_TIMEOUTS":0,"BINANCE_RS1_WINRATE":None,"BINANCE_RS1_EXPECTANCY_AFTER_COST":None,
        "BINANCE_RS1_PF_AFTER_COST":None,"BINANCE_RS1_TOTAL_RETURN_AFTER_COST":None,
        "BINANCE_RS2_DONE":"NO","BINANCE_RS2_TRADES":0,"BINANCE_RS2_WINS":0,"BINANCE_RS2_LOSSES":0,
        "BINANCE_RS2_TIMEOUTS":0,"BINANCE_RS2_WINRATE":None,"BINANCE_RS2_EXPECTANCY_AFTER_COST":None,
        "BINANCE_RS2_PF_AFTER_COST":None,"BINANCE_RS2_IMPROVES_RS1":"UNKNOWN",
        "BINANCE_RS1_TRANSFER_SUCCESS":"UNKNOWN","BINANCE_RS2_TRANSFER_SUCCESS":"UNKNOWN",
        "BINANCE_CONFIRMS_OKX_EDGE":"UNKNOWN",
        "NO_THRESHOLD_RETUNING_DONE":"YES","CANONICAL_LEDGER_USED":"YES (unchanged, not exercised — no data)",
        "TIMEOUT_PNL_EXACT":"YES (method unchanged)","FUTURE_LEAK_FOUND":"NO",
        "READY_FOR_TELEGRAM_SHADOW_MODE":"NO","READY_TO_CHANGE_ENGINE":"NO",
        "READY_FOR_PRODUCTION_TRADING":"NO","MORE_VALIDATION_REQUIRED":"YES"}
    J={"build_time_utc":now_iso(),
       "verdict":"BLOCKED — requested OOS window 2026-05-21..2026-05-30 does not exist in the project.",
       "max_date_available":max_date,
       "answers":{
         "1_dates_processed":"NONE of 05-21..30 (absent). Reference data exists only for 05-17..20.",
         "2_full_partial_bad":"N/A for requested window. Reference: 05-18 full, 05-17/19/20 partial (prior work).",
         "3_rs1_transfer":"UNKNOWN — could not run (no data).",
         "4_s7_improves":"UNKNOWN — could not run.",
         "5_comparable_to_okx":"UNKNOWN — no Binance OOS sample.",
         "6_sample_enough":"NO — zero days in requested window.",
         "7_confirm_or_reject_edge":"UNKNOWN — edge neither confirmed nor rejected.",
         "8_what_failed":"Data availability: the 05-21..30 recordings were never archived (snapshot stops at 05-20).",
         "9_next":"Obtain/record Binance Futures BTCUSDT for 2026-05-21..30 (or any unseen >=20-trading-day window), "
                  "normalize to data/binance-historical/BTCUSDT/<date>/, then re-run this exact gate + RS1 then RS2. "
                  "Alternatively run a clearly-labeled small cross-venue check on the 4 available 05-17..20 days "
                  "(expected <10 trades -> UNKNOWN by project standard).",
         "10_telegram_ready":"NO — OOS not done."},
       "flags":flags}
    (OUT/"BINANCE_2026_05_21_30_OOS_FINAL_REPORT.json").write_text(json.dumps(J,indent=2,default=str),encoding="utf-8")
    md=["# Binance OOS 2026-05-21..30 — FINAL REPORT","",f"**Build:** {now_iso()}","",
        "## VERDICT: BLOCKED — requested window does not exist","",
        f"- **Max Binance date available in project: `{max_date}`.**",
        f"- Requested days absent: {req_absent}",
        "- The Binance live-recorder archive snapshot (`OFFRW`) was created on 2026-05-21 and contains data "
        "only through 2026-05-20. Days 2026-05-21..2026-05-30 were never recorded into any available archive.",
        "- Per strict rules (no fabrication, OOS not calibration), the OKX RS1/RS2 frozen models were NOT applied "
        "to non-existent data.",
        "",
        "## Answers",
        "1. Dates processed: **NONE of 05-21..30** (absent). Real Binance data exists only for 05-17..20.",
        "2. Full/partial/bad: N/A for requested window (reference 05-18 full; 05-17/19/20 partial).",
        "3. Did RS1 transfer? **UNKNOWN** (no data to run).",
        "4. Did S7 improve RS1? **UNKNOWN**.",
        "5. Comparable to OKX March? **UNKNOWN** (no sample).",
        "6. Sample enough? **NO** (zero days).",
        "7. Confirm/reject OKX edge? **UNKNOWN** — neither.",
        "8. What failed: **data availability** — archive stops at 05-20.",
        "9. Next: record/obtain Binance BTCUSDT 05-21..30 (or any unseen >=20-trade window), normalize, re-run gate + RS1 then RS2.",
        "10. Telegram shadow ready? **NO**.",
        "",
        "## Frozen models remain intact (unchanged, ready to apply once data exists)",
        "- RS1: dist_to_recent_swing_high_pct<=0.4616 AND dl2_supp_minus_opp_net_flow_15m<=4497.76, top1/day; TP2% SL1.5% no-BE 24h cost0.14%.",
        "- RS2: RS1 + EV>0.4 (p_reach formula). NOTE: Binance HAS native OI/funding/liquidations for 05-17..20, "
        "so a future in-window recording would allow FULL RS2 (true fuel), unlike OKX March (daily OI only).",
        "",
        "## Final flags","```"]
    for k,v in flags.items(): md.append(f"{k} = {v}")
    md.append("```")
    (OUT/"BINANCE_2026_05_21_30_OOS_FINAL_REPORT.md").write_text("\n".join(md),encoding="utf-8")

    # console
    print("ARCHIVE INVENTORY:")
    for r in inv:
        print(f"  {Path(r['file']).name:<22} {round(r['size_bytes']/1e6,1):>8}MB  sha256={r['sha256'][:16]}  dirs={r.get('inner_date_dirs')}")
    print(f"\nALL DATES DETECTED: {sorted(all_dates)}")
    print(f"MAX DATE AVAILABLE: {max_date}")
    print(f"REQUESTED 05-21..30 PRESENT: {req_present or 'NONE'}")
    print(f"REQUESTED 05-21..30 ABSENT: {req_absent}")
    print("\nREFERENCE DAY QUALITY (05-17..20):")
    for r in dq_rows:
        print(f"  {r['date']} cov={r['coverage_hours']}h status={r['status']} trades_rows={r['trades_rows']}")
    print("\nFINAL FLAGS:")
    for k,v in flags.items(): print(f"  {k:<40s} = {v}")
    return 0

if __name__=="__main__":
    import sys; sys.exit(main())
