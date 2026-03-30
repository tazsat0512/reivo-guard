/**
 * Quality Verifier — logprob-based confidence scoring for routed requests.
 *
 * When a request is downgraded to a cheaper model, we assess the response's
 * confidence via logprobs. If average token entropy exceeds a threshold,
 * the response is flagged for fallback to the original model.
 *
 * Supports: OpenAI (logprobs), Gemini/Vertex (logprobsResult)
 * Not supported: Anthropic (use LLM-as-Judge instead, see #78)
 */

import type { NormalizedLogprobs, NormalizedToken } from './logprobs-normalizer.js';
import { normalizeLogprobs } from './logprobs-normalizer.js';

export interface QualityAssessment {
  /** 0-1, where 1 = maximum confidence */
  score: number;
  /** Mean logprob across all tokens (negative; closer to 0 = more confident) */
  meanLogprob: number;
  /** Mean per-token entropy (lower = more certain) */
  meanEntropy: number;
  /** Number of tokens assessed */
  tokenCount: number;
  /** Human-readable reason */
  reason: string;
  /** Whether the caller should retry with the original model */
  shouldFallback: boolean;
}

// Entropy threshold: above this, the model is "uncertain" and we should fallback.
// -1.0 mean logprob ≈ model is ~37% confident on average — a reasonable boundary.
const MEAN_LOGPROB_THRESHOLD = -1.0;

// Minimum tokens to make a judgement — too few tokens → skip verification
const MIN_TOKENS_FOR_ASSESSMENT = 5;

const INSUFFICIENT_RESULT: Readonly<QualityAssessment> = Object.freeze({
  score: 1,
  meanLogprob: 0,
  meanEntropy: 0,
  tokenCount: 0,
  reason: 'insufficient_tokens',
  shouldFallback: false,
});

/**
 * Compute entropy from top alternatives for a single token.
 * H = -Σ p * log(p) where p = exp(logprob)
 */
function tokenEntropy(entry: NormalizedToken): number {
  if (!entry.topAlternatives || entry.topAlternatives.length === 0) {
    const p = Math.exp(entry.logprob);
    return p > 0 ? -p * Math.log(p) : 0;
  }

  let h = 0;
  // Include the chosen token + alternatives
  const all = [{ logprob: entry.logprob }, ...entry.topAlternatives];
  for (const t of all) {
    const p = Math.exp(t.logprob);
    if (p > 0) {
      h -= p * Math.log(p);
    }
  }
  return h;
}

function assessFromNormalized(normalized: NormalizedLogprobs): QualityAssessment {
  const tokens = normalized.tokens;
  if (tokens.length < MIN_TOKENS_FOR_ASSESSMENT) {
    return { ...INSUFFICIENT_RESULT, tokenCount: tokens.length };
  }

  const sumLogprob = tokens.reduce((acc, t) => acc + t.logprob, 0);
  const meanLogprob = sumLogprob / tokens.length;

  const sumEntropy = tokens.reduce((acc, t) => acc + tokenEntropy(t), 0);
  const meanEntropy = sumEntropy / tokens.length;

  // Score: map mean logprob to 0-1 range
  // logprob 0 → score 1 (perfect), logprob -2 → score 0
  const score = Math.max(0, Math.min(1, 1 + meanLogprob / 2));
  const shouldFallback = meanLogprob < MEAN_LOGPROB_THRESHOLD;

  const reason = shouldFallback
    ? `low_confidence (mean_logprob=${meanLogprob.toFixed(3)})`
    : `confident (mean_logprob=${meanLogprob.toFixed(3)})`;

  return {
    score,
    meanLogprob,
    meanEntropy,
    tokenCount: tokens.length,
    reason,
    shouldFallback,
  };
}

/**
 * Assess quality of a response based on logprobs.
 * Supports OpenAI and Gemini (Vertex AI) response formats.
 *
 * @param provider - defaults to 'openai' for backward compatibility
 */
export function assessQuality(
  parsedResponse: unknown,
  provider: 'openai' | 'google' = 'openai',
): QualityAssessment {
  const normalized = normalizeLogprobs(parsedResponse, provider);
  if (!normalized) {
    return { ...INSUFFICIENT_RESULT };
  }
  return assessFromNormalized(normalized);
}

/**
 * Strip logprobs from OpenAI response before returning to client.
 * We injected logprobs for internal quality checking — the client
 * didn't request them, so we remove them to avoid confusion.
 */
export function stripLogprobs(parsedResponse: unknown): unknown {
  const res = parsedResponse as Record<string, unknown> | null;
  if (!res || typeof res !== 'object') return parsedResponse;

  const choices = res.choices as Record<string, unknown>[] | undefined;
  if (!Array.isArray(choices)) return parsedResponse;

  const cleaned = {
    ...res,
    choices: choices.map((c) => {
      const { logprobs: _, ...rest } = c;
      return rest;
    }),
  };
  return cleaned;
}

/**
 * Strip logprobs from Gemini response before returning to client.
 * Removes logprobsResult from each candidate.
 */
export function stripGeminiLogprobs(parsedResponse: unknown): unknown {
  const res = parsedResponse as Record<string, unknown> | null;
  if (!res || typeof res !== 'object') return parsedResponse;

  const candidates = res.candidates as Record<string, unknown>[] | undefined;
  if (!Array.isArray(candidates)) return parsedResponse;

  return {
    ...res,
    candidates: candidates.map((c) => {
      const { logprobsResult: _, ...rest } = c;
      return rest;
    }),
  };
}
