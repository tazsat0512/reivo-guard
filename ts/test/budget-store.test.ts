import { describe, expect, it } from 'vitest';
import { checkBudget, getTriggeredAlertThreshold } from '../src/budget-store.js';
import type { BudgetState } from '../src/types.js';

describe('budget-guard', () => {
  it('allows request when under budget', () => {
    const state: BudgetState = { usedUsd: 5.0, blockedUntil: null, lastAlertThreshold: 0 };
    const result = checkBudget(state, 10.0);
    expect(result.blocked).toBe(false);
    expect(result.remainingUsd).toBe(5.0);
  });

  it('blocks when budget exceeded', () => {
    const state: BudgetState = { usedUsd: 10.5, blockedUntil: null, lastAlertThreshold: 0 };
    const result = checkBudget(state, 10.0);
    expect(result.blocked).toBe(true);
    expect(result.remainingUsd).toBe(0);
  });

  it('allows unlimited budget', () => {
    const state: BudgetState = { usedUsd: 999.0, blockedUntil: null, lastAlertThreshold: 0 };
    const result = checkBudget(state, null);
    expect(result.blocked).toBe(false);
    expect(result.remainingUsd).toBe(null);
  });

  it('blocks when blockedUntil is in the future', () => {
    const state: BudgetState = {
      usedUsd: 5.0,
      blockedUntil: Date.now() + 60000,
      lastAlertThreshold: 0,
    };
    const result = checkBudget(state, 10.0);
    expect(result.blocked).toBe(true);
  });

  describe('alert thresholds', () => {
    it('triggers 50% alert', () => {
      const threshold = getTriggeredAlertThreshold(5.0, 10.0, 0);
      expect(threshold).toBe(0.5);
    });

    it('triggers 80% alert', () => {
      const threshold = getTriggeredAlertThreshold(8.0, 10.0, 0.5);
      expect(threshold).toBe(0.8);
    });

    it('triggers 100% alert', () => {
      const threshold = getTriggeredAlertThreshold(10.0, 10.0, 0.8);
      expect(threshold).toBe(1.0);
    });

    it('does not re-trigger same threshold', () => {
      const threshold = getTriggeredAlertThreshold(6.0, 10.0, 0.5);
      expect(threshold).toBe(null);
    });
  });
});
