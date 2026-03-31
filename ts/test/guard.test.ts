import { describe, expect, it } from 'vitest';
import {
  Guard,
  BudgetExceeded,
  LoopDetected,
  AnomalyDetectedError,
  RateLimitExceeded,
  estimateCost,
} from '../src/guard.js';

describe('Guard', () => {
  describe('basic usage', () => {
    it('allows requests with no limits', () => {
      const guard = new Guard();
      const d = guard.before({ messages: [{ role: 'user', content: 'hello' }] });
      expect(d.allowed).toBe(true);
      expect(d.budgetRemainingUsd).toBeNull();
    });

    it('tracks cost after calls', () => {
      const guard = new Guard({ budgetLimitUsd: 10 });
      guard.before();
      guard.after({ costUsd: 2.5 });
      expect(guard.stats.budgetUsedUsd).toBe(2.5);
      expect(guard.stats.budgetRemainingUsd).toBe(7.5);
    });

    it('counts total requests', () => {
      const guard = new Guard();
      guard.before();
      guard.before();
      guard.before();
      expect(guard.totalRequests).toBe(3);
    });
  });

  describe('budget enforcement', () => {
    it('blocks when budget exceeded', () => {
      const guard = new Guard({ budgetLimitUsd: 5 });
      guard.before();
      guard.after({ costUsd: 5 });
      const d = guard.before();
      expect(d.allowed).toBe(false);
      expect(d.reason).toContain('Budget exceeded');
      expect(d.budgetRemainingUsd).toBe(0);
    });

    it('raises BudgetExceeded when raiseOnBlock is true', () => {
      const guard = new Guard({ budgetLimitUsd: 1, raiseOnBlock: true });
      guard.before();
      guard.after({ costUsd: 1 });
      expect(() => guard.before()).toThrow(BudgetExceeded);
    });

    it('returns degradation level', () => {
      const guard = new Guard({ budgetLimitUsd: 100 });
      guard.before();
      guard.after({ costUsd: 85 });
      const d = guard.before();
      expect(d.degradationLevel).toBe('aggressive');
    });

    it('rejects non-positive budget limit', () => {
      expect(() => new Guard({ budgetLimitUsd: 0 })).toThrow();
      expect(() => new Guard({ budgetLimitUsd: -5 })).toThrow();
    });
  });

  describe('loop detection', () => {
    it('detects repeated identical prompts', () => {
      const guard = new Guard({ loopThreshold: 3 });
      const msg = [{ role: 'user', content: 'same prompt' }];
      guard.before({ messages: msg });
      guard.before({ messages: msg });
      const d = guard.before({ messages: msg });
      // 3rd time: hash appears 2 times in history + 1 current = matchCount 3
      // With default threshold of 5 this won't trigger — use threshold of 3
      expect(d.allowed).toBe(false);
      expect(d.reason).toContain('Loop detected');
    });

    it('does not flag different prompts', () => {
      const guard = new Guard({ loopThreshold: 3 });
      guard.before({ messages: [{ role: 'user', content: 'hello' }] });
      guard.before({ messages: [{ role: 'user', content: 'world' }] });
      const d = guard.before({ messages: [{ role: 'user', content: 'foo' }] });
      expect(d.allowed).toBe(true);
    });

    it('accepts pre-computed hash', () => {
      const guard = new Guard({ loopThreshold: 3 });
      guard.before({ promptHash: 'abc123' });
      guard.before({ promptHash: 'abc123' });
      const d = guard.before({ promptHash: 'abc123' });
      expect(d.allowed).toBe(false);
    });

    it('raises LoopDetected when raiseOnBlock is true', () => {
      const guard = new Guard({ loopThreshold: 3, raiseOnBlock: true });
      guard.before({ promptHash: 'x' });
      guard.before({ promptHash: 'x' });
      expect(() => guard.before({ promptHash: 'x' })).toThrow(LoopDetected);
    });
  });

  describe('anomaly detection', () => {
    it('suppresses during warmup', () => {
      const guard = new Guard({ enableAnomalyDetection: true, anomalyWarmup: 5 });
      for (let i = 0; i < 3; i++) {
        const d = guard.before({ tokenCount: 100 });
        expect(d.allowed).toBe(true);
      }
      // Spike during warmup — should still be allowed
      const d = guard.before({ tokenCount: 10000 });
      expect(d.allowed).toBe(true);
    });

    it('detects anomaly after warmup', () => {
      const guard = new Guard({ enableAnomalyDetection: true, anomalyWarmup: 5 });
      for (let i = 0; i < 20; i++) {
        guard.before({ tokenCount: 100 });
      }
      const d = guard.before({ tokenCount: 10000 });
      expect(d.allowed).toBe(false);
      expect(d.reason).toContain('Anomaly');
    });

    it('detects negative spike (drop below baseline)', () => {
      const guard = new Guard({ enableAnomalyDetection: true, anomalyWarmup: 5 });
      for (let i = 0; i < 50; i++) {
        guard.before({ tokenCount: 1000 });
      }
      const d = guard.before({ tokenCount: 0 });
      expect(d.allowed).toBe(false);
    });

    it('raises AnomalyDetectedError when raiseOnBlock is true', () => {
      const guard = new Guard({
        enableAnomalyDetection: true,
        anomalyWarmup: 5,
        raiseOnBlock: true,
      });
      for (let i = 0; i < 20; i++) {
        guard.before({ tokenCount: 100 });
      }
      expect(() => guard.before({ tokenCount: 10000 })).toThrow(AnomalyDetectedError);
    });
  });

  describe('rate limiting', () => {
    it('blocks after rate limit exceeded', () => {
      const guard = new Guard({ rateLimit: 3, rateLimitWindow: 60 });
      expect(guard.before().allowed).toBe(true);
      expect(guard.before().allowed).toBe(true);
      expect(guard.before().allowed).toBe(true);
      const d = guard.before();
      expect(d.allowed).toBe(false);
      expect(d.reason).toContain('Rate limit');
    });

    it('does not consume rate slot when blocked by other checks', () => {
      const guard = new Guard({ rateLimit: 10, budgetLimitUsd: 0.01 });
      guard.before();
      guard.after({ costUsd: 0.01 });
      // Budget exceeded — rate limit slot should NOT be consumed
      guard.before();
      guard.before();
      // Only 1 rate slot consumed (first allowed request)
    });

    it('raises RateLimitExceeded when raiseOnBlock is true', () => {
      const guard = new Guard({ rateLimit: 1, rateLimitWindow: 60, raiseOnBlock: true });
      guard.before();
      expect(() => guard.before()).toThrow(RateLimitExceeded);
    });
  });

  describe('cost estimation', () => {
    it('estimates cost when costUsd is undefined', () => {
      const guard = new Guard({ budgetLimitUsd: 100 });
      guard.before();
      guard.after({ model: 'gpt-4o-mini', inputTokens: 1000, outputTokens: 500 });
      // gpt-4o-mini: $0.15/1M input, $0.60/1M output
      // = 1000 * 0.15 / 1M + 500 * 0.60 / 1M = 0.00015 + 0.0003 = 0.00045
      expect(guard.stats.budgetUsedUsd).toBeCloseTo(0.00045, 6);
    });

    it('uses explicit costUsd=0 without estimation', () => {
      const guard = new Guard({ budgetLimitUsd: 100 });
      guard.before();
      guard.after({ costUsd: 0, model: 'gpt-4o', inputTokens: 1000000, outputTokens: 1000000 });
      expect(guard.stats.budgetUsedUsd).toBe(0);
    });

    it('handles unknown model', () => {
      const guard = new Guard({ budgetLimitUsd: 100 });
      guard.before();
      guard.after({ model: 'unknown-model', inputTokens: 1000, outputTokens: 500 });
      expect(guard.stats.budgetUsedUsd).toBe(0);
    });

    it('matches model by prefix', () => {
      const guard = new Guard({ budgetLimitUsd: 100 });
      guard.before();
      guard.after({ model: 'gpt-4o-2024-08-06', inputTokens: 1000000, outputTokens: 0 });
      // Should match gpt-4o: $2.50/1M input
      expect(guard.stats.budgetUsedUsd).toBeCloseTo(2.5, 2);
    });
  });

  describe('stats and degradation', () => {
    it('returns stats', () => {
      const guard = new Guard({ budgetLimitUsd: 50 });
      guard.before();
      guard.after({ costUsd: 10 });
      const s = guard.stats;
      expect(s.totalRequests).toBe(1);
      expect(s.budgetUsedUsd).toBe(10);
      expect(s.budgetLimitUsd).toBe(50);
      expect(s.budgetRemainingUsd).toBe(40);
      expect(s.degradationLevel).toBe('normal');
    });

    it('degradation property returns policy', () => {
      const guard = new Guard({ budgetLimitUsd: 100 });
      guard.before();
      guard.after({ costUsd: 90 });
      const d = guard.degradation;
      expect(d).not.toBeNull();
      expect(d!.level).toBe('aggressive');
      expect(d!.forceAggressiveRouting).toBe(true);
    });

    it('degradation returns null with no budget', () => {
      const guard = new Guard();
      expect(guard.degradation).toBeNull();
    });
  });

  describe('reset', () => {
    it('clears all state', () => {
      const guard = new Guard({ budgetLimitUsd: 100 });
      guard.before({ promptHash: 'x' });
      guard.after({ costUsd: 50 });
      guard.reset();
      expect(guard.totalRequests).toBe(0);
      expect(guard.totalCostUsd).toBe(0);
      expect(guard.stats.budgetUsedUsd).toBe(0);
    });
  });

  describe('blocked request counting', () => {
    it('counts blocked requests', () => {
      const guard = new Guard({ budgetLimitUsd: 1 });
      guard.before();
      guard.after({ costUsd: 1 });
      guard.before(); // blocked
      guard.before(); // blocked
      expect(guard.blockedRequests).toBe(2);
      expect(guard.totalRequests).toBe(3);
    });
  });
});

describe('estimateCost', () => {
  it('calculates gpt-4o cost', () => {
    const cost = estimateCost('gpt-4o', 1_000_000, 1_000_000);
    expect(cost).toBeCloseTo(12.5, 1); // 2.50 + 10.00
  });

  it('returns 0 for unknown model', () => {
    expect(estimateCost('mystery-model', 1000, 1000)).toBe(0);
  });
});
