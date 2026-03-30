import { ANOMALY_Z_THRESHOLD, type AnomalyResult, EWMA_ALPHA } from './constants.js';
import type { EwmaState } from './types.js';

export function initEwmaState(): EwmaState {
  return {
    ewmaValue: 0,
    ewmaVariance: 0,
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
    lastUpdated: Date.now(),
  };
}

export function detectAnomaly(state: EwmaState, currentRate: number): AnomalyResult {
  const stdDev = Math.sqrt(state.ewmaVariance);
  const zScore = stdDev === 0 ? 0 : (currentRate - state.ewmaValue) / stdDev;

  return {
    isAnomaly: zScore > ANOMALY_Z_THRESHOLD,
    zScore,
    ewmaValue: state.ewmaValue,
    currentRate,
  };
}
