"""Second-pass discovery: find BTC symbols on GLBX.MDP3 with correct stype_in.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

TOKEN_PATH = Path("data/databento/access_token.txt")


def main() -> int:
    key = TOKEN_PATH.read_text(encoding="utf-8").strip()
    import databento as db

    client = db.Historical(key=key)
    out: dict = {}

    # 1) Use list_symbols on GLBX.MDP3 to find any BTC-related raw symbols.
    print("=== list_unique_symbols GLBX.MDP3 ===")
    try:
        # Many DB API versions expose this; if not, will error.
        syms = client.metadata.list_unique_symbols(
            dataset="GLBX.MDP3",
            start_date="2026-04-01",
            end_date="2026-04-08",
            stype_in="raw_symbol",
        )
        btc = [s for s in syms if "BTC" in s or "MBT" in s or "BFF" in s]
        out["btc_like_symbols_glbx"] = btc
        print(f"  total symbols on GLBX in week = {len(syms)}; BTC-like = {len(btc)}")
        for s in btc[:50]:
            print(f"    {s}")
    except Exception as e:
        out["list_unique_symbols_error"] = repr(e)
        print(f"  FAIL: {e!r}")

    # 2) Try resolving parent symbol BTC with the various stype_in names.
    for stype_in in ("parent", "continuous", "smart", "raw_symbol"):
        for sym in ("BTC.FUT", "MBT.FUT", "BTC.c.0", "MBT.c.0", "BTC", "MBT"):
            try:
                r = client.symbology.resolve(
                    dataset="GLBX.MDP3",
                    symbols=[sym],
                    stype_in=stype_in,
                    stype_out="raw_symbol",
                    start_date="2026-04-01",
                    end_date="2026-04-08",
                )
                mappings = r.get("result") if isinstance(r, dict) else r
                if mappings:
                    out.setdefault("resolves", {})[f"{sym}|{stype_in}"] = mappings
                    print(f"  resolve OK: {sym} via stype_in={stype_in} -> {list(mappings.keys())[:5]}")
                    sample = next(iter(mappings.values()))
                    print(f"    sample: {sample}")
            except Exception as e:
                msg = str(e)
                if "422" in msg or "invalid" in msg.lower():
                    pass
                else:
                    out.setdefault("resolve_errors", {})[f"{sym}|{stype_in}"] = msg[:200]

    Path("data/databento/_discovery2_raw.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
