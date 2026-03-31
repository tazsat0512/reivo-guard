/**
 * Standalone Guard — framework-agnostic before/after pattern for TypeScript.
 *
 * Usage:
 *   import { Guard } from 'reivo-guard';
 *
 *   const guard = new Guard({ budgetLimitUsd: 10.0 });
 *
 *   const decision = guard.before({ messages: [{ role: 'user', content: 'Hello' }] });
 *   if (!decision.allowed) throw new Error(decision.reason);
 *   const response = await callLlm(messages);
 *   guard.after({ costUsd: 0.003 });
 */

import { ANOMALY_Z_THRESHOLD, type AnomalyResult } from './constants.js';
import { detectAnomaly, initEwmaState, updateEwma } from './anomaly-detector.js';
import { detectLoopByHash } from './loop-detector.js';
import { type DegradationLevel, type DegradationPolicy, getDegradationLevel } from './budget-degradation.js';
import type { EwmaState } from './types.js';

// ── Types ────────────────────────────────────────────────────────────

export interface GuardOptions {
  /** Maximum cumulative spend in USD. undefined = unlimited. */
  budgetLimitUsd?: number;
  /** Number of recent hashes to check for loops. Default: 20. */
  loopWindow?: number;
  /** Number of identical prompts within window to trigger. Default: 5. */
  loopThreshold?: number;
  /** Raise errors instead of returning non-allowed decisions. Default: false. */
  raiseOnBlock?: boolean;
  /** Enable EWMA anomaly detection on token counts. Default: false. */
  enableAnomalyDetection?: boolean;
  /** Z-score threshold for anomaly detection. Default: 3.0. */
  anomalyZThreshold?: number;
  /** Warmup samples before anomaly detection activates. Default: 5. */
  anomalyWarmup?: number;
  /** Max requests per rateLimitWindow seconds. undefined = unlimited. */
  rateLimit?: number;
  /** Time window in seconds for rate limiting. Default: 60. */
  rateLimitWindow?: number;
}

export interface BeforeInput {
  /** Messages to hash for loop detection. */
  messages?: Array<{ role: string; content: string }>;
  /** Pre-computed prompt hash (alternative to messages). */
  promptHash?: string;
  /** Token count for anomaly detection. */
  tokenCount?: number;
}

export interface AfterInput {
  /** Cost in USD. undefined = estimate from tokens. 0 = record zero explicitly. */
  costUsd?: number;
  /** Model name for cost estimation. */
  model?: string;
  /** Input token count for cost estimation. */
  inputTokens?: number;
  /** Output token count for cost estimation. */
  outputTokens?: number;
}

export interface GuardDecision {
  allowed: boolean;
  reason?: string;
  budgetUsedUsd: number;
  budgetRemainingUsd: number | null;
  degradationLevel?: DegradationLevel;
  anomaly?: AnomalyResult;
}

export interface GuardStats {
  totalRequests: number;
  totalCostUsd: number;
  budgetUsedUsd: number;
  budgetLimitUsd: number | null;
  budgetRemainingUsd: number | null;
  blockedRequests: number;
  degradationLevel?: DegradationLevel;
  ewmaValue?: number;
  ewmaSamples?: number;
}

// ── Errors ───────────────────────────────────────────────────────────

export class BudgetExceeded extends Error {
  constructor(public usedUsd: number, public limitUsd: number) {
    super(`Budget exceeded: $${usedUsd.toFixed(4)} / $${limitUsd.toFixed(2)}`);
    this.name = 'BudgetExceeded';
  }
}

export class LoopDetected extends Error {
  constructor(public matchCount: number, public window: number) {
    super(`Loop detected: ${matchCount} identical prompts in last ${window} requests`);
    this.name = 'LoopDetected';
  }
}

export class AnomalyDetectedError extends Error {
  constructor(public zScore: number, public currentRate: number) {
    super(`Anomaly detected: z-score=${zScore.toFixed(2)}, rate=${currentRate}`);
    this.name = 'AnomalyDetected';
  }
}

export class RateLimitExceeded extends Error {
  constructor(public requestsInWindow: number, public limit: number) {
    super(`Rate limit exceeded: ${requestsInWindow}/${limit} requests`);
    this.name = 'RateLimitExceeded';
  }
}

// ── Cost estimation ──────────────────────────────────────────────────

// Prices per 1M tokens [input, output] in USD
const PRICING: Record<string, [number, number]> = {
  // OpenAI
  'gpt-4o': [2.50, 10.00],
  'gpt-4o-mini': [0.15, 0.60],
  'gpt-4-turbo': [10.00, 30.00],
  'gpt-4': [30.00, 60.00],
  'gpt-3.5-turbo': [0.50, 1.50],
  'o1': [15.00, 60.00],
  'o1-mini': [3.00, 12.00],
  'o1-pro': [150.00, 600.00],
  'o3-mini': [1.10, 4.40],
  // Anthropic
  'claude-3-5-sonnet-20241022': [3.00, 15.00],
  'claude-3-5-haiku-20241022': [0.80, 4.00],
  'claude-3-opus-20240229': [15.00, 75.00],
  'claude-3-haiku-20240307': [0.25, 1.25],
  'claude-sonnet-4-20250514': [3.00, 15.00],
  'claude-opus-4-20250514': [15.00, 75.00],
  // Google
  'gemini-1.5-pro': [1.25, 5.00],
  'gemini-1.5-flash': [0.075, 0.30],
  'gemini-2.0-flash': [0.10, 0.40],
  'gemini-2.0-flash-lite': [0.075, 0.30],
};

export function estimateCost(model: string, inputTokens: number, outputTokens: number): number {
  let pricing = PRICING[model];
  if (!pricing) {
    let bestKey = '';
    for (const key of Object.keys(PRICING)) {
      if (model.startsWith(key) && key.length > bestKey.length) {
        bestKey = key;
        pricing = PRICING[key];
      }
    }
  }
  if (!pricing) return 0;
  return (inputTokens * pricing[0] + outputTokens * pricing[1]) / 1_000_000;
}

// ── Helper ───────────────────────────────────────────────────────────

/** Simple non-cryptographic hash — good enough for loop detection deduplication. */
function hashMessages(messages: Array<{ role: string; content: string }>): string {
  const text = messages.map((m) => `${m.role}:${m.content}`).join('\n');
  // FNV-1a 64-bit (as two 32-bit halves for JS compatibility)
  let h1 = 0x811c9dc5;
  let h2 = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193);
    h2 = Math.imul(h2 ^ (c >>> 0), 0x01000193);
  }
  return (h1 >>> 0).toString(16).padStart(8, '0') + (h2 >>> 0).toString(16).padStart(8, '0');
}

// ── Guard class ──────────────────────────────────────────────────────

export class Guard {
  private _budgetLimitUsd: number | null;
  private _budgetUsedUsd = 0;
  private _loopWindow: number;
  private _loopThreshold: number;
  private _loopHashes: string[] = [];
  private _raiseOnBlock: boolean;
  private _anomalyEnabled: boolean;
  private _anomalyZThreshold: number;
  private _anomalyWarmup: number;
  private _ewma: EwmaState;
  private _rateLimit: number | null;
  private _rateLimitWindow: number;
  private _requestTimestamps: number[] = [];

  totalRequests = 0;
  totalCostUsd = 0;
  blockedRequests = 0;

  constructor(options: GuardOptions = {}) {
    if (options.budgetLimitUsd !== undefined && options.budgetLimitUsd <= 0) {
      throw new Error('budgetLimitUsd must be positive or undefined');
    }
    if (options.loopWindow !== undefined && options.loopWindow < 1) {
      throw new Error('loopWindow must be >= 1');
    }
    if (options.loopThreshold !== undefined && options.loopThreshold < 2) {
      throw new Error('loopThreshold must be >= 2');
    }
    if (options.rateLimit !== undefined && options.rateLimit < 1) {
      throw new Error('rateLimit must be >= 1');
    }

    this._budgetLimitUsd = options.budgetLimitUsd ?? null;
    this._loopWindow = options.loopWindow ?? 20;
    this._loopThreshold = options.loopThreshold ?? 5;
    this._raiseOnBlock = options.raiseOnBlock ?? false;
    this._anomalyEnabled = options.enableAnomalyDetection ?? false;
    this._anomalyZThreshold = options.anomalyZThreshold ?? ANOMALY_Z_THRESHOLD;
    this._anomalyWarmup = options.anomalyWarmup ?? 5;
    this._ewma = initEwmaState();
    this._rateLimit = options.rateLimit ?? null;
    this._rateLimitWindow = options.rateLimitWindow ?? 60;
  }

  /** Check budget, loop, anomaly, and rate limit before an LLM call. */
  before(input: BeforeInput = {}): GuardDecision {
    const used = this._budgetUsedUsd;
    const remaining = this._budgetLimitUsd !== null
      ? Math.max(0, this._budgetLimitUsd - used)
      : null;

    // Degradation level
    let degLevel: DegradationLevel | undefined;
    if (this._budgetLimitUsd !== null) {
      degLevel = getDegradationLevel(used, this._budgetLimitUsd).level;
    }

    this.totalRequests += 1;

    // Budget check
    if (this._budgetLimitUsd !== null && used >= this._budgetLimitUsd) {
      this.blockedRequests += 1;
      if (this._raiseOnBlock) {
        throw new BudgetExceeded(used, this._budgetLimitUsd);
      }
      return {
        allowed: false,
        reason: `Budget exceeded: $${used.toFixed(4)} / $${this._budgetLimitUsd.toFixed(2)}`,
        budgetUsedUsd: used,
        budgetRemainingUsd: 0,
        degradationLevel: degLevel,
      };
    }

    // Rate limiting
    let rateLimitNow: number | null = null;
    if (this._rateLimit !== null) {
      rateLimitNow = Date.now() / 1000;
      const cutoff = rateLimitNow - this._rateLimitWindow;
      this._requestTimestamps = this._requestTimestamps.filter((t) => t > cutoff);
      if (this._requestTimestamps.length >= this._rateLimit) {
        this.blockedRequests += 1;
        if (this._raiseOnBlock) {
          throw new RateLimitExceeded(this._requestTimestamps.length, this._rateLimit);
        }
        return {
          allowed: false,
          reason: `Rate limit exceeded: ${this._requestTimestamps.length}/${this._rateLimit} in ${this._rateLimitWindow}s`,
          budgetUsedUsd: used,
          budgetRemainingUsd: remaining,
          degradationLevel: degLevel,
        };
      }
    }

    // Loop detection
    const hash = input.promptHash ?? (input.messages ? hashMessages(input.messages) : null);
    if (hash !== null) {
      this._loopHashes.push(hash);
      if (this._loopHashes.length > this._loopWindow) {
        this._loopHashes = this._loopHashes.slice(-this._loopWindow);
      }
      const result = detectLoopByHash(this._loopHashes.slice(0, -1), hash);
      if (result.matchCount >= this._loopThreshold) {
        this.blockedRequests += 1;
        if (this._raiseOnBlock) {
          throw new LoopDetected(result.matchCount, this._loopWindow);
        }
        return {
          allowed: false,
          reason: `Loop detected: ${result.matchCount} identical prompts in last ${this._loopWindow} requests`,
          budgetUsedUsd: used,
          budgetRemainingUsd: remaining,
          degradationLevel: degLevel,
        };
      }
    }

    // Anomaly detection
    let anomalyResult: AnomalyResult | undefined;
    if (this._anomalyEnabled && input.tokenCount !== undefined) {
      anomalyResult = detectAnomaly(this._ewma, input.tokenCount, this._anomalyWarmup);
      this._ewma = updateEwma(this._ewma, input.tokenCount);
      if (anomalyResult.isAnomaly) {
        this.blockedRequests += 1;
        if (this._raiseOnBlock) {
          throw new AnomalyDetectedError(anomalyResult.zScore, input.tokenCount);
        }
        return {
          allowed: false,
          reason: `Anomaly detected: z-score=${anomalyResult.zScore.toFixed(2)} (threshold=${this._anomalyZThreshold})`,
          budgetUsedUsd: used,
          budgetRemainingUsd: remaining,
          degradationLevel: degLevel,
          anomaly: anomalyResult,
        };
      }
    }

    // Only consume rate limit slot when request is allowed
    if (rateLimitNow !== null) {
      this._requestTimestamps.push(rateLimitNow);
    }

    return {
      allowed: true,
      budgetUsedUsd: used,
      budgetRemainingUsd: remaining,
      degradationLevel: degLevel,
      anomaly: anomalyResult,
    };
  }

  /** Record cost after an LLM call. */
  after(input: AfterInput = {}): void {
    let cost = input.costUsd;

    if (cost === undefined && (input.inputTokens || input.outputTokens) && input.model) {
      cost = estimateCost(input.model, input.inputTokens ?? 0, input.outputTokens ?? 0);
    }

    if (cost === undefined) cost = 0;
    if (!Number.isFinite(cost) || cost < 0) cost = 0;

    this._budgetUsedUsd += cost;
    this.totalCostUsd += cost;
  }

  /** Get current degradation policy. null if no budget limit. */
  get degradation(): DegradationPolicy | null {
    if (this._budgetLimitUsd === null) return null;
    return getDegradationLevel(this._budgetUsedUsd, this._budgetLimitUsd);
  }

  /** Return current guard statistics. */
  get stats(): GuardStats {
    const result: GuardStats = {
      totalRequests: this.totalRequests,
      totalCostUsd: Math.round(this.totalCostUsd * 1e6) / 1e6,
      budgetUsedUsd: Math.round(this._budgetUsedUsd * 1e6) / 1e6,
      budgetLimitUsd: this._budgetLimitUsd,
      budgetRemainingUsd: this._budgetLimitUsd !== null
        ? Math.round(Math.max(0, this._budgetLimitUsd - this._budgetUsedUsd) * 1e6) / 1e6
        : null,
      blockedRequests: this.blockedRequests,
    };
    if (this._budgetLimitUsd !== null) {
      result.degradationLevel = getDegradationLevel(this._budgetUsedUsd, this._budgetLimitUsd).level;
    }
    if (this._anomalyEnabled) {
      result.ewmaValue = Math.round(this._ewma.ewmaValue * 1e4) / 1e4;
      result.ewmaSamples = this._ewma.sampleCount ?? 0;
    }
    return result;
  }

  /** Reset all state. */
  reset(): void {
    this._budgetUsedUsd = 0;
    this._loopHashes = [];
    this._ewma = initEwmaState();
    this._requestTimestamps = [];
    this.totalRequests = 0;
    this.totalCostUsd = 0;
    this.blockedRequests = 0;
  }
}
