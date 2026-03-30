import type { GuardStore } from './store.js';

const SESSION_KEY_PREFIX = 'session_state:';
const SESSION_TTL = 86400; // 24 hours

export interface SessionState {
  sessionId: string;
  userId: string;
  requestCount: number;
  totalCostUsd: number;
  models: string[];
  qualityScores: number[];
  loopDetected: boolean;
  blocked: boolean;
  blockReason?: string;
  startedAt: number;
  lastActivityAt: number;
}

export interface SessionUpdateInput {
  costUsd: number;
  model: string;
  qualityScore?: number;
  loopDetected?: boolean;
  blocked?: boolean;
  blockReason?: string;
}

export function initSessionState(sessionId: string, userId: string): SessionState {
  const now = Date.now();
  return {
    sessionId,
    userId,
    requestCount: 0,
    totalCostUsd: 0,
    models: [],
    qualityScores: [],
    loopDetected: false,
    blocked: false,
    startedAt: now,
    lastActivityAt: now,
  };
}

export async function getSessionState(
  store: GuardStore,
  sessionId: string,
): Promise<SessionState | null> {
  const raw = await store.get(`${SESSION_KEY_PREFIX}${sessionId}`);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as SessionState;
    // Basic shape validation
    if (typeof parsed.sessionId !== 'string' || typeof parsed.requestCount !== 'number') {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export async function setSessionState(
  store: GuardStore,
  state: SessionState,
): Promise<void> {
  await store.put(
    `${SESSION_KEY_PREFIX}${state.sessionId}`,
    JSON.stringify(state),
    { expirationTtl: SESSION_TTL },
  );
}

/**
 * Record a request in the session and return the updated state.
 * Creates a new session if one doesn't exist.
 */
export async function trackRequest(
  store: GuardStore,
  sessionId: string,
  userId: string,
  input: SessionUpdateInput,
): Promise<SessionState> {
  let state = await getSessionState(store, sessionId);
  if (!state) {
    state = initSessionState(sessionId, userId);
  }

  state.requestCount += 1;
  const safeCost = Number.isFinite(input.costUsd) && input.costUsd >= 0 ? input.costUsd : 0;
  state.totalCostUsd += safeCost;
  state.lastActivityAt = Date.now();

  // Track unique models used in this session
  if (!state.models.includes(input.model)) {
    state.models.push(input.model);
  }

  // Quality scores: keep last 50 for trend analysis
  if (input.qualityScore !== undefined) {
    state.qualityScores.push(input.qualityScore);
    if (state.qualityScores.length > 50) {
      state.qualityScores = state.qualityScores.slice(-50);
    }
  }

  if (input.loopDetected) {
    state.loopDetected = true;
  }

  if (input.blocked) {
    state.blocked = true;
    state.blockReason = input.blockReason;
  }

  await setSessionState(store, state);
  return state;
}

/**
 * Force-block a session. Used by session kill API (2-3).
 */
export async function blockSession(
  store: GuardStore,
  sessionId: string,
  reason: string,
): Promise<SessionState | null> {
  const state = await getSessionState(store, sessionId);
  if (!state) return null;

  state.blocked = true;
  state.blockReason = reason;
  await setSessionState(store, state);
  return state;
}

/**
 * Check if a session is currently blocked.
 */
export async function isSessionBlocked(
  store: GuardStore,
  sessionId: string,
): Promise<{ blocked: boolean; reason?: string }> {
  const state = await getSessionState(store, sessionId);
  if (!state) return { blocked: false };
  return { blocked: state.blocked, reason: state.blockReason };
}

/**
 * Get session summary metrics.
 */
export function getSessionMetrics(state: SessionState) {
  const durationMs = state.lastActivityAt - state.startedAt;
  const avgCostPerRequest = state.requestCount > 0 ? state.totalCostUsd / state.requestCount : 0;
  const avgQualityScore =
    state.qualityScores.length > 0
      ? state.qualityScores.reduce((a, b) => a + b, 0) / state.qualityScores.length
      : null;

  return {
    sessionId: state.sessionId,
    requestCount: state.requestCount,
    totalCostUsd: state.totalCostUsd,
    avgCostPerRequest,
    avgQualityScore,
    durationMs,
    modelsUsed: state.models,
    loopDetected: state.loopDetected,
    blocked: state.blocked,
  };
}
