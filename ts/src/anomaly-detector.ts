import { ANOMALY_Z_THRESHOLD, type AnomalyResult, EWMA_ALPHA } from './constants.js';
import type { EwmaState } from './types.js';

const DEFAULT_WARMUP = 5;

export function initEwmaState(): EwmaState {
  return {
    ewmaValue: 0,
    ewmaVariance: 0,
    sampleCount: 0,
    lastUpdated: Date.now(),
  };
}

export function updateEwma(state: EwmaState, newValue: number): EwmaState {
  const diff = newValue - state.ewmaValue;
  const newEwma = state.ewmaValue + EWMA_ALPHA * diff;
  const newVariance = (1 - EWMA_ALPHA) * (state.ewmaVariance + EWMA_ALPHA * diff * diff);

  return {
    ewmaValue: newEwma,
    ewmaVariance: newVariance,
    sampleCount: (state.sampleCount ?? 0) + 1,
    lastUpdated: Date.now(),
  };
}

export function detectAnomaly(
  state: EwmaState,
  currentRate: number,
  warmup: number = DEFAULT_WARMUP,
): AnomalyResult {
  if ((state.sampleCount ?? 0) < warmup) {
    return {
      isAnomaly: false,
      zScore: 0,
      ewmaValue: state.ewmaValue,
      currentRate,
    };
  }

  const stdDev = Math.sqrt(state.ewmaVariance);
  const zScore = stdDev === 0 ? 0 : Math.abs(currentRate - state.ewmaValue) / stdDev;

  return {
    isAnomaly: zScore > ANOMALY_Z_THRESHOLD,
    zScore,
    ewmaValue: state.ewmaValue,
    currentRate,
  };
}
