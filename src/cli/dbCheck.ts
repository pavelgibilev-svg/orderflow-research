// `npm run db:check` — verify ClickHouse reachable and recorder tables exist.
import { clickhouseFromEnv } from "../live-recorder/clickhouseClient.js";
import { ALL_TABLES } from "../live-recorder/schema.js";

interface SystemTableRow { name: string; }

async function main(): Promise<void> {
  const ch = clickhouseFromEnv();
  const db = process.env.CLICKHOUSE_DB ?? "orderflow";
  console.log(`[db:check] url=${process.env.CLICKHOUSE_URL ?? "http://localhost:8123"} db=${db}`);
  const ok = await ch.ping();
  console.log(`[db:check] ping: ${ok ? "ok" : "FAILED"}`);
  if (!ok) process.exit(2);
  const rows = await ch.query<SystemTableRow>(
    `SELECT name FROM system.tables WHERE database = '${db.replace(/'/g, "''")}' ORDER BY name`
  );
  const present = new Set(rows.map((r) => r.name));
  console.log(`[db:check] tables in "${db}":`);
  for (const t of ALL_TABLES) {
    console.log(`  ${present.has(t) ? "✓" : "✗"} ${t}`);
  }
  const missing = ALL_TABLES.filter((t) => !present.has(t));
  if (missing.length > 0) {
    console.error(`[db:check] missing: ${missing.join(", ")} — run \`npm run db:migrate\` first.`);
    process.exit(3);
  }
  console.log(`[db:check] all required tables present.`);
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
