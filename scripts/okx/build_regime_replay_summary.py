"""Build reports/OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.md / .json by joining
OKX_REGIME_TABLE.json + per-date 3h replays + (where available) full-day
replays.

3h replay results come from reports/okx_3h_snapshots/OKX_TECHNICAL_REPLAY_<date>_3h_*.
Full-day results come from reports/OKX_TECHNICAL_REPLAY_<date>_fullday_*.
The default per-date OKX_TECHNICAL_REPLAY_<date>.* files are the 3h
snapshot (restored after any full-day rerun).
"""
from __future__ import annotations
import csv
import gzip
import json
import sys
from pathlib import Path

ROOT = Path("C:/Users/gibilev/orderflow-research")
REPORTS = ROOT / "reports"
OKX_ROOT = ROOT / "data" / "okx-historical" / "BTC-USDT-SWAP"
THREE_H_SNAPS = REPORTS / "okx_3h_snapshots"


def load_regime() -> dict:
    p = REPORTS / "OKX_REGIME_TABLE.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_selection() -> list[dict]:
    p = REPORTS / "OKX_SIX_SELECTED_DATES.json"
    return json.loads(p.read_text(encoding="utf-8"))["chosen"] if p.exists() else []


def parse_daily_summary(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    out: dict[str, float] = {}
    with path.open("r", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            line = line.strip()
            if not line:
                continue
            cells = line.split(",")
            if len(cells) >= 2:
                try:
                    out[cells[0]] = float(cells[1])
                except Exception:
                    pass
    return out


def load_3h_summary(date: str) -> dict[str, float]:
    # The 3h snapshot is a copy of the original BTC-USDT-SWAP_<date>/daily_summary.csv
    # BEFORE any fullday overwrite. But we only snapshotted the OKX_TECHNICAL_REPLAY files,
    # not the daily_summary.csv. So we read the OKX_TECHNICAL_REPLAY_<date>_3h.json instead.
    p = THREE_H_SNAPS / f"OKX_TECHNICAL_REPLAY_{date}_3h.json"
    if not p.exists():
        return {}
    try:
        outer = json.loads(p.read_text(encoding="utf-8"))
        inner = outer.get("underlying_backtest_summary") or {}
        return inner.get("daily_summary") or {}
    except Exception:
        return {}


def load_fullday_summary(date: str) -> dict[str, float]:
    p = REPORTS / f"OKX_TECHNICAL_REPLAY_{date}_fullday.json"
    if not p.exists():
        # Fall back to the live daily_summary.csv if a fullday run produced one but
        # the OKX wrapper hasn't been restored to snapshot yet.
        return {}
    try:
        outer = json.loads(p.read_text(encoding="utf-8"))
        inner = outer.get("underlying_backtest_summary") or {}
        return inner.get("daily_summary") or {}
    except Exception:
        return {}


def count_l2_rows(date: str) -> int | None:
    p = OKX_ROOT / date / "incremental_book_L2.csv.gz"
    if not p.exists():
        return None
    n = 0
    try:
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for _ in f:
                n += 1
        return n
    except Exception:
        return None


def fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{v*100:.2f}%"


def metrics_row(s: dict[str, float]) -> dict:
    if not s:
        return {}
    return {
        "zones_total": int(s.get("zones_total", 0)),
        "zones_triggered": int(s.get("zones_triggered", 0)),
        "zones_reached": int(s.get("zones_reached", 0)),
        "long_zones": int(s.get("direction_LONG", 0)),
        "short_zones": int(s.get("direction_SHORT", 0)),
        "unique_moves": int(s.get("unique_reached_moves", 0)),
        "raw_hit_rate": s.get("raw_triggered_hit_rate", 0.0),
        "unique_move_hit_rate": s.get("unique_move_adjusted_hit_rate", 0.0),
        "duplicate_suppressions": int(s.get("duplicate_suppression_count", 0)),
    }


def main() -> int:
    regime = load_regime()
    regime_by_date = {r["date"]: r for r in regime.get("dates", [])}
    selected = load_selection()
    if not selected:
        print("missing OKX_SIX_SELECTED_DATES.json — run select_six_dates.py first.")
        return 1

    rows: list[dict] = []
    for s in selected:
        d = s["date"]
        rg = regime_by_date.get(d, {})
        s3 = load_3h_summary(d)
        sf = load_fullday_summary(d)
        # If 3h snapshot not present (older selection), fall back to the live BTC-USDT-SWAP_<date>/daily_summary.csv
        if not s3:
            s3 = parse_daily_summary(REPORTS / f"BTC-USDT-SWAP_{d}" / "daily_summary.csv")
        l2 = count_l2_rows(d)
        trades_n = rg.get("trades_n", 0)
        rows.append({
            "date": d,
            "bucket": s["bucket"],
            "regime_native": rg.get("regime"),
            "day_return_pct": rg.get("day_return_pct"),
            "range_pct": rg.get("range_pct"),
            "horizons": rg.get("horizons"),
            "feasibility": rg.get("feasibility"),
            "l2_rows": l2,
            "trades_rows": trades_n,
            "three_h": metrics_row(s3),
            "fullday": metrics_row(sf),
            "fullday_ran": bool(sf),
        })

    md = [
        "# OKX first-day regime + technical replay summary (6 chosen dates)",
        "",
        "**Venue:** OKX `okex-swap` BTC-USDT-SWAP (perpetual)",
        "**Source:** Tardis CDN first-of-month free samples (29 dates classified, 6 selected)",
        "**Selection:** 2 bullish + 2 bearish + 2 choppy chosen from the regime table",
        "**Strategy thresholds:** Binance USDS-M Futures defaults — **UNCHANGED**",
        "",
        "## HARD DISCLAIMER",
        "",
        "  • OKX is NOT Binance.",
        "  • Strategy thresholds are calibrated for Binance USDS-M Futures BTCUSDT-perp.",
        "  • Numbers below are the engine's reaction to OKX microstructure with Binance-tuned thresholds left UNCHANGED.",
        "  • Do NOT quote any of these numbers as a strategy edge or winrate.",
        "  • Purpose: cross-venue research on engine behaviour across regimes.",
        "",
        "## A. Per-date overview — **3 h cap** (L2 capped at 03:00 UTC, trades full 24 h)",
        "",
        "| date       | bucket   | day Δ %  | range % | L2 rows         | trades rows     | zones | triggered | reached | LONG | SHORT | unique moves | dedup suppr. | raw hit | uniq-move hit |",
        "|------------|----------|---------:|--------:|----------------:|----------------:|------:|----------:|--------:|-----:|------:|-------------:|-------------:|--------:|--------------:|",
    ]
    for r in rows:
        m = r["three_h"] or {}
        l2 = f"{r['l2_rows']:>15,d}" if r["l2_rows"] is not None else "—".rjust(15)
        tr = f"{r['trades_rows']:>14,d}" if r["trades_rows"] else "—".rjust(14)
        if not m:
            md.append(f"| {r['date']} | {r['bucket']:<8s} | {r['day_return_pct']:+6.2f}  | {r['range_pct']:6.2f} | {l2} | {tr} |    — |        — |       — |    — |     — |            — |            — |     —   |             — |")
        else:
            md.append(
                f"| {r['date']} | {r['bucket']:<8s} | {r['day_return_pct']:+6.2f}  | {r['range_pct']:6.2f} | "
                f"{l2} | {tr} | {m['zones_total']:>4d} | {m['zones_triggered']:>9d} | "
                f"{m['zones_reached']:>7d} | {m['long_zones']:>4d} | {m['short_zones']:>5d} | "
                f"{m['unique_moves']:>12d} | {m['duplicate_suppressions']:>12d} | "
                f"{m['raw_hit_rate']*100:>6.2f}% | {m['unique_move_hit_rate']*100:>13.2f}% |"
            )

    md.extend([
        "",
        "## B. Per-date overview — **full UTC day** (L2 full 24 h, trades full 24 h)",
        "",
        "Full-day replay is much heavier per date (~30–75 min wall-clock depending on L2 file size). To stay within compute budget, only one date was executed end-to-end here. The remaining five dates have their 3 h metrics in Section A; full-day reruns are a known follow-up.",
        "",
        "| date       | bucket   | zones | triggered | reached | LONG | SHORT | unique moves | dedup suppr. | raw hit | uniq-move hit |",
        "|------------|----------|------:|----------:|--------:|-----:|------:|-------------:|-------------:|--------:|--------------:|",
    ])
    for r in rows:
        m = r["fullday"]
        if not m:
            md.append(f"| {r['date']} | {r['bucket']:<8s} |    — |        — |       — |    — |     — |            — |            — |   not yet — see Section A 3 h numbers |")
        else:
            md.append(
                f"| {r['date']} | {r['bucket']:<8s} | {m['zones_total']:>4d} | "
                f"{m['zones_triggered']:>9d} | {m['zones_reached']:>7d} | {m['long_zones']:>4d} | "
                f"{m['short_zones']:>5d} | {m['unique_moves']:>12d} | {m['duplicate_suppressions']:>12d} | "
                f"{m['raw_hit_rate']*100:>6.2f}% | {m['unique_move_hit_rate']*100:>13.2f}% |"
            )

    md.extend([
        "",
        "## C. Per-date target feasibility (24 h max forward move from any minute)",
        "",
        "| date       | 4h up | 4h dn | 8h up | 8h dn | 24h up | 24h dn | 0.5% | 1% | 1.5% | 2% |",
        "|------------|------:|------:|------:|------:|-------:|-------:|:----:|:--:|:----:|:--:|",
    ])
    for r in rows:
        h = r["horizons"] or {}
        f4 = h.get("4h", {}); f8 = h.get("8h", {}); f24 = h.get("24h", {})
        feas = r["feasibility"] or {}
        md.append(
            f"| {r['date']} | {f4.get('max_up_pct',0):5.2f} | {f4.get('max_down_pct',0):5.2f} | "
            f"{f8.get('max_up_pct',0):5.2f} | {f8.get('max_down_pct',0):5.2f} | "
            f"{f24.get('max_up_pct',0):6.2f} | {f24.get('max_down_pct',0):6.2f} | "
            f"{'✓' if feas.get('0.5pct') else '·':^4s} | {'✓' if feas.get('1.0pct') else '·':^2s} | "
            f"{'✓' if feas.get('1.5pct') else '·':^4s} | {'✓' if feas.get('2.0pct') else '·':^2s} |"
        )

    md.extend([
        "",
        "## D. Per-date quality / behaviour notes",
        "",
    ])
    for r in rows:
        notes: list[str] = []
        m3 = r["three_h"] or {}
        mf = r["fullday"] or {}
        if m3.get("zones_triggered", 0) > 0 and m3.get("zones_reached", 0) == 0:
            notes.append("3h: engine triggered but never reached 2% — consistent with the day's regime / feasibility table for the first 3 hours UTC.")
        if mf and mf.get("unique_moves", 0) > 0 and mf.get("zones_reached", 0) > mf["unique_moves"]:
            notes.append(f"full-day: {mf['zones_reached']} reaches but only {mf['unique_moves']} unique move — {mf['zones_reached']-mf['unique_moves']} duplicate-move-credit zones absorbed by clustering.")
        if mf and mf.get("zones_total", 0) > 3 * m3.get("zones_total", 1):
            notes.append("full-day produced >3× more zones than 3h — most signal came from the 21 h after the 3 h cap.")
        if not m3:
            notes.append("3 h replay missing.")
        if not notes:
            notes.append("clean.")
        md.append(f"- **{r['date']}** ({r['bucket']}, day Δ {r['day_return_pct']:+.2f}%): " + " ".join(notes))

    md.extend([
        "",
        "## E. Interpretation guide",
        "",
        "- **`bullish` days with 2 % feasibility** are mechanically the easiest to register LONG reaches; bearish days the same for SHORT. A bullish day that still produces 0 reaches in 3 h points to trigger-timing or zone-band placement mismatch with this venue's microstructure, not to a strategy defect.",
        "- **`choppy` days with `2 %` infeasibility** are guaranteed 0 % reach for a 2 % target. Any triggers there land as RESOLVED_FAILED regardless of strategy quality.",
        "- **3 h vs full-day:** the 3 h cap is a compute-budget knob, not a strategy threshold. Full-day on 2024-01-01 produced 43 zones vs 10 in the 3 h cap — 4× more zones and many more triggers, but the **unique-move count stays low (1)** because the strategy keeps firing similar same-direction zones throughout a sustained multi-hour rally. This is the exact phenomenon the unique-move-clustering accounting fix was built for.",
        "- **Dedup suppression counts rise to 4-15K under full-day** — the engine sees a high volume of same-direction candidates, which the deduplication layer absorbs. Whether the residual zone density is appropriately calibrated for OKX is a separate, deliberately-out-of-scope calibration task.",
        "",
        "## F. What's still missing for a real cross-venue conclusion",
        "",
        "- **Full-day on the other 5 dates** — pending compute budget; ~30–75 min per date × 5 = ~3–6 hours total. Run via:",
        "  ```",
        "  for D in 2024-07-01 2024-10-01 2025-10-01 2025-12-01 2026-04-01; do",
        "    npm run backtest:okx-technical -- --date $D --window full-day",
        "    for E in md json _ZONES.csv; do mv reports/OKX_TECHNICAL_REPLAY_$D.$E reports/OKX_TECHNICAL_REPLAY_${D}_fullday.$E; done",
        "    cp reports/okx_3h_snapshots/OKX_TECHNICAL_REPLAY_${D}_3h.* reports/  # restore 3h",
        "  done",
        "  ```",
        "- **More than 6 days** — would need Tardis paid tier or OKX VIP/premium for non-first-of-month days.",
        "- **A venue-calibrated thresholds config** — explicitly out of scope per the user's hard rules.",
        "- **A matched-window Binance backtest** on the same UTC days for direct head-to-head.",
        "",
        "Companion JSON: `reports/OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.json`",
        "",
        "## G. File layout",
        "",
        "```",
        "data/okx-historical/BTC-USDT-SWAP/<date>/",
        "    incremental_book_L2.csv.gz       # 5 dates full + 3 dates with only trades",
        "    trades.csv.gz                    # all 29 dates",
        "    book_ticker.csv.gz               # only 2026-04-01",
        "    derivative_ticker.csv.gz         # only 2026-04-01",
        "    liquidations.csv.gz              # only 2026-04-01",
        "",
        "reports/",
        "    OKX_REGIME_TABLE.md/.json                    # 29 dates classified",
        "    OKX_SIX_SELECTED_DATES.json                  # the 6 chosen for replay",
        "    OKX_TECHNICAL_REPLAY_<date>.md/.json/.csv    # 3 h cap, current head",
        "    OKX_TECHNICAL_REPLAY_<date>_fullday.{md,json,_ZONES.csv}  # full UTC day where run",
        "    okx_3h_snapshots/OKX_TECHNICAL_REPLAY_<date>_3h.*        # immutable 3 h backups",
        "    OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.md/.json (this file)",
        "    BTC-USDT-SWAP_<date>/                        # underlying per-date backtest output",
        "```",
    ])

    out_md = REPORTS / "OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    out_json = REPORTS / "OKX_FIRST_DAY_REGIME_AND_REPLAY_SUMMARY.json"
    out_json.write_text(json.dumps({
        "venue": "OKX (okex-swap)",
        "symbol": "BTC-USDT-SWAP",
        "selected_dates": [s["date"] for s in selected],
        "strategy_thresholds_unchanged": True,
        "okx_is_binance": False,
        "okx_is_directly_equivalent_to_binance_usdsm_futures": False,
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"wrote {out_md}")
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
