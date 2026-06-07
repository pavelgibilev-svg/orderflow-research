// `npm run db:migrate` — apply ClickHouse schema. Idempotent.
import { clickhouseFromEnv } from "../live-recorder/clickhouseClient.js";
import { allMigrationSql, ALL_TABLES } from "../live-recorder/schema.js";

async function main(): Promise<void> {
  const ch = clickhouseFromEnv();
  const db = process.env.CLICKHOUSE_DB ?? "orderflow";
  console.log(`[db:migrate] target=${process.env.CLICKHOUSE_URL ?? "http://localhost:8123"} database=${db}`);
  const ok = await ch.ping();
  if (!ok) {
    console.error(`[db:migrate] ClickHouse ping failed; check the server is up and CLICKHOUSE_URL is correct.`);
    process.exit(2);
  }
  for (const sql of allMigrationSql(db)) {
    const head = sql.split("\n")[0]?.replace(/\s+/g, " ").trim();
    process.stdout.write(`  applying: ${head} ... `);
    await ch.exec(sql);
    process.stdout.write("ok\n");
  }
  console.log(`[db:migrate] ${ALL_TABLES.length} tables ready in database "${db}".`);
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
