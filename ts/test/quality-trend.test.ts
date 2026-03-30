import { describe, expect, it } from 'vitest';
import { detectQualityTrend } from '../src/quality-trend.js';

describe('quality-trend', () => {
  it('returns insufficient_data for too few scores', () => {
    const result = detectQualityTrend([0.9, 0.8, 0.7]);
    expect(result.trend).toBe('insufficient_data');
    expect(result.shouldUpgrade).toBe(false);
  });

  it('returns insufficient_data for exactly 7 scores', () => {
    const result = detectQualityTrend([0.9, 0.8, 0.7, 0.9, 0.8, 0.7, 0.9]);
    expect(result.trend).toBe('insufficient_data');
  });

  it('detects stable trend', () => {
    // 8 scores, all around 0.85
    const scores = [0.85, 0.86, 0.84, 0.85, 0.86, 0.84, 0.85, 0.86];
    const result = detectQualityTrend(scores);
    expect(result.trend).toBe('stable');
    expect(result.shouldUpgrade).toBe(false);
    expect(Math.abs(result.delta)).toBeLessThan(0.15);
  });

  it('detects degrading trend', () => {
    // Older scores high, recent scores low
    const scores = [0.9, 0.88, 0.85, 0.6, 0.55, 0.5, 0.48, 0.45];
    const result = detectQualityTrend(scores);
    expect(result.trend).toBe('degrading');
    expect(result.delta).toBeLessThan(-0.15);
  });

  it('sets shouldUpgrade when degrading AND recent avg below 0.5', () => {
    // Recent scores are very low
    const scores = [0.9, 0.85, 0.8, 0.35, 0.3, 0.25, 0.2, 0.15];
    const result = detectQualityTrend(scores);
    expect(result.trend).toBe('degrading');
    expect(result.shouldUpgrade).toBe(true);
    expect(result.avgRecent).toBeLessThan(0.5);
  });

  it('does NOT set shouldUpgrade when degrading but recent avg above 0.5', () => {
    // Degrading but recent scores still acceptable
    const scores = [0.95, 0.93, 0.92, 0.7, 0.68, 0.65, 0.63, 0.60];
    const result = detectQualityTrend(scores);
    expect(result.trend).toBe('degrading');
    expect(result.shouldUpgrade).toBe(false);
    expect(result.avgRecent).toBeGreaterThan(0.5);
  });

  it('detects improving trend', () => {
    // Older scores low, recent scores high
    const scores = [0.4, 0.45, 0.5, 0.75, 0.8, 0.85, 0.9, 0.92];
    const result = detectQualityTrend(scores);
    expect(result.trend).toBe('improving');
    expect(result.delta).toBeGreaterThan(0.15);
  });

  it('handles many scores (uses last 5 as recent)', () => {
    const older = Array(20).fill(0.9);
    const recent = [0.3, 0.35, 0.3, 0.25, 0.3];
    const result = detectQualityTrend([...older, ...recent]);
    expect(result.trend).toBe('degrading');
    expect(result.shouldUpgrade).toBe(true);
  });

  it('computes correct averages', () => {
    // 3 older + 5 recent = 8 total
    const scores = [0.9, 0.9, 0.9, 0.5, 0.5, 0.5, 0.5, 0.5];
    const result = detectQualityTrend(scores);
    expect(result.avgOlder).toBeCloseTo(0.9);
    expect(result.avgRecent).toBeCloseTo(0.5);
    expect(result.delta).toBeCloseTo(-0.4);
  });
});
