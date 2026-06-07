"""Databento discovery: list datasets, schemas, BTC-related symbols.

Reads the API key from data/databento/access_token.txt — never prints it.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

TOKEN_PATH = Path("data/databento/access_token.txt")


def load_key() -> str:
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


def redact(s: str) -> str:
    if not s:
        return "<empty>"
    return f"{s[:3]}...{s[-2:]} (len={len(s)})"


def main() -> int:
    key = load_key()
    print(json.dumps({"key_preview": redact(key)}, indent=2))

    import databento as db
    print(json.dumps({"databento_version": getattr(db, "__version__", "?")}, indent=2))

    client = db.Historical(key=key)
    out: dict = {}

    print("=== list_datasets ===")
    try:
        ds = client.metadata.list_datasets()
        out["datasets"] = ds
        print(json.dumps(ds, indent=2))
    except Exception as e:
        out["datasets_error"] = repr(e)
        print(f"FAIL: {e!r}")

    # Probe each dataset for crypto / BTC content. The list is normally
    # short (a handful of regulated venues).
    out["dataset_probes"] = {}
    for d in (out.get("datasets") or []):
        info = {}
        try:
            info["schemas"] = client.metadata.list_schemas(dataset=d)
        except Exception as e:
            info["schemas_error"] = repr(e)
        try:
            info["dataset_range"] = client.metadata.get_dataset_range(dataset=d)
        except Exception as e:
            info["dataset_range_error"] = repr(e)
        out["dataset_probes"][d] = info
        print(f"{d}: schemas={info.get('schemas')} range={info.get('dataset_range')}")

    # CME Globex futures (GLBX.MDP3) is the dataset most likely to carry
    # BTC futures. Probe for BTC* and MBT* parent symbols.
    target_dataset = "GLBX.MDP3"
    if target_dataset in (out.get("datasets") or []):
        print(f"=== GLBX.MDP3 parent symbol probes ===")
        # parent symbology examples for CME crypto futures:
        #   BTC.FUT  -> all expirations of the regular Bitcoin futures
        #   MBT.FUT  -> all expirations of Micro Bitcoin futures
        #   ETH.FUT  -> Ether futures
        #   MET.FUT  -> Micro Ether futures
        probes = ["BTC.FUT", "MBT.FUT", "ETH.FUT", "MET.FUT"]
        # Try continuous symbology too
        cont = ["BTC.c.0", "MBT.c.0", "ETH.c.0", "MET.c.0"]

        # resolve()
        for s in probes + cont:
            try:
                r = client.symbology.resolve(
                    dataset=target_dataset,
                    symbols=[s],
                    stype_in="parent" if s.endswith(".FUT") else "continuous",
                    stype_out="raw_symbol",
                    start_date="2026-04-01",
                    end_date="2026-04-08",
                )
                out.setdefault("glbx_symbol_probes", {})[s] = r
                print(f"  resolve {s}: {r}")
            except Exception as e:
                out.setdefault("glbx_symbol_probes", {})[s] = {"error": repr(e)}
                print(f"  resolve {s} FAIL: {e!r}")

    Path("data/databento/_discovery_raw.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
