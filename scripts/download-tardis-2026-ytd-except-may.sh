#!/usr/bin/env bash
# Tardis YTD-2026 downloader (Jan-Apr only, May explicitly excluded).
#
# Layout:
#   data/tardis/binance-futures/BTCUSDT/{date}/{dataType}.csv.gz
#
# Per task: only Jan-Apr 2026 (May is current month, future months not yet on Tardis).
# Free first-day-of-month datasets are accessible without an API key.
#
# 200 -> OK, 404 -> SKIP, other failure -> ERROR.
# Existing files (size > 1KB) are kept and counted as EXISTS.
#
# Final summary: downloaded / existing / skipped / failed.

set -u

EXCHANGE="${EXCHANGE:-binance-futures}"
SYMBOL="${SYMBOL:-BTCUSDT}"
OUT_ROOT="${OUT_ROOT:-data/tardis}"
BASE_URL="https://datasets.tardis.dev/v1"

# Only Jan-Apr 2026. May is current month and is intentionally excluded.
DATES=("2026-01-01" "2026-02-01" "2026-03-01" "2026-04-01")
# Order matters: required first, then optional.
DATA_TYPES=("incremental_book_L2" "trades" "derivative_ticker" "book_ticker" "liquidations")

CURL_HEADERS=()
if [[ -n "${TARDIS_API_KEY:-}" ]]; then
  CURL_HEADERS=(-H "Authorization: Bearer ${TARDIS_API_KEY}")
  echo "Using TARDIS_API_KEY from environment."
else
  echo "No TARDIS_API_KEY found. Using free first-day-of-month datasets."
fi

DOWNLOADED=0
EXISTING=0
SKIPPED=0
FAILED=0

download_one() {
  local url="$1"
  local outfile="$2"

  if [[ -s "$outfile" ]]; then
    local size
    size=$(wc -c < "$outfile" | tr -d ' ')
    if [[ "$size" -gt 1000 ]]; then
      echo "EXISTS $outfile ($size bytes)"
      EXISTING=$((EXISTING+1))
      return 0
    fi
  fi

  mkdir -p "$(dirname "$outfile")"
  echo "GET $url"

  local http_code
  http_code=$(curl -sS -L -o "$outfile" -w "%{http_code}" "${CURL_HEADERS[@]}" "$url" || echo "000")

  if [[ "$http_code" == "200" ]]; then
    local size
    size=$(wc -c < "$outfile" | tr -d ' ')
    echo "OK $outfile ($size bytes)"
    DOWNLOADED=$((DOWNLOADED+1))
  elif [[ "$http_code" == "404" ]]; then
    rm -f "$outfile"
    echo "SKIP HTTP 404 $url"
    SKIPPED=$((SKIPPED+1))
  else
    rm -f "$outfile"
    echo "ERROR HTTP $http_code $url"
    FAILED=$((FAILED+1))
  fi
}

for date in "${DATES[@]}"; do
  yyyy="${date:0:4}"
  mm="${date:5:2}"
  dd="${date:8:2}"
  date_dir="${OUT_ROOT}/${EXCHANGE}/${SYMBOL}/${date}"
  mkdir -p "$date_dir"

  for data_type in "${DATA_TYPES[@]}"; do
    url="${BASE_URL}/${EXCHANGE}/${data_type}/${yyyy}/${mm}/${dd}/${SYMBOL}.csv.gz"
    outfile="${date_dir}/${data_type}.csv.gz"
    download_one "$url" "$outfile"
  done
done

echo
echo "==== SUMMARY ===="
echo "downloaded : ${DOWNLOADED}"
echo "existing   : ${EXISTING}"
echo "skipped    : ${SKIPPED}   (404 — likely missing optional types)"
echo "failed     : ${FAILED}    (other HTTP / network errors)"
echo
echo "Output root: ${OUT_ROOT}/${EXCHANGE}/${SYMBOL}/"
echo "Note: incremental_book_L2 and trades are mandatory; the others are optional."
