/**
 * Budget Degradation — graceful response to budget pressure.
 *
 * Instead of hard-blocking at 100%, progressively restricts capabilities
 * as budget usage increases.
 */

export type DegradationLevel = 'normal' | 'aggressive' | 'new_sessions_only' | 'blocked';

export interface DegradationPolicy {
  level: DegradationLevel;
  /** Budget usage ratio (0-1+) */
  usageRatio: number;
  /** Force aggressive routing (cheaper models) */
  forceAggressiveRouting: boolean;
  /** Only allow requests within existing sessions */
  blockNewSessions: boolean;
  /** Block all requests */
  blockAll: boolean;
}

// Thresholds
const AGGRESSIVE_THRESHOLD = 0.8; // 80%
const NEW_SESSIONS_ONLY_THRESHOLD = 0.95; // 95%
const BLOCKED_THRESHOLD = 1.0; // 100%

/**
 * Determine degradation level based on budget usage.
 *
 * <80%  → normal: no restrictions
 * 80-95% → aggressive: force cheaper model routing
 * 95-100% → new_sessions_only: only existing sessions can continue
 * ≥100% → blocked: all requests blocked
 */
export function getDegradationLevel(usedUsd: number, limitUsd: number): DegradationPolicy {
  if (limitUsd <= 0) {
    return {
      level: 'blocked',
      usageRatio: 1,
      forceAggressiveRouting: true,
      blockNewSessions: true,
      blockAll: true,
    };
  }

  const ratio = usedUsd / limitUsd;

  if (ratio >= BLOCKED_THRESHOLD) {
    return {
      level: 'blocked',
      usageRatio: ratio,
      forceAggressiveRouting: true,
      blockNewSessions: true,
      blockAll: true,
    };
  }

  if (ratio >= NEW_SESSIONS_ONLY_THRESHOLD) {
    return {
      level: 'new_sessions_only',
      usageRatio: ratio,
      forceAggressiveRouting: true,
      blockNewSessions: true,
      blockAll: false,
    };
  }

  if (ratio >= AGGRESSIVE_THRESHOLD) {
    return {
      level: 'aggressive',
      usageRatio: ratio,
      forceAggressiveRouting: true,
      blockNewSessions: false,
      blockAll: false,
    };
  }

  return {
    level: 'normal',
    usageRatio: ratio,
    forceAggressiveRouting: false,
    blockNewSessions: false,
    blockAll: false,
  };
}
