import { describe, expect, it } from 'vitest';
import {
  blockSession,
  getSessionMetrics,
  getSessionState,
  initSessionState,
  isSessionBlocked,
  trackRequest,
} from '../src/session-tracker.js';
import { createMemoryStore } from '../src/store.js';

describe('session-tracker', () => {
  it('returns null for unknown session', async () => {
    const store = createMemoryStore();
    const state = await getSessionState(store, 'unknown');
    expect(state).toBeNull();
  });

  it('creates session on first trackRequest', async () => {
    const store = createMemoryStore();
    const state = await trackRequest(store, 'sess-1', 'user-1', {
      costUsd: 0.01,
      model: 'gpt-4o-mini',
    });
    expect(state.sessionId).toBe('sess-1');
    expect(state.userId).toBe('user-1');
    expect(state.requestCount).toBe(1);
    expect(state.totalCostUsd).toBe(0.01);
    expect(state.models).toEqual(['gpt-4o-mini']);
  });

  it('accumulates requests in a session', async () => {
    const store = createMemoryStore();
    await trackRequest(store, 'sess-1', 'user-1', { costUsd: 0.01, model: 'gpt-4o-mini' });
    await trackRequest(store, 'sess-1', 'user-1', { costUsd: 0.02, model: 'gpt-4o-mini' });
    const state = await trackRequest(store, 'sess-1', 'user-1', { costUsd: 0.05, model: 'gpt-4o' });

    expect(state.requestCount).toBe(3);
    expect(state.totalCostUsd).toBeCloseTo(0.08);
    expect(state.models).toEqual(['gpt-4o-mini', 'gpt-4o']);
  });

  it('tracks quality scores', async () => {
    const store = createMemoryStore();
    await trackRequest(store, 'sess-1', 'user-1', {
      costUsd: 0.01,
      model: 'gpt-4o-mini',
      qualityScore: 0.9,
    });
    const state = await trackRequest(store, 'sess-1', 'user-1', {
      costUsd: 0.01,
      model: 'gpt-4o-mini',
      qualityScore: 0.7,
    });
    expect(state.qualityScores).toEqual([0.9, 0.7]);
  });

  it('limits quality scores to last 50', async () => {
    const store = createMemoryStore();
    for (let i = 0; i < 60; i++) {
      await trackRequest(store, 'sess-1', 'user-1', {
        costUsd: 0.001,
        model: 'gpt-4o-mini',
        qualityScore: i / 100,
      });
    }
    const state = await getSessionState(store, 'sess-1');
    expect(state!.qualityScores.length).toBe(50);
    expect(state!.qualityScores[0]).toBeCloseTo(0.1); // starts from i=10
  });

  it('records loop detection', async () => {
    const store = createMemoryStore();
    const state = await trackRequest(store, 'sess-1', 'user-1', {
      costUsd: 0.01,
      model: 'gpt-4o-mini',
      loopDetected: true,
    });
    expect(state.loopDetected).toBe(true);
  });

  it('records block status', async () => {
    const store = createMemoryStore();
    const state = await trackRequest(store, 'sess-1', 'user-1', {
      costUsd: 0.01,
      model: 'gpt-4o-mini',
      blocked: true,
      blockReason: 'budget_exceeded',
    });
    expect(state.blocked).toBe(true);
    expect(state.blockReason).toBe('budget_exceeded');
  });

  describe('blockSession', () => {
    it('blocks an existing session', async () => {
      const store = createMemoryStore();
      await trackRequest(store, 'sess-1', 'user-1', { costUsd: 0.01, model: 'gpt-4o-mini' });

      const state = await blockSession(store, 'sess-1', 'manual_kill');
      expect(state).not.toBeNull();
      expect(state!.blocked).toBe(true);
      expect(state!.blockReason).toBe('manual_kill');
    });

    it('returns null for unknown session', async () => {
      const store = createMemoryStore();
      const state = await blockSession(store, 'unknown', 'test');
      expect(state).toBeNull();
    });
  });

  describe('isSessionBlocked', () => {
    it('returns false for unknown session', async () => {
      const store = createMemoryStore();
      const result = await isSessionBlocked(store, 'unknown');
      expect(result.blocked).toBe(false);
    });

    it('returns true for blocked session', async () => {
      const store = createMemoryStore();
      await trackRequest(store, 'sess-1', 'user-1', { costUsd: 0.01, model: 'gpt-4o-mini' });
      await blockSession(store, 'sess-1', 'loop_detected');

      const result = await isSessionBlocked(store, 'sess-1');
      expect(result.blocked).toBe(true);
      expect(result.reason).toBe('loop_detected');
    });
  });

  describe('getSessionMetrics', () => {
    it('computes correct metrics', () => {
      const state = initSessionState('sess-1', 'user-1');
      state.requestCount = 10;
      state.totalCostUsd = 0.50;
      state.models = ['gpt-4o-mini', 'gpt-4o'];
      state.qualityScores = [0.9, 0.8, 0.7, 0.85];
      state.startedAt = 1000;
      state.lastActivityAt = 61000;

      const metrics = getSessionMetrics(state);
      expect(metrics.requestCount).toBe(10);
      expect(metrics.totalCostUsd).toBe(0.50);
      expect(metrics.avgCostPerRequest).toBeCloseTo(0.05);
      expect(metrics.avgQualityScore).toBeCloseTo(0.8125);
      expect(metrics.durationMs).toBe(60000);
      expect(metrics.modelsUsed).toEqual(['gpt-4o-mini', 'gpt-4o']);
    });

    it('handles zero requests', () => {
      const state = initSessionState('sess-1', 'user-1');
      const metrics = getSessionMetrics(state);
      expect(metrics.avgCostPerRequest).toBe(0);
      expect(metrics.avgQualityScore).toBeNull();
    });
  });

  it('keeps sessions independent', async () => {
    const store = createMemoryStore();
    await trackRequest(store, 'sess-1', 'user-1', { costUsd: 0.10, model: 'gpt-4o' });
    await trackRequest(store, 'sess-2', 'user-1', { costUsd: 0.01, model: 'gpt-4o-mini' });

    const s1 = await getSessionState(store, 'sess-1');
    const s2 = await getSessionState(store, 'sess-2');
    expect(s1!.totalCostUsd).toBe(0.10);
    expect(s2!.totalCostUsd).toBe(0.01);
  });
});
