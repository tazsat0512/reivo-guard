/** Constants inlined from @reivo/shared for standalone distribution. */

export const EWMA_ALPHA = 0.3;
export const ANOMALY_Z_THRESHOLD = 3.0;

export const LOOP_HASH_WINDOW = 20;
export const LOOP_HASH_THRESHOLD = 5;
export const LOOP_COSINE_THRESHOLD = 0.92;

export const BUDGET_ALERT_THRESHOLDS = [0.5, 0.8, 1.0] as const;

export interface AnomalyResult {
  isAnomaly: boolean;
  zScore: number;
  ewmaValue: number;
  currentRate: number;
}

export interface LoopDetectionResult {
  isLoop: boolean;
  matchCount: number;
  similarity?: number;
}

export interface BudgetStatus {
  limitUsd: number | null;
  usedUsd: number;
  remainingUsd: number | null;
  blocked: boolean;
}
