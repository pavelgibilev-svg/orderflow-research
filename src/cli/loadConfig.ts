import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { StrategyConfig } from "../strategy/types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEFAULT_CONFIG_PATH = path.join(__dirname, "..", "..", "config", "strategy.default.json");

export function loadConfig(overridePath?: string): StrategyConfig {
  const filePath = overridePath ?? DEFAULT_CONFIG_PATH;
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw) as StrategyConfig;
}
