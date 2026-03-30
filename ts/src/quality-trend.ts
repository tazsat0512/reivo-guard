/**
 * Quality Trend Detector — detects degrading quality within a session.
 *
 * Compares recent quality scores against older scores to identify
 * trends that may require model upgrades or alerts.
 */

export interface QualityTrend {
  trend: 'stable' | 'degrading' | 'improving' | 'insufficient_data';
  /** True when degrading AND recent average is below acceptable threshold */
  shouldUpgrade: boolean;
  /** Average of recent scores (last RECENT_WINDOW) */
  avgRecent: number;
  /** Average of older scores (before RECENT_WINDOW) */
  avgOlder: number;
  /** avgRecent - avgOlder (negative = degrading) */
  delta: number;
}

// Minimum total scores needed to make a trend judgment
const MIN_SCORES_FOR_TREND = 8;
// Number of recent scores to compare against older ones
const RECENT_WINDOW = 5;
// Delta threshold: if avgRecent - avgOlder < this, it's degrading
const DEGRADING_THRESHOLD = -0.15;
// Improving threshold
const IMPROVING_THRESHOLD = 0.15;
// Below this recent average, shouldUpgrade triggers
const UPGRADE_SCORE_THRESHOLD = 0.5;

const INSUFFICIENT: Readonly<QualityTrend> = Object.freeze({
  trend: 'insufficient_data',
  shouldUpgrade: false,
  avgRecent: 0,
  avgOlder: 0,
  delta: 0,
});

/**
 * Detect quality trend from a list of quality scores (ordered chronologically).
 * Typically called with SessionState.qualityScores.
 */
export function detectQualityTrend(scores: number[]): QualityTrend {
  if (scores.length < MIN_SCORES_FOR_TREND) {
    return { ...INSUFFICIENT };
  }

  const recentScores = scores.slice(-RECENT_WINDOW);
  const olderScores = scores.slice(0, -RECENT_WINDOW);

  if (olderScores.length === 0) {
    return { ...INSUFFICIENT };
  }

  const avgRecent = recentScores.reduce((a, b) => a + b, 0) / recentScores.length;
  const avgOlder = olderScores.reduce((a, b) => a + b, 0) / olderScores.length;
  const delta = avgRecent - avgOlder;

  let trend: QualityTrend['trend'];
  if (delta <= DEGRADING_THRESHOLD) {
    trend = 'degrading';
  } else if (delta >= IMPROVING_THRESHOLD) {
    trend = 'improving';
  } else {
    trend = 'stable';
  }

  const shouldUpgrade = trend === 'degrading' && avgRecent < UPGRADE_SCORE_THRESHOLD;

  return { trend, shouldUpgrade, avgRecent, avgOlder, delta };
}
