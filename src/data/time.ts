// Time helpers. Tardis CSVs use microseconds since epoch (UTC) in
// `timestamp` and `local_timestamp`. Internally we work in milliseconds
// (number) — Date.getTime()-style — to avoid BigInt overhead.

export function microsToMs(usText: string | number): number {
  if (typeof usText === "number") return Math.floor(usText / 1000);
  // Avoid Number() precision loss for 16-digit µs by integer arithmetic on string.
  // Length is typically 16 (µs since epoch fits 64-bit but JS number is safe up to 2^53).
  // Safe up to ~year 2255 in milliseconds, so we can use Number() but still divide.
  const n = Number(usText);
  if (!Number.isFinite(n)) return NaN;
  return Math.floor(n / 1000);
}

export function parseHorizon(horizon: string): number {
  // Returns horizon in milliseconds.
  const m = horizon.match(/^(\d+(?:\.\d+)?)\s*([smhd])$/i);
  if (!m) throw new Error(`Bad horizon: ${horizon}`);
  const v = parseFloat(m[1]);
  switch (m[2].toLowerCase()) {
    case "s":
      return Math.round(v * 1000);
    case "m":
      return Math.round(v * 60 * 1000);
    case "h":
      return Math.round(v * 3600 * 1000);
    case "d":
      return Math.round(v * 86400 * 1000);
  }
  throw new Error(`Bad horizon: ${horizon}`);
}

export function parseInterval(interval: string): number {
  // Returns ms. Accepts "100ms", "1s", "5s", "1m" etc.
  const m = interval.match(/^(\d+(?:\.\d+)?)\s*(ms|s|m|h)?$/i);
  if (!m) throw new Error(`Bad interval: ${interval}`);
  const v = parseFloat(m[1]);
  const unit = (m[2] || "s").toLowerCase();
  switch (unit) {
    case "ms":
      return Math.round(v);
    case "s":
      return Math.round(v * 1000);
    case "m":
      return Math.round(v * 60_000);
    case "h":
      return Math.round(v * 3_600_000);
  }
  throw new Error(`Bad interval: ${interval}`);
}

export function isoDateUtc(ts: number): string {
  return new Date(ts).toISOString();
}

export function dayBoundsUtc(date: string): { startMs: number; endMs: number } {
  // date format: YYYY-MM-DD
  const m = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) throw new Error(`Bad date: ${date}`);
  const start = Date.UTC(+m[1], +m[2] - 1, +m[3]);
  return { startMs: start, endMs: start + 86_400_000 };
}
