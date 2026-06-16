// Byte-level number/side parsers. No intermediate strings, no Number()/parseFloat()
// in the hot loop. Each function reads raw bytes from a Buffer slice [start, end).
//
// All functions assume ASCII input (digits 0x30-0x39, '.', '-', '+'), which is
// always true for Tardis / exchange CSV market data.

import type { Side } from "./types.js";

const ZERO = 0x30; // '0'
const DOT = 0x2e; // '.'
const MINUS = 0x2d; // '-'
const PLUS = 0x2b; // '+'
const LOWER_A = 0x61; // 'a'
const UPPER_A = 0x41; // 'A'
const LOWER_B = 0x62; // 'b'
const UPPER_B = 0x42; // 'B'

/**
 * Parse an unsigned integer directly from bytes, returning a JS `number`.
 *
 * Trade-off (number vs bigint):
 *   - `number` is a float64 with 53 bits of integer precision (max safe integer
 *     = 9_007_199_254_740_991 ≈ 9.0e15). It is fast and allocation-free.
 *   - MICROSECOND timestamps (~1.77e15 today) fit safely in a number.
 *   - NANOSECOND timestamps (~1.77e18) DO NOT fit — the lowest ~3 digits get
 *     rounded. Ordering is preserved and millisecond precision is intact, but
 *     exact nanoseconds are lost. For exact ns use `parseBigIntFromBuffer`,
 *     which is precise but allocates a heap BigInt per row (GC pressure) and is
 *     several times slower. For throughput benchmarks, `number` is preferred.
 */
export function parseUnsignedIntFromBuffer(buf: Buffer, start: number, end: number): number {
  let n = 0;
  for (let i = start; i < end; i++) {
    n = n * 10 + (buf[i] - ZERO);
  }
  return n;
}

/**
 * Exact integer parse into a BigInt (use only when you truly need nanosecond
 * precision). Allocates a BigInt per call — keep it OUT of the benchmark path.
 */
export function parseBigIntFromBuffer(buf: Buffer, start: number, end: number): bigint {
  let n = 0n;
  for (let i = start; i < end; i++) {
    n = n * 10n + BigInt(buf[i] - ZERO);
  }
  return n;
}

/**
 * Parse a decimal (e.g. "43120.5", "0.001", "100", "-1.25") into a `number`,
 * byte by byte. Handles an optional leading sign and a single decimal point.
 *
 * Limitation: scientific notation ("1e-3") is NOT handled — exchange L2 dumps
 * use plain decimals. If a feed ever emits exponents, route those rows through
 * a slow-path `parseFloat(buf.toString(...))` fallback.
 */
export function parseDecimalFromBuffer(buf: Buffer, start: number, end: number): number {
  let i = start;
  let neg = false;
  const first = buf[i];
  if (first === MINUS) {
    neg = true;
    i++;
  } else if (first === PLUS) {
    i++;
  }

  let intPart = 0;
  for (; i < end; i++) {
    const c = buf[i];
    if (c === DOT) {
      i++;
      break;
    }
    intPart = intPart * 10 + (c - ZERO);
  }

  // Fractional digits (if any). `scale` tracks 10^(#fractional digits).
  let frac = 0;
  let scale = 1;
  for (; i < end; i++) {
    frac = frac * 10 + (buf[i] - ZERO);
    scale *= 10;
  }

  const v = scale === 1 ? intPart : intPart + frac / scale;
  return neg ? -v : v;
}

/**
 * Map a side token to a number: bid -> 0, ask -> 1. Decided on the first byte
 * only (cheapest possible: 'b'/'a' differ at index 0). Unknown tokens throw a
 * clear error rather than being silently mislabelled.
 */
export function parseSideFromBuffer(buf: Buffer, start: number, end: number): Side {
  const c = buf[start];
  if (c === LOWER_B || c === UPPER_B) return 0; // bid
  if (c === LOWER_A || c === UPPER_A) return 1; // ask
  throw new Error(`parseSideFromBuffer: unknown side token "${buf.toString("utf8", start, end)}"`);
}
