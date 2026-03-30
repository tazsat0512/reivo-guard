import { describe, expect, it } from 'vitest';
import { detectAnomaly, initEwmaState, updateEwma } from '../src/anomaly-detector.js';

describe('anomaly-detector', () => {
  it('initializes with zero state', () => {
    const state = initEwmaState();
    expect(state.ewmaValue).toBe(0);
    expect(state.ewmaVariance).toBe(0);
  });

  it('converges EWMA towards stable input', () => {
    let state = initEwmaState();
    // Feed constant value 10 multiple times
    for (let i = 0; i < 20; i++) {
      state = updateEwma(state, 10);
    }
    expect(state.ewmaValue).toBeCloseTo(10, 1);
  });

  it('detects spike as anomaly', () => {
    let state = initEwmaState();
    // Build up baseline
    for (let i = 0; i < 50; i++) {
      state = updateEwma(state, 1.0);
    }

    // Now check a huge spike
    const result = detectAnomaly(state, 100);
    expect(result.isAnomaly).toBe(true);
    expect(result.zScore).toBeGreaterThan(3.0);
  });

  it('does not flag normal variation', () => {
    let state = initEwmaState();
    for (let i = 0; i < 50; i++) {
      state = updateEwma(state, 10 + Math.random() * 2);
    }
    const result = detectAnomaly(state, 11);
    expect(result.isAnomaly).toBe(false);
  });

  it('handles zero variance gracefully', () => {
    const state = initEwmaState();
    const result = detectAnomaly(state, 5);
    expect(result.isAnomaly).toBe(false);
    expect(result.zScore).toBe(0);
  });
});
