// `npm run live:recorder` — start the Binance USDS-M Futures public market-
// data recorder. Reads configuration from environment variables (see
// `.env.example`). Public-only: no API key, no order endpoints.

import { clickhouseFromEnv } from "../live-recorder/clickhouseClient.js";
import { RecorderService } from "../live-recorder/recorderService.js";

async function main(): Promise<void> {
  const ch = clickhouseFromEnv();
  const symbols = (process.env.SYMBOLS ?? "BTCUSDT").split(",").map((s) => s.trim()).filter(Boolean);
  const exchange = process.env.EXCHANGE ?? "binance-futures";
  const depthSpeed = (process.env.DEPTH_STREAM_SPEED ?? "100ms") as "100ms" | "250ms" | "500ms" | "1000ms" | "default";
  const snapshotIntervalMs = Number(process.env.SNAPSHOT_INTERVAL_MS ?? "1000");
  const spoolDir = process.env.RAW_SPOOL_DIR ?? "./data/live-spool";
  console.log(
    `[live:recorder] exchange=${exchange} symbols=${symbols.join(",")} depth=${depthSpeed} snapshotEveryMs=${snapshotIntervalMs} spool=${spoolDir}`
  );
  const ok = await ch.ping().catch(() => false);
  if (!ok) {
    console.warn(`[live:recorder] WARN ClickHouse ping failed at ${process.env.CLICKHOUSE_URL ?? "http://localhost:8123"} — events will spool to ${spoolDir}.`);
  }
  const svc = new RecorderService({
    ch,
    exchange,
    symbols,
    depthSpeed,
    snapshotIntervalMs,
    spoolDir,
  });
  await svc.start();
  // Graceful shutdown.
  const stop = async () => {
    console.log("[live:recorder] shutting down ...");
    await svc.stop();
    process.exit(0);
  };
  process.on("SIGINT", () => void stop());
  process.on("SIGTERM", () => void stop());
}

import { pathToFileURL } from "node:url";
const __isMain =
  process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;
if (__isMain) {
  main().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
