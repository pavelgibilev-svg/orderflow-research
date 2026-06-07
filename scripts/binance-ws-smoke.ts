// 60-second WS smoke test for Binance USDS-M Futures public market-data.
// Uses BinanceWsClient. Also taps the `raw` event to inventory every
// distinct event type the server delivers, so we can verify routing.

import { BinanceWsClient } from "../src/live-recorder/binanceWsClient.js";

interface RawCounters {
  byEventType: Record<string, number>;
  byStream: Record<string, number>;
  totalRaw: number;
}

const events: Record<string, number> = {
  depth: 0,
  trade: 0,
  bookTicker: 0,
  markPrice: 0,
  liquidation: 0,
};
const firstSeenAt: Record<string, number> = {};
const raw: RawCounters = { byEventType: {}, byStream: {}, totalRaw: 0 };
let errors = 0;
let reconnects = 0;

function note(kind: keyof typeof events): void {
  events[kind] += 1;
  if (firstSeenAt[kind] === undefined) firstSeenAt[kind] = Date.now();
}

const DURATION_MS = Number(process.env.SMOKE_DURATION_MS ?? "60000");
const SYMBOL = process.env.SMOKE_SYMBOL ?? "BTCUSDT";

const client = new BinanceWsClient({ symbols: [SYMBOL] });

client.on("depth", () => note("depth"));
client.on("trade", () => note("trade"));
client.on("bookTicker", () => note("bookTicker"));
client.on("markPrice", () => note("markPrice"));
client.on("liquidation", () => note("liquidation"));
client.on("error", (err: unknown) => { errors += 1; console.error("[error]", err); });
client.on("disconnect", () => { reconnects += 1; });
client.on("raw", (info: { stream: string; data: unknown }) => {
  raw.totalRaw += 1;
  const d = info.data as Record<string, unknown>;
  const e = (d?.["e"] as string | undefined) ?? "<no-e>";
  raw.byEventType[e] = (raw.byEventType[e] ?? 0) + 1;
  raw.byStream[info.stream] = (raw.byStream[info.stream] ?? 0) + 1;
});

const started = Date.now();
console.log(`[smoke] connecting to Binance USDS-M Futures public WS, symbol=${SYMBOL}, duration_ms=${DURATION_MS}`);
console.log(`[smoke] url=${client.getUrl()}`);
client.connect();

setTimeout(() => {
  const elapsed = (Date.now() - started) / 1000;
  const out = {
    symbol: SYMBOL,
    duration_seconds: Number(elapsed.toFixed(2)),
    events_received_via_typed_emitters: events,
    rate_per_second: Object.fromEntries(
      Object.entries(events).map(([k, n]) => [k, (n / elapsed).toFixed(2)]),
    ),
    first_event_offset_seconds: Object.fromEntries(
      Object.entries(firstSeenAt).map(([k, t]) => [k, ((t - started) / 1000).toFixed(2)]),
    ),
    raw_message_inventory: {
      total: raw.totalRaw,
      by_e_field: raw.byEventType,
      by_stream_suffix: Object.fromEntries(
        Object.entries(raw.byStream).map(([s, n]) => [s.split("@").slice(1).join("@") || "<root>", n]),
      ),
    },
    errors,
    reconnects,
    all_required_streams_received:
      events.depth > 0 && events.trade > 0 && events.bookTicker > 0 && events.markPrice > 0,
  };
  console.log(JSON.stringify(out, null, 2));
  client.close();
  setTimeout(() => process.exit(0), 200);
}, DURATION_MS);
