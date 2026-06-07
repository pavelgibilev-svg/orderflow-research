// Minimal CLI argument parser. We intentionally avoid pulling in commander
// to keep dependencies tiny.

export interface ParsedArgs {
  positional: string[];
  flags: Record<string, string | boolean>;
}

export function parseArgs(argv: string[]): ParsedArgs {
  const out: ParsedArgs = { positional: [], flags: {} };
  let i = 0;
  while (i < argv.length) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        out.flags[key] = next;
        i += 2;
        continue;
      } else {
        out.flags[key] = true;
        i += 1;
        continue;
      }
    } else if (a.startsWith("-")) {
      out.flags[a.slice(1)] = true;
      i += 1;
    } else {
      out.positional.push(a);
      i += 1;
    }
  }
  return out;
}

export function getString(args: ParsedArgs, key: string, fallback?: string): string {
  const v = args.flags[key];
  if (typeof v === "string") return v;
  if (fallback !== undefined) return fallback;
  throw new Error(`Missing --${key}`);
}

export function getNumber(args: ParsedArgs, key: string, fallback?: number): number {
  const v = args.flags[key];
  if (typeof v === "string") {
    const n = +v;
    if (!Number.isFinite(n)) throw new Error(`--${key} must be a number, got "${v}"`);
    return n;
  }
  if (fallback !== undefined) return fallback;
  throw new Error(`Missing --${key}`);
}

export function getOptString(args: ParsedArgs, key: string): string | undefined {
  const v = args.flags[key];
  return typeof v === "string" ? v : undefined;
}
