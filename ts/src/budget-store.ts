import { BUDGET_ALERT_THRESHOLDS, type BudgetStatus } from './constants.js';
import type { GuardStore } from './store.js';
import type { BudgetState } from './types.js';

const BUDGET_KEY_PREFIX = 'budget:';

function budgetKey(userId: string, agentId?: string | null): string {
  if (agentId) {
    return `${BUDGET_KEY_PREFIX}${userId}:agent:${agentId}`;
  }
  return `${BUDGET_KEY_PREFIX}${userId}`;
}

const DEFAULT_BUDGET_STATE: BudgetState = { usedUsd: 0, blockedUntil: null, lastAlertThreshold: 0 };

function parseBudgetState(raw: string): BudgetState {
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      usedUsd: typeof parsed.usedUsd === 'number' && Number.isFinite(parsed.usedUsd) ? parsed.usedUsd : 0,
      blockedUntil: typeof parsed.blockedUntil === 'number' ? parsed.blockedUntil : null,
      lastAlertThreshold: typeof parsed.lastAlertThreshold === 'number' ? parsed.lastAlertThreshold : 0,
    };
  } catch {
    return { ...DEFAULT_BUDGET_STATE };
  }
}

export async function getBudgetState(store: GuardStore, userId: string): Promise<BudgetState> {
  const raw = await store.get(budgetKey(userId));
  if (!raw) return { ...DEFAULT_BUDGET_STATE };
  return parseBudgetState(raw);
}

export async function getAgentBudgetState(
  store: GuardStore,
  userId: string,
  agentId: string,
): Promise<BudgetState> {
  const raw = await store.get(budgetKey(userId, agentId));
  if (!raw) return { ...DEFAULT_BUDGET_STATE };
  return parseBudgetState(raw);
}

export async function setBudgetState(
  store: GuardStore,
  userId: string,
  state: BudgetState,
): Promise<void> {
  await store.put(budgetKey(userId), JSON.stringify(state));
}

/** Sanitize cost to prevent NaN/Infinity/negative values from corrupting state. */
function sanitizeCost(costUsd: number): number {
  if (!Number.isFinite(costUsd) || costUsd < 0) return 0;
  return costUsd;
}

export async function addCost(
  store: GuardStore,
  userId: string,
  costUsd: number,
): Promise<BudgetState> {
  const state = await getBudgetState(store, userId);
  state.usedUsd += sanitizeCost(costUsd);
  await setBudgetState(store, userId, state);
  return state;
}

export async function updateAgentBudgetState(
  store: GuardStore,
  userId: string,
  agentId: string,
  costUsd: number,
): Promise<BudgetState> {
  const state = await getAgentBudgetState(store, userId, agentId);
  state.usedUsd += sanitizeCost(costUsd);
  await store.put(budgetKey(userId, agentId), JSON.stringify(state));
  return state;
}

export function checkBudget(state: BudgetState, limitUsd: number | null): BudgetStatus {
  if (limitUsd === null) {
    return {
      limitUsd: null,
      usedUsd: state.usedUsd,
      remainingUsd: null,
      blocked: false,
    };
  }

  const remaining = limitUsd - state.usedUsd;
  return {
    limitUsd,
    usedUsd: state.usedUsd,
    remainingUsd: Math.max(0, remaining),
    blocked:
      state.usedUsd >= limitUsd || (state.blockedUntil !== null && Date.now() < state.blockedUntil),
  };
}

export function getTriggeredAlertThreshold(
  usedUsd: number,
  limitUsd: number,
  lastAlertThreshold: number,
): number | null {
  if (limitUsd <= 0) return null;
  const ratio = usedUsd / limitUsd;
  for (const threshold of BUDGET_ALERT_THRESHOLDS) {
    if (ratio >= threshold && lastAlertThreshold < threshold) {
      return threshold;
    }
  }
  return null;
}
