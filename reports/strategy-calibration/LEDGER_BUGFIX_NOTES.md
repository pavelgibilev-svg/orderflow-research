# Ledger bugfix notes - blind 24h hold -> actual exit timestamp

**Build:** 2026-05-23T15:00:16+00:00

## Primary bug

- Description: Strict-ledger walker locked the position for a FULL 24h after entry, regardless of when target/stop/timeout actually fired. This blocked ~90+ filtered signals on OKX (only 13 trades survived) vs 41+ under the correct (actual-exit) model.
- Buggy formula: `open_until_sec = trig_sec + 24 * 3600  (TIMEOUT_H * 3600, applied to every trade)`
- Correct formula: `open_until_sec = sim['exit_sec']     (actual target/stop/timeout exit)`

## Where the old bug lived

- File: `scripts/strategy-calibration/hi_priority_filter_research.py`
- Function: `section_f_entry_stop_alternatives -> nested strict_ledger helper`
- Buggy line ref: `open_until = trig_sec + TIMEOUT_H * 3600`
- Status: left in place for archival reproducibility of older reports; documented as DEPRECATED. New analyses MUST use canonical_ledger.py.

## Canonical replacement

- TypeScript module: `src/research/canonicalLedger.ts`
- Python mirror: `scripts/strategy-calibration/canonical_ledger.py`
- Tests: `tests/canonicalLedger.test.ts (8 tests, including REGRESSION test for blind 24h hold)`

## Files modified in this change

- `src/research/canonicalLedger.ts                       (NEW)`
- `tests/canonicalLedger.test.ts                         (NEW)`
- `scripts/strategy-calibration/canonical_ledger.py     (NEW)`
- `scripts/strategy-calibration/okx_march_canonical_retest.py  (NEW)`
- `reports/strategy-calibration/LEDGER_BUGFIX_NOTES.{md,json}    (NEW)`
- `reports/strategy-calibration/OKX_MARCH_CANONICAL_LEDGER_RETEST.{md,json,csv}  (NEW)`
- `reports/strategy-calibration/LEDGER_FIX_AND_OKX_MARCH_RETEST_SUMMARY.{md,json}  (NEW)`

## Files NOT modified (strategy engine / detectors)

- `src/strategy/zoneDetector.ts            (UNCHANGED)`
- `src/strategy/zoneScoreV1.ts             (UNCHANGED)`
- `src/cli/backtestDay.ts                  (UNCHANGED)`
- `src/cli/backtestOkxTechnical.ts         (UNCHANGED)`

## Regression test summary

tests/canonicalLedger.test.ts includes an explicit REGRESSION test that creates Signal A which stops at 01:00 and Signal B at 02:00 (well within the OLD buggy 24h hold window). Under the correct canonical model, both trades must be admitted. Under the OLD buggy code, signal B would be skipped. The test asserts n_trades=2 and skippedDueToPosition=0 to guarantee the bug cannot return.

## Flags

- `LEDGER_BUGFIX_DONE` = **YES**
- `BLIND_24H_HOLD_REMOVED_from_canonical` = **YES**
- `BLIND_24H_HOLD_remaining_in_legacy_scripts` = **YES (in hi_priority_filter_research.py Section F only; documented as DEPRECATED, not used for new reports)**