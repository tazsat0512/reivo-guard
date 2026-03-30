import { describe, expect, it } from 'vitest';
import { assessQuality, stripGeminiLogprobs, stripLogprobs } from '../src/quality-verifier.js';

describe('quality-verifier', () => {
  describe('assessQuality', () => {
    it('returns score 1 and no fallback when logprobs are missing', () => {
      const response = {
        choices: [{ message: { content: 'Hello' }, finish_reason: 'stop' }],
        usage: { prompt_tokens: 5, completion_tokens: 3 },
      };
      const result = assessQuality(response);
      expect(result.score).toBe(1);
      expect(result.shouldFallback).toBe(false);
      expect(result.reason).toBe('insufficient_tokens');
    });

    it('returns score 1 and no fallback when too few tokens', () => {
      const response = {
        choices: [
          {
            message: { content: 'Hi' },
            logprobs: {
              content: [
                { token: 'Hi', logprob: -0.1 },
                { token: '!', logprob: -0.2 },
              ],
            },
          },
        ],
      };
      const result = assessQuality(response);
      expect(result.score).toBe(1);
      expect(result.shouldFallback).toBe(false);
      expect(result.tokenCount).toBe(2);
    });

    it('returns high score and no fallback for confident response', () => {
      const tokens = Array.from({ length: 10 }, (_, i) => ({
        token: `word${i}`,
        logprob: -0.1, // Very confident
        top_logprobs: [
          { token: `word${i}`, logprob: -0.1 },
          { token: `alt${i}`, logprob: -3.0 },
        ],
      }));
      const response = {
        choices: [{ message: { content: 'test' }, logprobs: { content: tokens } }],
      };
      const result = assessQuality(response);
      expect(result.score).toBeGreaterThan(0.9);
      expect(result.shouldFallback).toBe(false);
      expect(result.meanLogprob).toBeCloseTo(-0.1, 1);
      expect(result.tokenCount).toBe(10);
    });

    it('returns low score and triggers fallback for uncertain response', () => {
      const tokens = Array.from({ length: 10 }, (_, i) => ({
        token: `word${i}`,
        logprob: -1.5, // Uncertain
        top_logprobs: [
          { token: `word${i}`, logprob: -1.5 },
          { token: `alt${i}`, logprob: -1.6 },
        ],
      }));
      const response = {
        choices: [{ message: { content: 'test' }, logprobs: { content: tokens } }],
      };
      const result = assessQuality(response);
      expect(result.score).toBeLessThan(0.5);
      expect(result.shouldFallback).toBe(true);
      expect(result.meanLogprob).toBeCloseTo(-1.5, 1);
    });

    it('handles edge case: exactly at threshold', () => {
      const tokens = Array.from({ length: 10 }, (_, i) => ({
        token: `word${i}`,
        logprob: -1.0, // Exactly at threshold
      }));
      const response = {
        choices: [{ message: { content: 'test' }, logprobs: { content: tokens } }],
      };
      const result = assessQuality(response);
      // At -1.0 exactly, shouldFallback is false (threshold is strictly less than)
      expect(result.shouldFallback).toBe(false);
      expect(result.score).toBe(0.5);
    });

    it('handles null/invalid response gracefully', () => {
      expect(assessQuality(null).shouldFallback).toBe(false);
      expect(assessQuality({}).shouldFallback).toBe(false);
      expect(assessQuality('string').shouldFallback).toBe(false);
    });
  });

  describe('stripLogprobs', () => {
    it('removes logprobs from choices', () => {
      const response = {
        id: 'chatcmpl-123',
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: 'Hello' },
            logprobs: { content: [{ token: 'Hello', logprob: -0.1 }] },
            finish_reason: 'stop',
          },
        ],
        usage: { prompt_tokens: 5, completion_tokens: 1 },
      };
      const result = stripLogprobs(response) as Record<string, unknown>;
      const choices = result.choices as Record<string, unknown>[];
      expect(choices[0].logprobs).toBeUndefined();
      expect(choices[0].message).toEqual({ role: 'assistant', content: 'Hello' });
      expect(result.id).toBe('chatcmpl-123');
    });

    it('returns original when no choices', () => {
      expect(stripLogprobs({ usage: {} })).toEqual({ usage: {} });
      expect(stripLogprobs(null)).toBe(null);
    });
  });

  describe('stripGeminiLogprobs', () => {
    it('removes logprobsResult from candidates', () => {
      const response = {
        candidates: [
          {
            content: { parts: [{ text: 'Hello' }] },
            logprobsResult: {
              topCandidates: [{ candidates: [{ token: 'Hello', logProbability: -0.1 }] }],
            },
            finishReason: 'STOP',
          },
        ],
        usageMetadata: { promptTokenCount: 5 },
      };
      const result = stripGeminiLogprobs(response) as Record<string, unknown>;
      const candidates = result.candidates as Record<string, unknown>[];
      expect(candidates[0].logprobsResult).toBeUndefined();
      expect(candidates[0].content).toEqual({ parts: [{ text: 'Hello' }] });
      expect(result.usageMetadata).toEqual({ promptTokenCount: 5 });
    });

    it('returns original when no candidates', () => {
      expect(stripGeminiLogprobs({ error: 'bad' })).toEqual({ error: 'bad' });
      expect(stripGeminiLogprobs(null)).toBe(null);
    });
  });

  describe('assessQuality with google provider', () => {
    it('assesses quality from Gemini logprobs', () => {
      const topCandidates = Array.from({ length: 10 }, (_, i) => ({
        candidates: [
          { token: `word${i}`, logProbability: -0.1 },
          { token: `alt${i}`, logProbability: -3.0 },
        ],
      }));
      const response = {
        candidates: [
          {
            content: { parts: [{ text: 'test' }] },
            logprobsResult: { topCandidates },
          },
        ],
      };
      const result = assessQuality(response, 'google');
      expect(result.score).toBeGreaterThan(0.9);
      expect(result.shouldFallback).toBe(false);
      expect(result.tokenCount).toBe(10);
    });
  });
});
