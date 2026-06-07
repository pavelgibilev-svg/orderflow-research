// Pure helper that builds the argv-equivalent argument list passed to the
// runBacktestDb() function from inside the acceptance orchestrator.
// Exposed as a function so tests can verify the args without invoking the
// actual backtest.

export interface BacktestInvocationOpts {
  symbol: string;
  exchange: string;
  fromMs: number;
  toMs: number;
  targetPct: number;
  horizons: string[];
  outDir: string;
}

export interface BacktestInvocation {
  symbol: string;
  exchange: string;
  fromMs: number;
  toMs: number;
  targetPct: number;
  horizons: string[];
  outDir: string;
}

export function buildBacktestInvocation(opts: BacktestInvocationOpts): BacktestInvocation {
  if (!opts.symbol) throw new Error("symbol required");
  if (!opts.exchange) throw new Error("exchange required");
  if (!Number.isFinite(opts.fromMs) || !Number.isFinite(opts.toMs)) throw new Error("from/to must be finite");
  if (opts.toMs <= opts.fromMs) throw new Error("to must be > from");
  if (!Array.isArray(opts.horizons) || opts.horizons.length === 0) throw new Error("horizons required");
  return {
    symbol: opts.symbol,
    exchange: opts.exchange,
    fromMs: opts.fromMs,
    toMs: opts.toMs,
    targetPct: opts.targetPct,
    horizons: [...opts.horizons],
    outDir: opts.outDir,
  };
}

export function describeBacktestInvocation(inv: BacktestInvocation): string {
  return `npm run backtest:db -- --symbol ${inv.symbol} --exchange ${inv.exchange} --from ${new Date(inv.fromMs).toISOString()} --to ${new Date(inv.toMs).toISOString()} --target-pct ${inv.targetPct} --horizons ${inv.horizons.join(",")}`;
}
