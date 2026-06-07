"""
Download the krrdev1/binance-btcusdt-l3-market-microstructure-data dataset
to data/kaggle/binance-btcusdt-l3/ and unzip.

Uses the raw KGAT bearer token at data/kaggle/access_token.txt and Kaggle's
public REST API. NEVER prints the token.
"""

from __future__ import annotations
import io
import json
import os
import sys
import zipfile
from pathlib import Path

TOKEN_PATH = Path("data/kaggle/access_token.txt")
DATASET = "krrdev1/binance-btcusdt-l3-market-microstructure-data"
DEST = Path("data/kaggle/binance-btcusdt-l3")
ZIP_PATH = DEST / "_dataset.zip"
META_PATH = DEST / "_dataset_meta.json"


def load_token() -> str:
    raw = TOKEN_PATH.read_text(encoding="utf-8").strip()
    if raw.startswith("{"):
        return json.loads(raw)["key"]
    return raw


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    token = load_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/octet-stream, application/json",
        "User-Agent": "orderflow-research-audit/1.0",
    }

    # 1) Pull metadata + full description so we have it locally even if download fails.
    import urllib.request
    import urllib.error

    owner, name = DATASET.split("/")
    view_url = f"https://www.kaggle.com/api/v1/datasets/view/{owner}/{name}"
    print(f"GET {view_url}")
    req = urllib.request.Request(view_url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        meta_text = resp.read().decode("utf-8")
        meta = json.loads(meta_text)
    META_PATH.write_text(meta_text, encoding="utf-8")
    print(f"  saved metadata -> {META_PATH}")

    # 2) Download the dataset zip.
    dl_url = f"https://www.kaggle.com/api/v1/datasets/download/{owner}/{name}"
    print(f"GET {dl_url}")
    req = urllib.request.Request(dl_url, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as resp:
        total = resp.headers.get("Content-Length")
        ctype = resp.headers.get("Content-Type")
        print(f"  -> status={resp.status} content_type={ctype} content_length={total}")
        bytes_written = 0
        chunk_size = 1024 * 1024
        with ZIP_PATH.open("wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)
                if bytes_written % (16 * 1024 * 1024) == 0:
                    pct = (bytes_written / int(total)) * 100 if total else 0
                    print(f"    {bytes_written:,} bytes ({pct:.1f}%)")
        print(f"  done: {bytes_written:,} bytes -> {ZIP_PATH}")

    # 3) Unzip.
    print(f"unzip {ZIP_PATH} -> {DEST}")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        names = zf.namelist()
        print(f"  archive contains {len(names)} entries")
        for n in names[:30]:
            info = zf.getinfo(n)
            print(f"    {n}  {info.file_size:,} bytes")
        if len(names) > 30:
            print(f"    ... and {len(names) - 30} more")
        zf.extractall(DEST)

    # 4) Summary listing on disk.
    extracted = sorted(p for p in DEST.rglob("*") if p.is_file() and p.suffix != ".zip")
    print(f"extracted {len(extracted)} files; total bytes: {sum(p.stat().st_size for p in extracted):,}")
    for p in extracted[:30]:
        print(f"  {p.relative_to(DEST)}  {p.stat().st_size:,} bytes")
    if len(extracted) > 30:
        print(f"  ... and {len(extracted) - 30} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
