// `npm run live:health` — point-in-time recorder health snapshot.
// Pulls recent counts from ClickHouse and prints them.
import { clickhouseFromEnv } from "../live-recorder/clickhouseClient.js";

interface CountRow { c: number | string; }
interface LastRow { ts: string; }
interface HealthRow {
  ts: string;
  symbol: string;
  status: string;
  ws_connected: number;
  sequence_ok: number;
  depth_events_per_sec: number;
  trades_per_sec: number;
  reconnect_count: number;
  sequence_gap_count: number;
  db_queue_size: number;
  spool_queue_size: number;
  notes: string;
}

async function main(): Promise<void> {
  const ch = clickhouseFromEnv();
  const ok = await ch.ping();
  if (!ok) {
    console.error("[live:health] ClickHouse not reachable.");
    process.exit(2);
  }
  console.log(`[live:health] ${new Date().toISOString()}`);

  const dCount1m = await ch.query<CountRow>(
    `SELECT count() AS c FROM raw_depth_events WHERE event_time >= now() - INTERVAL 1 MINUTE`
  );
  const dCount5m = await ch.query<CountRow>(
    `SELECT count() AS c FROM raw_depth_events WHERE event_time >= now() - INTERVAL 5 MINUTE`
  );
  const tCount1m = await ch.query<CountRow>(
    `SELECT count() AS c FROM trades WHERE event_time >= now() - INTERVAL 1 MINUTE`
  );
  const tCount5m = await ch.query<CountRow>(
    `SELECT count() AS c FROM trades WHERE event_time >= now() - INTERVAL 5 MINUTE`
  );
  const lastDepth = await ch.query<LastRow>(`SELECT toString(max(event_time)) AS ts FROM raw_depth_events`);
  const lastTrade = await ch.query<LastRow>(`SELECT toString(max(event_time)) AS ts FROM trades`);
  const recentHealth = await ch.query<HealthRow>(
    `SELECT toString(ts) AS ts, symbol, status, ws_connected, sequence_ok,
            depth_events_per_sec, trades_per_sec, reconnect_count,
            sequence_gap_count, db_queue_size, spool_queue_size, notes
     FROM recorder_health
     ORDER BY ts DESC
     LIMIT 8`
  );

  console.log(`  depth events  1m=${dCount1m[0]?.c ?? 0}  5m=${dCount5m[0]?.c ?? 0}  last=${lastDepth[0]?.ts ?? "-"}`);
  console.log(`  trade events  1m=${tCount1m[0]?.c ?? 0}  5m=${tCount5m[0]?.c ?? 0}  last=${lastTrade[0]?.ts ?? "-"}`);
  console.log(`  recent recorder_health (latest first):`);
  if (recentHealth.length === 0) {
    console.log(`    (no rows yet — recorder may not have emitted health samples)`);
  } else {
    for (const h of recentHealth) {
      console.log(
        `    ${h.ts} ${h.symbol.padEnd(10)} ${h.status.padEnd(9)} ws=${h.ws_connected} seq=${h.sequence_ok} ` +
          `depth/s=${Number(h.depth_events_per_sec).toFixed(1)} trades/s=${Number(h.trades_per_sec).toFixed(2)} ` +
          `gaps=${h.sequence_gap_count} reconnects=${h.reconnect_count} queued=${h.db_queue_size} spool=${h.spool_queue_size} ${h.notes}`
      );
    }
  }
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
