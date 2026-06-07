// Parse the --duration-min flag (and friends) to a millisecond integer.
// Accepts:
//   "10"      -> 10 minutes (the default unit when bare number)
//   "10min"   -> 10 minutes
//   "10m"     -> 10 minutes
//   "1h"      -> 60 minutes
//   "30s"     -> 30 seconds
// Returns ms.

export class DurationParseError extends Error {
  constructor(input: string) {
    super(`Bad duration: "${input}". Accepts e.g. "10", "10min", "1h", "30s".`);
    this.name = "DurationParseError";
  }
}

export function parseDurationMinutesArg(input: string | number | undefined, fallbackMin = 10): number {
  if (input === undefined || input === null || input === "") return fallbackMin * 60_000;
  if (typeof input === "number") {
    if (!Number.isFinite(input) || input <= 0) throw new DurationParseError(String(input));
    return Math.round(input * 60_000);
  }
  const s = String(input).trim().toLowerCase();
  // bare number → minutes
  const bare = /^(\d+(?:\.\d+)?)$/.exec(s);
  if (bare) {
    const n = Number(bare[1]);
    if (!Number.isFinite(n) || n <= 0) throw new DurationParseError(s);
    return Math.round(n * 60_000);
  }
  const m = /^(\d+(?:\.\d+)?)\s*(s|sec|secs|m|min|mins|h|hr|hour|hours)$/.exec(s);
  if (!m) throw new DurationParseError(s);
  const n = Number(m[1]);
  if (!Number.isFinite(n) || n <= 0) throw new DurationParseError(s);
  const unit = m[2];
  if (unit === "s" || unit === "sec" || unit === "secs") return Math.round(n * 1000);
  if (unit === "m" || unit === "min" || unit === "mins") return Math.round(n * 60_000);
  if (unit === "h" || unit === "hr" || unit === "hour" || unit === "hours") return Math.round(n * 3_600_000);
  throw new DurationParseError(s);
}
