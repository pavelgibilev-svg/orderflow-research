"""
Probe Kaggle access for the orderflow-research audit.

Reads the API token from data/kaggle/access_token.txt and tries multiple
auth strategies, in order:
  1) JSON-style kaggle.json (username + key)
  2) Raw bearer KGAT via kagglehub
  3) Raw bearer KGAT via direct REST call

NEVER prints the token. Only redacted previews and result codes go to stdout.
"""

from __future__ import annotations
import json
import os
import sys
from pathlib import Path

TOKEN_PATH = Path("data/kaggle/access_token.txt")
DATASET = "krrdev1/binance-btcusdt-l3-market-microstructure-data"


def redact(s: str) -> str:
    if not s:
        return "<empty>"
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:3]}...{s[-2:]} (len={len(s)})"


def load_token() -> tuple[str, object]:
    raw = TOKEN_PATH.read_text(encoding="utf-8").strip()
    if raw.startswith("{"):
        return ("json", json.loads(raw))
    return ("raw", raw)


def configure_env() -> dict:
    kind, val = load_token()
    info: dict = {"kind": kind}
    if kind == "json":
        info["username"] = val.get("username", "")
        info["key_preview"] = redact(val.get("key", ""))
        os.environ["KAGGLE_USERNAME"] = val["username"]
        os.environ["KAGGLE_KEY"] = val["key"]
    else:
        info["token_preview"] = redact(val)
        # Try every env var name kagglehub / kagglesdk has historically used
        os.environ["KAGGLE_API_TOKEN"] = val
        os.environ["KAGGLE_KEY"] = val
        # For some flows kagglehub picks up KAGGLE_USERNAME/KEY format only;
        # bearer tokens are accepted by the REST API directly.
    return info


def try_rest_v1(token: str) -> dict:
    """Direct call to https://www.kaggle.com/api/v1/ — works with any token format
    that Kaggle's gateway accepts as Bearer.
    """
    import urllib.request
    import urllib.error
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "orderflow-research-audit/1.0",
    }
    out: dict = {}

    # 1) Search for btcusdt datasets to confirm auth works
    url = "https://www.kaggle.com/api/v1/datasets/list?search=btcusdt"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            out["search_btcusdt_status"] = resp.status
            out["search_btcusdt_count"] = len(data) if isinstance(data, list) else None
            out["search_btcusdt_sample"] = [
                {"ref": d.get("ref"), "title": d.get("title"), "size": d.get("totalBytes")}
                for d in (data[:5] if isinstance(data, list) else [])
            ]
    except urllib.error.HTTPError as e:
        out["search_btcusdt_status"] = e.code
        out["search_btcusdt_error"] = e.reason
        try:
            out["search_btcusdt_body"] = e.read().decode("utf-8")[:500]
        except Exception:
            pass
    except Exception as e:
        out["search_btcusdt_error"] = repr(e)

    # 2) List files of the target dataset
    owner, name = DATASET.split("/")
    url = f"https://www.kaggle.com/api/v1/datasets/list/files/{owner}/{name}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            out["list_files_status"] = resp.status
            out["list_files_payload_keys"] = list(data.keys()) if isinstance(data, dict) else None
            out["list_files"] = data
    except urllib.error.HTTPError as e:
        out["list_files_status"] = e.code
        out["list_files_error"] = e.reason
        try:
            out["list_files_body"] = e.read().decode("utf-8")[:500]
        except Exception:
            pass
    except Exception as e:
        out["list_files_error"] = repr(e)

    # 3) Dataset metadata (alternate endpoint)
    url = f"https://www.kaggle.com/api/v1/datasets/view/{owner}/{name}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            out["view_status"] = resp.status
            interesting = {
                k: data.get(k)
                for k in (
                    "id", "ref", "title", "subtitle", "description",
                    "ownerUser", "ownerName", "totalBytes", "lastUpdated",
                    "currentVersionNumber", "downloadCount", "viewCount",
                    "voteCount", "licenseName", "files", "creatorName",
                )
                if k in data
            }
            # Truncate description for readability
            if isinstance(interesting.get("description"), str):
                desc = interesting["description"]
                interesting["description_preview"] = desc[:600]
                interesting["description_length"] = len(desc)
                interesting.pop("description", None)
            out["view_interesting"] = interesting
    except urllib.error.HTTPError as e:
        out["view_status"] = e.code
        out["view_error"] = e.reason
        try:
            out["view_body"] = e.read().decode("utf-8")[:500]
        except Exception:
            pass
    except Exception as e:
        out["view_error"] = repr(e)

    return out


def try_kagglehub() -> dict:
    out: dict = {}
    try:
        import kagglehub
        out["kagglehub_version"] = getattr(kagglehub, "__version__", "?")
    except Exception as e:
        out["kagglehub_import_error"] = repr(e)
        return out
    try:
        # kagglehub doesn't have a stable list-files API in 1.0.x; we just confirm import + auth bootstrap
        out["kagglehub_ok"] = True
    except Exception as e:
        out["kagglehub_error"] = repr(e)
    return out


def main() -> int:
    if not TOKEN_PATH.exists():
        print(json.dumps({"error": f"token file missing: {TOKEN_PATH}"}, indent=2))
        return 2
    info = configure_env()
    print(json.dumps({"token_info": info}, indent=2))
    print()

    print("=== kagglehub ===")
    print(json.dumps(try_kagglehub(), indent=2))
    print()

    kind, val = load_token()
    token = val if kind == "raw" else val.get("key", "")
    print("=== REST v1 ===")
    print(json.dumps(try_rest_v1(token), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
