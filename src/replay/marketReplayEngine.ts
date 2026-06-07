// Market replay engine.
//
// Drives multiple async iterators (incremental_book_L2, trades,
// derivative_ticker, liquidations, book_ticker) merged on `ts` (ms).
// Yields a flat stream of {kind, event} that the caller can dispatch.
//
// We use a tiny n-way merge: at each step we pick the source whose head event
// has the smallest timestamp. Because each source is itself ordered by
// timestamp this is correct and O(N) with a constant number of sources.

import type { AnyEvent } from "../data/schema.js";
import { streamTardisFile } from "../data/tardisCsvLoader.js";
import type { ResolvedFile } from "../data/fileResolver.js";

interface IterState {
  iter: AsyncIterator<AnyEvent>;
  head: AnyEvent | null;
  done: boolean;
  source: ResolvedFile;
}

export interface ReplayEvent {
  ts: number;
  ev: AnyEvent;
  source: ResolvedFile;
}

export interface ReplayOpts {
  /**
   * Per-data-type ts ceiling (ms). When a source's next event exceeds the
   * ceiling, we stop reading that file. Other sources continue. This is the
   * mechanism that lets backtestDay cap L2 replay to N hours while letting
   * the full-day trades file feed the TargetChecker.
   */
  endTsByDataType?: Partial<Record<string, number>>;
}

export async function* replayFiles(
  files: ResolvedFile[],
  opts: ReplayOpts = {}
): AsyncIterableIterator<ReplayEvent> {
  // Open every file and prefetch the first event from each.
  const states: IterState[] = [];
  for (const f of files) {
    const endTsMs = opts.endTsByDataType?.[f.dataType];
    const iter = streamTardisFile(f.path, endTsMs !== undefined ? { endTsMs } : {})[Symbol.asyncIterator]();
    const first = await iter.next();
    states.push({
      iter,
      head: first.done ? null : first.value,
      done: !!first.done,
      source: f,
    });
  }

  while (true) {
    // Find min ts among non-done sources.
    let minIdx = -1;
    let minTs = Number.POSITIVE_INFINITY;
    for (let i = 0; i < states.length; i++) {
      const s = states[i];
      if (s.done || !s.head) continue;
      if (s.head.ts < minTs) {
        minTs = s.head.ts;
        minIdx = i;
      }
    }
    if (minIdx === -1) return;

    const s = states[minIdx];
    const ev = s.head!;
    yield { ts: ev.ts, ev, source: s.source };
    // Advance.
    const next = await s.iter.next();
    if (next.done) {
      s.done = true;
      s.head = null;
    } else {
      s.head = next.value;
    }
  }
}
