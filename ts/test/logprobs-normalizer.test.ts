import { describe, expect, it } from 'vitest';
import {
  normalizeGeminiLogprobs,
  normalizeLogprobs,
  normalizeOpenAILogprobs,
} from '../src/logprobs-normalizer.js';

describe('logprobs-normalizer', () => {
  describe('normalizeOpenAILogprobs', () => {
    it('extracts tokens from OpenAI format', () => {
      const response = {
        choices: [
          {
            message: { content: 'Hello world' },
            logprobs: {
              content: [
                { token: 'Hello', logprob: -0.1, top_logprobs: [{ token: 'Hi', logprob: -2.0 }] },
                { token: ' world', logprob: -0.3 },
              ],
            },
          },
        ],
      };
      const result = normalizeOpenAILogprobs(response);
      expect(result).not.toBeNull();
      expect(result!.tokens).toHaveLength(2);
      expect(result!.tokens[0].token).toBe('Hello');
      expect(result!.tokens[0].logprob).toBe(-0.1);
      expect(result!.tokens[0].topAlternatives).toEqual([{ token: 'Hi', logprob: -2.0 }]);
      expect(result!.tokens[1].topAlternatives).toBeUndefined();
    });

    it('returns null for missing logprobs', () => {
      const response = {
        choices: [{ message: { content: 'Hello' } }],
      };
      expect(normalizeOpenAILogprobs(response)).toBeNull();
    });

    it('returns null for null input', () => {
      expect(normalizeOpenAILogprobs(null)).toBeNull();
      expect(normalizeOpenAILogprobs({})).toBeNull();
    });
  });

  describe('normalizeGeminiLogprobs', () => {
    it('extracts tokens from Gemini Vertex format', () => {
      const response = {
        candidates: [
          {
            content: { parts: [{ text: 'Hello world' }] },
            logprobsResult: {
              topCandidates: [
                {
                  candidates: [
                    { token: 'Hello', logProbability: -0.05 },
                    { token: 'Hi', logProbability: -1.5 },
                    { token: 'Hey', logProbability: -2.0 },
                  ],
                },
                {
                  candidates: [
                    { token: ' world', logProbability: -0.2 },
                    { token: ' there', logProbability: -1.8 },
                  ],
                },
              ],
            },
          },
        ],
      };
      const result = normalizeGeminiLogprobs(response);
      expect(result).not.toBeNull();
      expect(result!.tokens).toHaveLength(2);
      expect(result!.tokens[0].token).toBe('Hello');
      expect(result!.tokens[0].logprob).toBe(-0.05);
      expect(result!.tokens[0].topAlternatives).toEqual([
        { token: 'Hi', logprob: -1.5 },
        { token: 'Hey', logprob: -2.0 },
      ]);
      expect(result!.tokens[1].token).toBe(' world');
      expect(result!.tokens[1].topAlternatives).toEqual([{ token: ' there', logprob: -1.8 }]);
    });

    it('returns null for missing logprobsResult', () => {
      const response = {
        candidates: [{ content: { parts: [{ text: 'Hello' }] } }],
      };
      expect(normalizeGeminiLogprobs(response)).toBeNull();
    });

    it('returns null for null input', () => {
      expect(normalizeGeminiLogprobs(null)).toBeNull();
    });
  });

  describe('normalizeLogprobs', () => {
    it('dispatches to openai normalizer', () => {
      const response = {
        choices: [
          {
            logprobs: {
              content: [{ token: 'test', logprob: -0.5 }],
            },
          },
        ],
      };
      const result = normalizeLogprobs(response, 'openai');
      expect(result).not.toBeNull();
      expect(result!.tokens[0].token).toBe('test');
    });

    it('dispatches to google normalizer', () => {
      const response = {
        candidates: [
          {
            logprobsResult: {
              topCandidates: [
                {
                  candidates: [{ token: 'test', logProbability: -0.3 }],
                },
              ],
            },
          },
        ],
      };
      const result = normalizeLogprobs(response, 'google');
      expect(result).not.toBeNull();
      expect(result!.tokens[0].token).toBe('test');
    });
  });
});
