// Crude volatility regime tracker driven by mid-price samples on the
// feature grid. Provides realised vol over the last N seconds (% std) and a
// 1-minute high-low range %.

interface MidPoint {
  ts: number;
  mid: number;
}

export class VolatilityTracker {
  private points: MidPoint[] = [];
  private readonly windowMs = 60_000;
  private readonly volWindowMs = 300_000; // 5 min realized vol

  push(ts: number, mid: number | null): void {
    if (mid === null) return;
    this.points.push({ ts, mid });
    const cutoff = ts - this.volWindowMs;
    let i = 0;
    while (i < this.points.length && this.points[i].ts < cutoff) i++;
    if (i > 0) this.points = this.points.slice(i);
  }

  realizedVolPct(): number {
    if (this.points.length < 2) return 0;
    const rets: number[] = [];
    for (let i = 1; i < this.points.length; i++) {
      const a = this.points[i - 1].mid;
      const b = this.points[i].mid;
      if (a > 0 && b > 0) rets.push(Math.log(b / a));
    }
    if (rets.length === 0) return 0;
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    let sq = 0;
    for (const r of rets) sq += (r - mean) ** 2;
    const std = Math.sqrt(sq / rets.length);
    return std * 100;
  }

  range1mPct(ts: number): number {
    const cutoff = ts - this.windowMs;
    let lo = +Infinity;
    let hi = -Infinity;
    for (const p of this.points) {
      if (p.ts < cutoff) continue;
      if (p.mid < lo) lo = p.mid;
      if (p.mid > hi) hi = p.mid;
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo <= 0) return 0;
    return ((hi - lo) / lo) * 100;
  }

  /** Range compressed = current 1m range below threshold (in pct). */
  isRangeCompressed(ts: number, thresholdPct: number): boolean {
    return this.range1mPct(ts) <= thresholdPct;
  }
}
