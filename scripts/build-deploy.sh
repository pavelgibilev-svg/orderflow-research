#!/usr/bin/env bash
# Build the live-recorder deploy tree.
# Copies a curated subset of the project into dist/orderflow-live-recorder-deploy/
# and emits filenames the caller can use for typecheck/zip.

set -euo pipefail

SRC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$SRC_ROOT/dist/orderflow-live-recorder-deploy"

cd "$SRC_ROOT"
rm -rf "$DEST"
mkdir -p "$DEST"

copy() {
  local rel="$1"
  local dest_dir
  dest_dir="$DEST/$(dirname "$rel")"
  mkdir -p "$dest_dir"
  cp "$rel" "$DEST/$rel"
}

# --- top-level project files
for f in package.json package-lock.json tsconfig.json vitest.config.ts docker-compose.yml .env.example README.md .gitignore; do
  if [ -f "$f" ]; then copy "$f"; fi
done

# --- config
copy "config/strategy.default.json"

# --- in-scope CLIs (only the live-recorder + db + backtestDb pipeline)
for f in args loadConfig dbMigrate dbCheck liveRecorder liveHealth liveAcceptance backtestDb; do
  copy "src/cli/$f.ts"
done

# --- data layer (only schema/time + the two adapters)
for f in schema time marketDataSource clickhouseDataSource; do
  copy "src/data/$f.ts"
done

# --- live-recorder: ALL files (already passes Test J banned-token grep)
while IFS= read -r f; do copy "$f"; done < <(find src/live-recorder -type f -name "*.ts" | sort)

# --- features: ALL files (pure, no Tardis coupling)
while IFS= read -r f; do copy "$f"; done < <(find src/features -type f -name "*.ts" | sort)

# --- replay: only the files needed by backtestDb / live recorder
# (marketReplayEngine.ts is Tardis-coupled; exclude it)
for f in orderBook dataQuality snapshotBuilder; do
  copy "src/replay/$f.ts"
done

# --- strategy: exclude sampleRunnerCore + validateTardisCore (Tardis-coupled, unused by backtestDb)
for f in probabilityBaseline targetChecker types uniqueMoveClustering zoneDetector zoneStateMachine; do
  copy "src/strategy/$f.ts"
done

# --- reports: exclude sampleRunReport + validateTardisReport (transitively pull Tardis)
for f in csvWriter jsonWriter markdownReport reportWriter; do
  copy "src/reports/$f.ts"
done

# --- tests requested explicitly
copy "tests/binanceLiveRecorder.test.ts"
copy "tests/liveAcceptance.test.ts"

# Confirm tree built
find "$DEST" -type f | sort
