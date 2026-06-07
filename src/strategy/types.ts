// Shared types and config interfaces for the Orderflow L2 research module.
// Kept in strategy/types.ts because zone/target structures depend on them and
// most other layers import them.

export type Side = "bid" | "ask";
export type TradeSide = "buy" | "sell"; // taker side from Tardis

export type ZoneDirection = "LONG" | "SHORT";
export type ZoneType = "ACCUMULATION" | "DISTRIBUTION";
export type ZoneStatus =
  | "CANDIDATE"
  | "CONFIRMED"
  | "TRIGGERED"
  | "RESOLVED_REACHED"
  | "RESOLVED_FAILED"
  | "EXPIRED"
  | "INVALIDATED"
  | "NO_TRIGGER";

export type TargetOutcome =
  | "reached"
  | "failed_by_timeout"
  | "invalid_data"
  | "no_trigger"
  | "invalidated_before_trigger";

export interface DepthBuckets {
  // Map: pct (e.g. "0.05") -> { bid: number, ask: number }
  [pctKey: string]: { bid: number; ask: number };
}

export interface BookState {
  ts: number; // ms
  bestBid: number | null;
  bestAsk: number | null;
  mid: number | null;
  spread: number | null;
  spreadPct: number | null;
  totalBid: number;
  totalAsk: number;
  depthBuckets: DepthBuckets;
  bidLevels: number; // number of price levels on bid side
  askLevels: number;
  qualityFlags: string[]; // e.g. ['CROSSED','GAP','EMPTY']
}

export interface TradeAggWindow {
  windowSec: number;
  buyVolume: number;
  sellVolume: number;
  delta: number;
  trades: number;
  vwap: number | null;
  highPrice: number | null;
  lowPrice: number | null;
}

export interface TradeAgg {
  ts: number;
  windows: { [secKey: string]: TradeAggWindow };
}

export interface FeatureRow {
  ts: number;
  book: BookState;
  trades: TradeAgg;
  imbalance: { [pctKey: string]: number }; // (bid-ask)/(bid+ask)
  pressure: {
    buyPressure: number; // 0..1, normalised
    sellPressure: number; // 0..1
    aggressiveFlowRatio: number; // buy/(buy+sell)
  };
  absorption: {
    buyAbsorptionScore: number; // 0..1 — sells absorbed by bids
    sellAbsorptionScore: number; // 0..1 — buys absorbed by asks
    priceProgressDownPct: number; // pct over recent window
    priceProgressUpPct: number;
  };
  liquidityVoid: {
    voidUp2PctScore: number; // 0..1 (higher = more void)
    voidDown2PctScore: number;
    askVolUpTo2Pct: number;
    bidVolDownTo2Pct: number;
  };
  liquidityEvents: {
    bidAddRate: number; // levels added per second
    bidRemoveRate: number;
    askAddRate: number;
    askRemoveRate: number;
    bidRefillScore: number; // 0..1
    askRefillScore: number;
    bidThinningScore: number;
    askThinningScore: number;
  };
  volatility: {
    realizedVolPct: number; // % move in window
    range1mPct: number;
  };
  rangeCompression: boolean;
  forcedFlow?: { liqBuyVol: number; liqSellVol: number };
  qualityFlags: string[];
}

export interface ZoneReason {
  stage: "candidate" | "confirmed" | "trigger" | "invalidate" | "expire";
  ts: number;
  conditions: { [k: string]: number | boolean | string | null };
  notes?: string;
}

export interface ZoneTargetMetrics {
  horizon: string;
  outcome: TargetOutcome;
  reachedAt?: number; // ms
  timeToTargetMin?: number;
  mfePct?: number;
  maePct?: number;
  maxDrawdownBeforeTargetPct?: number;
  endPrice?: number;
  endTs?: number;
}

export interface Zone {
  id: string;
  symbol: string;
  date: string;
  direction: ZoneDirection;
  zoneType: ZoneType;
  status: ZoneStatus;
  startTs: number;
  confirmedTs?: number;
  triggerTs?: number;
  resolvedTs?: number;
  zoneLow: number;
  zoneHigh: number;
  triggerPrice?: number;
  referencePrice?: number;
  targetPrice?: number;
  // scores at confirmation/trigger time
  scores: {
    absorptionScore: number;
    liquidityVoidScore: number;
    ofiScore: number;
    triggerScore?: number;
    refillScore?: number;
  };
  qualityFlags: string[];
  // results: keyed by horizon string
  targets: { [horizon: string]: ZoneTargetMetrics };
  // human-readable reason chain
  reasons: ZoneReason[];
  /**
   * Move-clustering accounting fields — populated by the post-processing
   * `applyMoveClustering()` step. Only RESOLVED_REACHED zones receive a
   * `uniqueMoveId`; all other statuses leave these fields unset.
   *
   * Two reached zones share a uniqueMoveId when they are the same direction
   * and their `[triggerTs, reachedAt]` time windows overlap or are within
   * `moveClusterGapMinutes` of each other.
   */
  uniqueMoveId?: number;
  moveClusterSize?: number;
  isPrimaryMoveZone?: boolean;
  duplicateMoveCredit?: boolean;
}

// ----- Strategy configuration -----

export interface StrategyConfig {
  symbol: string;
  exchange: string;
  targetPct: number;
  featureIntervalSec: number;
  snapshotDepthLevels: number;
  depthPctBuckets: number[];
  tradeWindowsSec: number[];
  zone: {
    minCandidateDurationMin: number;
    minConfirmedDurationMin: number;
    maxFormationDurationMin: number;
    minAbsorptionCycles: number;
    maxNoProgressPct: number;
    minAbsorptionScore: number;
    minLiquidityVoidScore: number;
    minTriggerScore: number;
    candidate: {
      minSidedPressure: number;
      minRefillScore: number;
      rangeCompressionPct: number;
    };
    confirmed: {
      minDefendedPersistenceSec: number;
      minOppositeThinningScore: number;
    };
    trigger: {
      minBreakDistancePct: number;
      minAggressiveFlowMultiplier: number;
    };
  };
  targetChecker: {
    horizons: string[];
    referencePrice: "triggerPrice" | "zoneMid" | "zoneBoundary" | "firstPriceAfterTrigger";
  };
  quality: {
    maxSpreadPct: number;
    maxGapMs: number;
    requireBestBidAsk: boolean;
  };
  replay: {
    warmupSeconds: number;
    logEveryRows: number;
  };
  /**
   * Deduplication / accounting fix. NOT a tune of entry thresholds — this
   * only controls whether the detector is allowed to open a *second*
   * same-direction zone over the same active price band, and whether a
   * cooldown applies after a zone resolves.
   *
   * Enable to suppress same-direction zones that overlap the price band of
   * an existing CANDIDATE / CONFIRMED / TRIGGERED zone, or one that resolved
   * within `cooldownMinutesAfterResolve`. Set `enabled=false` to restore
   * the legacy behaviour (each candidate fires regardless of pre-existing
   * zones).
   */
  deduplication?: DeduplicationConfig;

  /**
   * Unique-move clustering. Pure post-processing accounting fix that runs
   * AFTER target checking. Groups RESOLVED_REACHED zones whose
   * `[triggerTs, reachedAt]` windows overlap (or are within
   * `moveClusterGapMinutes`) into a single `uniqueMoveId`. The earliest
   * zone in each cluster is marked `isPrimaryMoveZone=true`; the rest are
   * `duplicateMoveCredit=true`.
   *
   * Used to compute the **honest** hit rate — `uniqueMoveAdjustedHitRate =
   * uniqueReachedMoves / triggered` — alongside the diagnostic raw hit
   * rate. Does NOT change which zones are detected, triggered or marked
   * REACHED; failed / no_trigger / invalidated zones are untouched.
   */
  moveClustering?: MoveClusteringConfig;
}

export interface DeduplicationConfig {
  enabled: boolean;
  sameDirectionOverlapSuppression: boolean;
  cooldownMinutesAfterResolve: number;
  /** Required overlap fraction (0..1) of the smaller zone's price height
   * before a new candidate is suppressed. 0.25 = 25%. */
  priceOverlapMinPct: number;
}

export interface MoveClusteringConfig {
  enabled: boolean;
  /** When true, group reached zones into unique moves. */
  clusterReachedZones: boolean;
  /** Time gap threshold in minutes — two reached zones merge into one move
   * if the next one's triggerTs is within this gap of the prior cluster's
   * latest reachedAt. */
  moveClusterGapMinutes: number;
  /** When true, only zones of the same direction can share a move. */
  sameDirectionOnly: boolean;
}

export interface SuppressionRecord {
  ts: number;
  direction: ZoneDirection;
  /** Initial proposed price band of the would-be candidate. */
  proposedLow: number;
  proposedHigh: number;
  suppressedByZoneId: string;
  /**
   * "active_open" — duplicate of an open CANDIDATE/CONFIRMED zone.
   * "active_triggered" — duplicate of an already-triggered zone whose
   *     target hasn't yet resolved.
   * "cooldown" — duplicate within `cooldownMinutesAfterResolve` after a
   *     zone of the same direction terminated.
   */
  reason:
    | "active_open"
    | "active_triggered"
    | "cooldown";
  /** Overlap as a fraction of the smaller zone's height. */
  overlapPct: number;
}
