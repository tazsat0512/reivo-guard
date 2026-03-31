export type BudgetAction = 'block' | 'alert' | 'downgrade';

export interface BudgetPolicy {
  agentId: string | null; // null = global
  limitUsd: number;
  action: BudgetAction;
}

export interface BudgetState {
  usedUsd: number;
  blockedUntil: number | null;
  lastAlertThreshold: number;
}

export interface LoopState {
  hashes: string[];
  blocked: boolean;
  blockedAt?: number;
}

export interface EwmaState {
  ewmaValue: number;
  ewmaVariance: number;
  sampleCount?: number;
  lastUpdated: number;
}
