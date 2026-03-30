import { describe, expect, it } from 'vitest';
import { getDegradationLevel } from '../src/budget-degradation.js';

describe('getDegradationLevel', () => {
  it('returns normal when under 80%', () => {
    const result = getDegradationLevel(7, 10);
    expect(result.level).toBe('normal');
    expect(result.forceAggressiveRouting).toBe(false);
    expect(result.blockNewSessions).toBe(false);
    expect(result.blockAll).toBe(false);
  });

  it('returns aggressive at 80%', () => {
    const result = getDegradationLevel(8, 10);
    expect(result.level).toBe('aggressive');
    expect(result.forceAggressiveRouting).toBe(true);
    expect(result.blockNewSessions).toBe(false);
    expect(result.blockAll).toBe(false);
  });

  it('returns aggressive at 90%', () => {
    const result = getDegradationLevel(9, 10);
    expect(result.level).toBe('aggressive');
    expect(result.forceAggressiveRouting).toBe(true);
  });

  it('returns new_sessions_only at 95%', () => {
    const result = getDegradationLevel(9.5, 10);
    expect(result.level).toBe('new_sessions_only');
    expect(result.forceAggressiveRouting).toBe(true);
    expect(result.blockNewSessions).toBe(true);
    expect(result.blockAll).toBe(false);
  });

  it('returns blocked at 100%', () => {
    const result = getDegradationLevel(10, 10);
    expect(result.level).toBe('blocked');
    expect(result.blockAll).toBe(true);
  });

  it('returns blocked when over 100%', () => {
    const result = getDegradationLevel(15, 10);
    expect(result.level).toBe('blocked');
    expect(result.usageRatio).toBe(1.5);
  });

  it('returns blocked when limit is 0', () => {
    const result = getDegradationLevel(5, 0);
    expect(result.level).toBe('blocked');
  });

  it('returns normal at 0 usage', () => {
    const result = getDegradationLevel(0, 10);
    expect(result.level).toBe('normal');
    expect(result.usageRatio).toBe(0);
  });

  it('returns correct usage ratio', () => {
    const result = getDegradationLevel(4.5, 10);
    expect(result.usageRatio).toBeCloseTo(0.45);
  });
});
