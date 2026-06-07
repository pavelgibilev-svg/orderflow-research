"""Third-pass discovery: probe parent/continuous symbols on GLBX directly."""
from __future__ import annotations
import json
import sys
import traceback
from pathlib import Path

TOKEN_PATH = Path("data/databento/access_token.txt")


def main() -> int:
    key = TOKEN_PATH.read_text(encoding="utf-8").strip()
    import databento as db
    client = db.Historical(key=key)
    out: dict = {}

    print("=== try symbology.resolve variants ===")
    cases = [
        # (symbols, stype_in)
        (["BTC"], "parent"),
        (["MBT"], "parent"),
        (["ETH"], "parent"),
        (["MET"], "parent"),
        (["BTC.FUT"], "parent"),
        (["MBT.FUT"], "parent"),
        (["BTC.n.0"], "continuous"),
        (["BTC.c.0"], "continuous"),
        (["MBT.n.0"], "continuous"),
        (["MBT.c.0"], "continuous"),
        (["BTC.v.0"], "continuous"),  # volume-weighted continuous
        (["MBT.v.0"], "continuous"),
    ]
    for symbols, stype_in in cases:
        try:
            r = client.symbology.resolve(
                dataset="GLBX.MDP3",
                symbols=symbols,
                stype_in=stype_in,
                stype_out="raw_symbol",
                start_date="2026-04-01",
                end_date="2026-04-08",
            )
            mappings = r.get("result") if isinstance(r, dict) else r
            out.setdefault("resolves", {})[f"{symbols[0]}|{stype_in}"] = mappings
            print(f"  OK {symbols[0]} via {stype_in}:")
            if isinstance(mappings, dict):
                for k, v in list(mappings.items())[:5]:
                    print(f"      {k} -> {v}")
        except Exception as e:
            msg = str(e)[:250]
            out.setdefault("errors", {})[f"{symbols[0]}|{stype_in}"] = msg
            # Print the FULL error message for debugging the first few
            print(f"  ERR {symbols[0]} via {stype_in}: {msg}")

    Path("data/databento/_discovery3_raw.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
