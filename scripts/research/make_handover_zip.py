"""Build the OKX-May-18d research HANDOVER zip.

Packs (full scope): code (src, scripts, config, root files) + reports/okx-may-early/ (all reports, caches,
per-day zones) + the strategy-calibration NEXT_WINDOWS_* / CALIBRATION_* artifacts + data/daily schema.
Excludes __pycache__/*.pyc, node_modules, .git, dist, *.zip. Forward-slash arcnames under orderflow-handover/.
Output: dist/orderflow-handover-okx-may-18d_<UTC-date>.zip  (+ .sha256 + an in-zip ARCHIVE_CONTENTS.txt).
"""
from __future__ import annotations
import datetime as dt, hashlib, sys, zipfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "package.json").exists() and (p / "scripts").exists())
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
OUT = ROOT / "dist" / f"orderflow-handover-okx-may-18d_{STAMP}.zip"
TOP = "orderflow-handover"

ROOT_FILES = ["package.json", "package-lock.json", "tsconfig.json", ".env.example",
              "requirements.txt", "DATA_HANDOVER.md", "MANIFEST.txt", ".gitignore"]
DIRS = ["src", "config", "scripts"]
REPORT_DIRS = ["reports/okx-may-early"]
GLOB_FILES = [("reports/strategy-calibration", "NEXT_WINDOWS_TO_DOWNLOAD.*"),
              ("reports/strategy-calibration", "CALIBRATION_WINDOW_PLAN.*"),
              ("data/daily", "BTC_USDT_1d.SCHEMA.csv")]

EXC_PARTS = {"__pycache__", ".git", "node_modules", "dist"}
def excluded(p: Path) -> bool:
    if any(part in EXC_PARTS for part in p.parts): return True
    if p.suffix in (".pyc", ".zip"): return True
    return False


def collect():
    files = []
    for rf in ROOT_FILES:
        p = ROOT / rf
        if p.is_file(): files.append(p)
    for d in DIRS + REPORT_DIRS:
        base = ROOT / d
        if not base.exists(): continue
        for p in base.rglob("*"):
            if p.is_file() and not excluded(p): files.append(p)
    for d, pat in GLOB_FILES:
        for p in (ROOT / d).glob(pat):
            if p.is_file() and not excluded(p): files.append(p)
    # de-dup, stable order
    seen = set(); out = []
    for p in sorted(files):
        if p not in seen: seen.add(p); out.append(p)
    return out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists(): OUT.unlink()
    files = collect()
    total = sum(p.stat().st_size for p in files)
    # build manifest of contents grouped by top dir
    groups = {}
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        key = rel.split("/")[0] if "/" in rel else "(root files)"
        groups.setdefault(key, [0, 0]); groups[key][0] += 1; groups[key][1] += p.stat().st_size
    contents = [f"ORDERFLOW HANDOVER — OKX May 18d", f"Built (UTC): {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
                f"Files: {len(files)}  Raw bytes: {total}", "", "By top-level group:"]
    for k in sorted(groups):
        contents.append(f"  {k:<24} {groups[k][0]:>4} files  {groups[k][1]/1e6:.2f} MB")
    contents += ["", "See MANIFEST.txt for full description (caches vs reports, dates, commands, commit)."]
    contents_txt = "\n".join(contents)

    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(f"{TOP}/ARCHIVE_CONTENTS.txt", contents_txt)
        for p in files:
            zf.write(p, arcname=f"{TOP}/{p.relative_to(ROOT).as_posix()}")

    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    (OUT.with_suffix(".zip.sha256")).write_text(f"{sha}  {OUT.name}\n", encoding="utf-8")

    print(contents_txt)
    print("")
    print(f"zip_path   = {OUT}")
    print(f"zip_size   = {OUT.stat().st_size/1e6:.2f} MB")
    print(f"sha256     = {sha}")
    print(f"sha256_file= {OUT.with_suffix('.zip.sha256')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
