"""Fourth-pass discovery: use get_cost / get_record_count / get_billable_size
to confirm BTC.FUT and MBT.FUT parent symbols work for data queries, and
to estimate cost for the target week."""
from __future__ import annotations
import json
import sys
from pathlib import Path

TOKEN_PATH = Path("data/databento/access_token.txt")
DATASET = "GLBX.MDP3"
WEEK_START = "2026-04-01"
WEEK_END = "2026-04-08"


def main() -> int:
    key = TOKEN_PATH.read_text(encoding="utf-8").strip()
    import databento as db
    client = db.Historical(key=key)
    out: dict = {}

    print("=== get_record_count + get_cost + get_billable_size ===")
    cases = [
        ("BTC.FUT", "parent", "mbo"),
        ("BTC.FUT", "parent", "mbp-10"),
        ("BTC.FUT", "parent", "trades"),
        ("MBT.FUT", "parent", "mbo"),
        ("MBT.FUT", "parent", "mbp-10"),
        ("MBT.FUT", "parent", "trades"),
    ]
    for sym, stype_in, schema in cases:
        key2 = f"{sym}|{schema}"
        info = {}
        for fn_name in ("get_record_count", "get_billable_size", "get_cost"):
            fn = getattr(client.metadata, fn_name)
            try:
                v = fn(
                    dataset=DATASET,
                    symbols=[sym],
                    stype_in=stype_in,
                    schema=schema,
                    start=f"{WEEK_START}T00:00:00",
                    end=f"{WEEK_END}T00:00:00",
                )
                info[fn_name] = v
            except Exception as e:
                info[fn_name + "_error"] = str(e)[:200]
        out[key2] = info
        print(f"  {key2}: {info}")

    Path("data/databento/_discovery4_raw.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
