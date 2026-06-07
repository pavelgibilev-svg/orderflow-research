// Tiny dependency-free ClickHouse HTTP client.
//
// Why not @clickhouse/client? Adding a runtime dep means npm install must
// resolve it; the project deliberately keeps runtime deps zero. ClickHouse
// over HTTP supports everything we need: SELECT with FORMAT, INSERT FORMAT
// JSONEachRow, DDL via plain query, and basic auth via username/password.
//
// All inserts go through `insertJSONEachRow(table, rows)` which is the one
// hot path. Queries are exposed via `query<T>(sql, opts)` which returns
// rows as parsed JSON objects (FORMAT JSONEachRow output).

import * as http from "node:http";
import * as https from "node:https";
import { URL } from "node:url";
import { Buffer } from "node:buffer";

export interface ClickHouseClientOptions {
  url: string;
  database?: string;
  username?: string;
  password?: string;
  /** Per-request timeout in ms. */
  timeoutMs?: number;
}

export interface ClickHouseError extends Error {
  status?: number;
  body?: string;
}

const DEFAULT_TIMEOUT_MS = 30_000;

/** Minimal ClickHouse client. Statements use HTTP /?query=... ; data goes in body. */
export class ClickHouseClient {
  private readonly base: URL;
  private readonly username?: string;
  private readonly password?: string;
  private readonly database: string;
  private readonly timeoutMs: number;

  constructor(opts: ClickHouseClientOptions) {
    this.base = new URL(opts.url);
    this.username = opts.username;
    this.password = opts.password;
    this.database = opts.database ?? "default";
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  /** Health-ping. Returns true on HTTP 200. */
  async ping(): Promise<boolean> {
    try {
      const r = await this.rawGet("/ping");
      return r.status === 200;
    } catch {
      return false;
    }
  }

  /** Execute DDL or any non-row-returning statement. */
  async exec(sql: string): Promise<void> {
    await this.rawPost("/", sql);
  }

  /** Run a SELECT and return rows. The SQL must end with `FORMAT JSONEachRow`
   *  OR omit a FORMAT — we append JSONEachRow in that case. */
  async query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
    const stripped = sql.trim().replace(/;\s*$/, "");
    const finalSql = /\bformat\s+\w+/i.test(stripped) ? stripped : `${stripped} FORMAT JSONEachRow`;
    const r = await this.rawPost("/", finalSql);
    if (!r.body) return [];
    const out: T[] = [];
    for (const line of r.body.split("\n")) {
      const t = line.trim();
      if (!t) continue;
      try {
        out.push(JSON.parse(t) as T);
      } catch {
        // skip malformed
      }
    }
    return out;
  }

  /**
   * Insert rows in JSONEachRow format. Each row must be a plain object
   * whose fields match the table columns. Arrays are passed as JS arrays.
   * Errors throw with the ClickHouse response body for diagnostics.
   */
  async insertJSONEachRow(table: string, rows: ReadonlyArray<Record<string, unknown>>): Promise<void> {
    if (rows.length === 0) return;
    const body = rows.map((r) => JSON.stringify(r)).join("\n") + "\n";
    const sql = `INSERT INTO ${this.qualifyTable(table)} FORMAT JSONEachRow`;
    await this.rawPostWithQuery("/", sql, body);
  }

  /** Returns the fully-qualified table name with database prefix when not present. */
  qualifyTable(table: string): string {
    if (table.includes(".")) return table;
    return `${this.database}.${table}`;
  }

  // ---------- internals ----------

  private buildAuthHeader(): Record<string, string> {
    const headers: Record<string, string> = {};
    if (this.username) {
      const credentials = `${this.username}:${this.password ?? ""}`;
      headers["Authorization"] = "Basic " + Buffer.from(credentials, "utf8").toString("base64");
    }
    headers["X-ClickHouse-Database"] = this.database;
    return headers;
  }

  private rawGet(pathName: string): Promise<{ status: number; body: string }> {
    return this.transport(pathName, "GET", undefined, undefined);
  }

  /** Plain POST: full SQL is the body, no `?query=` parameter. */
  private rawPost(pathName: string, sql: string): Promise<{ status: number; body: string }> {
    return this.transport(pathName, "POST", undefined, sql);
  }

  /** POST with `?query=` (the SQL statement) and a separate body (data). Used for INSERT. */
  private rawPostWithQuery(pathName: string, sql: string, body: string): Promise<{ status: number; body: string }> {
    return this.transport(pathName, "POST", sql, body);
  }

  private transport(
    pathName: string,
    method: "GET" | "POST",
    query: string | undefined,
    body: string | undefined
  ): Promise<{ status: number; body: string }> {
    const u = new URL(this.base.toString());
    if (!u.pathname || u.pathname === "/") u.pathname = pathName;
    else u.pathname = u.pathname.replace(/\/$/, "") + pathName;
    if (query !== undefined) u.searchParams.set("query", query);
    const isHttps = u.protocol === "https:";
    const transport = isHttps ? https : http;
    const headers = {
      "Content-Type": "text/plain; charset=utf-8",
      ...this.buildAuthHeader(),
    } as Record<string, string>;
    if (body !== undefined) headers["Content-Length"] = String(Buffer.byteLength(body, "utf8"));
    return new Promise((resolve, reject) => {
      const req = transport.request(
        {
          method,
          host: u.hostname,
          port: u.port ? Number(u.port) : (isHttps ? 443 : 80),
          path: `${u.pathname}${u.search}`,
          headers,
          timeout: this.timeoutMs,
        },
        (res) => {
          const chunks: Buffer[] = [];
          res.on("data", (c) => chunks.push(c));
          res.on("end", () => {
            const text = Buffer.concat(chunks).toString("utf8");
            const status = res.statusCode ?? 0;
            if (status >= 200 && status < 300) resolve({ status, body: text });
            else {
              const err: ClickHouseError = new Error(`ClickHouse HTTP ${status}: ${text.slice(0, 500)}`);
              err.status = status;
              err.body = text;
              reject(err);
            }
          });
        }
      );
      req.on("error", reject);
      req.on("timeout", () => {
        req.destroy(new Error(`ClickHouse request timed out after ${this.timeoutMs}ms`));
      });
      if (body !== undefined) req.write(body);
      req.end();
    });
  }
}

export function clickhouseFromEnv(env: NodeJS.ProcessEnv = process.env): ClickHouseClient {
  return new ClickHouseClient({
    url: env.CLICKHOUSE_URL ?? "http://localhost:8123",
    database: env.CLICKHOUSE_DB ?? "orderflow",
    username: env.CLICKHOUSE_USER || undefined,
    password: env.CLICKHOUSE_PASSWORD || undefined,
  });
}
