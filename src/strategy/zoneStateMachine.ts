// Zone state machine: explicit transitions used by zoneDetector.
//
//   CANDIDATE -> CONFIRMED       (held conditions for cfg.minConfirmedDurationMin)
//   CANDIDATE -> INVALIDATED     (defended side gone / wrong direction / data bad)
//   CONFIRMED -> TRIGGERED       (price exits zone with thinning + flow flip)
//   CONFIRMED -> EXPIRED         (cfg.maxFormationDurationMin elapsed without trigger)
//   CONFIRMED -> INVALIDATED     (defended side broken before trigger)
//   TRIGGERED -> RESOLVED_*      (TargetChecker decides reached/failed/timeout)
//
// We expose deterministic transitions; zoneDetector calls `attempt(...)`
// helpers to perform legal moves and record `reasons`.

import type { Zone, ZoneStatus, ZoneReason } from "./types.js";

const ALLOWED: Record<ZoneStatus, ZoneStatus[]> = {
  CANDIDATE: ["CONFIRMED", "INVALIDATED", "EXPIRED", "NO_TRIGGER"],
  CONFIRMED: ["TRIGGERED", "INVALIDATED", "EXPIRED", "NO_TRIGGER"],
  TRIGGERED: ["RESOLVED_REACHED", "RESOLVED_FAILED", "EXPIRED"],
  RESOLVED_REACHED: [],
  RESOLVED_FAILED: [],
  EXPIRED: [],
  INVALIDATED: [],
  NO_TRIGGER: [],
};

export function canTransition(from: ZoneStatus, to: ZoneStatus): boolean {
  return ALLOWED[from].includes(to);
}

/**
 * Additive, NON-BEHAVIORAL observer hook (Part D, exportZoneFeatures).
 *
 * When set, the callback is invoked STRICTLY AFTER a transition has been
 * committed (status written, side effects applied, return value fixed) and only
 * for a *successful* transition. It cannot influence the transition decision,
 * `ALLOWED`, or the return value — it is a read-only notification. Default: none
 * (when unset, `transition` is byte-for-byte the original behaviour).
 *
 * NOTE: RESOLVED_REACHED / RESOLVED_FAILED are set directly by TargetChecker
 * (targetChecker.ts:130/139), bypassing `transition`, so they do NOT fire this
 * observer — consumers must collect resolved zones after TargetChecker runs.
 */
export type TransitionObserver = (zone: Zone, to: ZoneStatus, reason: ZoneReason) => void;

let transitionObserver: TransitionObserver | null = null;

export function setTransitionObserver(cb: TransitionObserver | null): void {
  transitionObserver = cb;
}

export function transition(zone: Zone, to: ZoneStatus, reason: ZoneReason): boolean {
  if (!canTransition(zone.status, to)) return false;
  zone.status = to;
  zone.reasons.push(reason);
  if (to === "CONFIRMED") zone.confirmedTs = reason.ts;
  else if (to === "TRIGGERED") zone.triggerTs = reason.ts;
  else if (to === "RESOLVED_REACHED" || to === "RESOLVED_FAILED" || to === "EXPIRED" || to === "INVALIDATED") {
    zone.resolvedTs = reason.ts;
  }
  // Observer fires only on a successful, already-committed transition; it is
  // read-only and does not affect the outcome above.
  if (transitionObserver !== null) transitionObserver(zone, to, reason);
  return true;
}
