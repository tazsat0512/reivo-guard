/**
 * Logprobs Normalizer — unified interface for OpenAI and Gemini logprob formats.
 *
 * OpenAI: choices[0].logprobs.content[].logprob + top_logprobs[]
 * Gemini (Vertex): candidates[0].logprobsResult.topCandidates[].candidates[]
 * Anthropic: not supported (use LLM-as-Judge instead)
 */

export interface NormalizedToken {
  token: string;
  logprob: number;
  topAlternatives?: Array<{ token: string; logprob: number }>;
}

export interface NormalizedLogprobs {
  tokens: NormalizedToken[];
}

/**
 * Normalize OpenAI chat completion logprobs.
 * Format: choices[0].logprobs.content[].{token, logprob, top_logprobs[]}
 */
export function normalizeOpenAILogprobs(response: unknown): NormalizedLogprobs | null {
  const res = response as Record<string, unknown> | null;
  if (!res || typeof res !== 'object') return null;

  const choices = res.choices as Record<string, unknown>[] | undefined;
  if (!Array.isArray(choices) || choices.length === 0) return null;

  const logprobs = choices[0].logprobs as Record<string, unknown> | undefined;
  if (!logprobs || typeof logprobs !== 'object') return null;

  const content = logprobs.content as Array<{
    token: string;
    logprob: number;
    top_logprobs?: Array<{ token: string; logprob: number }>;
  }> | undefined;
  if (!Array.isArray(content) || content.length === 0) return null;

  return {
    tokens: content.map((entry) => ({
      token: entry.token,
      logprob: entry.logprob,
      topAlternatives: entry.top_logprobs?.map((tp) => ({
        token: tp.token,
        logprob: tp.logprob,
      })),
    })),
  };
}

/**
 * Normalize Gemini (Vertex AI) logprobs.
 * Format: candidates[0].logprobsResult.topCandidates[].candidates[]
 *
 * Each topCandidates entry represents one token position.
 * The first candidate in each position is the chosen token.
 */
export function normalizeGeminiLogprobs(response: unknown): NormalizedLogprobs | null {
  const res = response as Record<string, unknown> | null;
  if (!res || typeof res !== 'object') return null;

  const candidates = res.candidates as Record<string, unknown>[] | undefined;
  if (!Array.isArray(candidates) || candidates.length === 0) return null;

  const logprobsResult = candidates[0].logprobsResult as Record<string, unknown> | undefined;
  if (!logprobsResult || typeof logprobsResult !== 'object') return null;

  const topCandidates = logprobsResult.topCandidates as Array<{
    candidates: Array<{ token: string; logProbability: number }>;
  }> | undefined;
  if (!Array.isArray(topCandidates) || topCandidates.length === 0) return null;

  return {
    tokens: topCandidates.map((position) => {
      const chosen = position.candidates[0];
      return {
        token: chosen?.token ?? '',
        logprob: chosen?.logProbability ?? 0,
        topAlternatives: position.candidates.slice(1).map((alt) => ({
          token: alt.token,
          logprob: alt.logProbability,
        })),
      };
    }),
  };
}

/**
 * Normalize logprobs from any supported provider.
 * Returns null if logprobs are not present or provider is unsupported.
 */
export function normalizeLogprobs(
  response: unknown,
  provider: 'openai' | 'google',
): NormalizedLogprobs | null {
  switch (provider) {
    case 'openai':
      return normalizeOpenAILogprobs(response);
    case 'google':
      return normalizeGeminiLogprobs(response);
    default:
      return null;
  }
}
