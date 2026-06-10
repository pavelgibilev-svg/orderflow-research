"""Pack dist/orderflow-live-recorder-deploy/ into a zip with portable
forward-slash paths (so it extracts cleanly on Linux/macOS).
"""
import os
import sys
import zipfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
SRC = ROOT / "dist" / "orderflow-live-recorder-deploy"
OUT = ROOT / "dist" / "orderflow-live-recorder-deploy.zip"

if OUT.exists():
    OUT.unlink()

n = 0
total = 0
with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for p in sorted(SRC.rglob("*")):
        if p.is_file():
            rel = p.relative_to(SRC).as_posix()
            arcname = f"orderflow-live-recorder-deploy/{rel}"
            zf.write(p, arcname=arcname)
            n += 1
            total += p.stat().st_size

print(f"files={n}")
print(f"raw_bytes={total}")
print(f"zip_path={OUT}")
print(f"zip_size_bytes={OUT.stat().st_size}")
