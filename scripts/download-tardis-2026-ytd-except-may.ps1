# Tardis YTD-2026 downloader (Jan-Apr only, May explicitly excluded).
#
# Layout:
#   data\tardis\binance-futures\BTCUSDT\{date}\{dataType}.csv.gz
#
# 200 -> OK, 404 -> SKIP, other failure -> ERROR.
# Existing files (size > 1KB) are kept and counted as EXISTS.
#
# Final summary: downloaded / existing / skipped / failed.

param(
  [string]$Exchange = "binance-futures",
  [string]$Symbol   = "BTCUSDT",
  [string]$OutRoot  = "data/tardis"
)

$ErrorActionPreference = "Stop"

# Only Jan-Apr 2026. May is current month and is intentionally excluded.
$Dates = @("2026-01-01","2026-02-01","2026-03-01","2026-04-01")
$DataTypes = @("incremental_book_L2","trades","derivative_ticker","book_ticker","liquidations")
$BaseUrl = "https://datasets.tardis.dev/v1"

$Headers = @{}
if ($env:TARDIS_API_KEY) {
  $Headers["Authorization"] = "Bearer $env:TARDIS_API_KEY"
  Write-Host "Using TARDIS_API_KEY from environment."
} else {
  Write-Host "No TARDIS_API_KEY found. Using free first-day-of-month datasets."
}

$Counts = @{ downloaded = 0; existing = 0; skipped = 0; failed = 0 }

function Download-One($Url, $OutFile) {
  if (Test-Path $OutFile) {
    $size = (Get-Item $OutFile).Length
    if ($size -gt 1000) {
      Write-Host "EXISTS $OutFile ($size bytes)"
      $Counts.existing += 1
      return
    }
  }

  $dir = Split-Path -Parent $OutFile
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

  Write-Host "GET $Url"
  try {
    $resp = Invoke-WebRequest -Uri $Url -OutFile $OutFile -Headers $Headers -ErrorAction Stop -PassThru
    $size = (Get-Item $OutFile).Length
    Write-Host "OK $OutFile ($size bytes)"
    $Counts.downloaded += 1
  } catch {
    if (Test-Path $OutFile) { Remove-Item $OutFile -Force }
    $status = $null
    try { $status = [int]$_.Exception.Response.StatusCode } catch {}
    if ($status -eq 404) {
      Write-Host "SKIP HTTP 404 $Url"
      $Counts.skipped += 1
    } elseif ($status) {
      Write-Host "ERROR HTTP $status $Url"
      $Counts.failed += 1
    } else {
      Write-Host "ERROR $Url"
      Write-Host $_.Exception.Message
      $Counts.failed += 1
    }
  }
}

foreach ($Date in $Dates) {
  $Yyyy = $Date.Substring(0,4)
  $Mm   = $Date.Substring(5,2)
  $Dd   = $Date.Substring(8,2)
  $DateDir = Join-Path $OutRoot (Join-Path $Exchange (Join-Path $Symbol $Date))
  if (!(Test-Path $DateDir)) { New-Item -ItemType Directory -Force -Path $DateDir | Out-Null }

  foreach ($DataType in $DataTypes) {
    $Url = "{0}/{1}/{2}/{3}/{4}/{5}/{6}.csv.gz" -f $BaseUrl, $Exchange, $DataType, $Yyyy, $Mm, $Dd, $Symbol
    $OutFile = Join-Path $DateDir ("{0}.csv.gz" -f $DataType)
    Download-One $Url $OutFile
  }
}

Write-Host ""
Write-Host "==== SUMMARY ===="
Write-Host ("downloaded : {0}" -f $Counts.downloaded)
Write-Host ("existing   : {0}" -f $Counts.existing)
Write-Host ("skipped    : {0}   (404 - likely missing optional types)" -f $Counts.skipped)
Write-Host ("failed     : {0}    (other HTTP / network errors)" -f $Counts.failed)
Write-Host ""
Write-Host "Output root: $OutRoot/$Exchange/$Symbol/"
Write-Host "Note: incremental_book_L2 and trades are mandatory; the others are optional."
