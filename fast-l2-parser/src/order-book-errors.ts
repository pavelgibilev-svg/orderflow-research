// Order-book error types. All are critical — the book builder never tries to
// auto-repair; it surfaces a typed error with enough context to debug the feed.

/**
 * Thrown only AFTER a full timestamp batch has been applied, if the top of book
 * is crossed (bestBid >= bestAsk). Never thrown mid-batch.
 */
export class CrossedBookError extends Error {
  constructor(
    public readonly timestampNs: number,
    public readonly sequence: number,
    public readonly bestBid: number,
    public readonly bestAsk: number,
    public readonly bidDepth: number,
    public readonly askDepth: number
  ) {
    super(
      `Crossed book detected after timestamp batch: bestBid=${bestBid} >= bestAsk=${bestAsk} ` +
        `at timestampNs=${timestampNs}, sequence=${sequence}, bidDepth=${bidDepth}, askDepth=${askDepth}`
    );
    this.name = "CrossedBookError";
    // Keep `instanceof` correct even if compiled/down-levelled.
    Object.setPrototypeOf(this, CrossedBookError.prototype);
  }
}

/** Thrown on a non-monotonic incremental sequence when `validateSequence` is on. */
export class SequenceGapError extends Error {
  constructor(
    public readonly timestampNs: number,
    public readonly expectedSequence: number,
    public readonly actualSequence: number,
    public readonly lastSequence: number
  ) {
    super(
      `Sequence gap detected: expected sequence=${expectedSequence}, actual sequence=${actualSequence}, ` +
        `lastSequence=${lastSequence}, timestampNs=${timestampNs}`
    );
    this.name = "SequenceGapError";
    Object.setPrototypeOf(this, SequenceGapError.prototype);
  }
}

/** Thrown for structurally invalid updates: bad side / price / size. */
export class InvalidBookUpdateError extends Error {
  constructor(
    message: string,
    public readonly field: "side" | "price" | "size",
    public readonly value: unknown
  ) {
    super(`Invalid book update (${field}=${String(value)}): ${message}`);
    this.name = "InvalidBookUpdateError";
    Object.setPrototypeOf(this, InvalidBookUpdateError.prototype);
  }
}
