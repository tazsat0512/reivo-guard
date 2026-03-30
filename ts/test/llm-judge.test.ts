import { describe, expect, it } from 'vitest';
import {
  buildJudgePrompt,
  extractPromptText,
  extractResponseText,
  parseJudgeResponse,
} from '../src/llm-judge.js';

describe('buildJudgePrompt', () => {
  it('returns gpt-4o-mini request', () => {
    const result = buildJudgePrompt({
      prompt: 'What is 2+2?',
      response: 'The answer is 4.',
      model: 'claude-3-haiku-20240307',
    });
    expect(result.model).toBe('gpt-4o-mini');
    expect(result.messages).toHaveLength(4);
    expect(result.messages[0].role).toBe('system');
    expect(result.messages[1].role).toBe('user');
    expect(result.messages[2].content).toContain('What is 2+2?');
    expect(result.messages[3].content).toContain('The answer is 4.');
    expect(result.max_tokens).toBe(100);
    expect(result.temperature).toBe(0);
  });

  it('truncates long prompts', () => {
    const longPrompt = 'x'.repeat(1000);
    const result = buildJudgePrompt({
      prompt: longPrompt,
      response: 'short',
      model: 'test',
    });
    // Prompt message (index 2) should be truncated to ~500 chars + delimiters
    expect(result.messages[2].content.length).toBeLessThan(600);
  });
});

describe('parseJudgeResponse', () => {
  it('parses valid JSON response', () => {
    const result = parseJudgeResponse('{"score": 0.85, "reason": "Good response"}');
    expect(result.score).toBe(0.85);
    expect(result.reason).toBe('Good response');
    expect(result.shouldFallback).toBe(false);
  });

  it('handles score below fallback threshold', () => {
    const result = parseJudgeResponse('{"score": 0.2, "reason": "Poor quality"}');
    expect(result.score).toBe(0.2);
    expect(result.shouldFallback).toBe(true);
  });

  it('clamps score to 0-1 range', () => {
    expect(parseJudgeResponse('{"score": 1.5}').score).toBe(1);
    expect(parseJudgeResponse('{"score": -0.5}').score).toBe(0);
  });

  it('extracts JSON from surrounding text', () => {
    const result = parseJudgeResponse('Here is my assessment: {"score": 0.7, "reason": "OK"} done');
    expect(result.score).toBe(0.7);
  });

  it('handles nested braces in reason', () => {
    const result = parseJudgeResponse('{"score": 0.6, "reason": "good {overall} quality"}');
    expect(result.score).toBe(0.6);
    expect(result.reason).toContain('overall');
  });

  it('returns fallback for unparseable response', () => {
    const result = parseJudgeResponse('I cannot evaluate this');
    expect(result.score).toBe(0.5);
    expect(result.shouldFallback).toBe(false);
    expect(result.reason).toContain('Could not parse');
  });

  it('returns fallback for empty response', () => {
    const result = parseJudgeResponse('');
    expect(result.score).toBe(0.5);
    expect(result.shouldFallback).toBe(false);
  });
});

describe('extractPromptText', () => {
  it('extracts from Anthropic string content', () => {
    const body = {
      messages: [{ role: 'user', content: 'Hello world' }],
    };
    expect(extractPromptText(body)).toBe('Hello world');
  });

  it('extracts from Anthropic content blocks', () => {
    const body = {
      messages: [
        {
          role: 'user',
          content: [{ type: 'text', text: 'Hello from blocks' }],
        },
      ],
    };
    expect(extractPromptText(body)).toBe('Hello from blocks');
  });

  it('skips assistant messages', () => {
    const body = {
      messages: [
        { role: 'assistant', content: 'Previous response' },
        { role: 'user', content: 'User question' },
      ],
    };
    expect(extractPromptText(body)).toBe('User question');
  });

  it('returns empty for null/undefined', () => {
    expect(extractPromptText(null)).toBe('');
    expect(extractPromptText(undefined)).toBe('');
  });
});

describe('extractResponseText', () => {
  it('extracts from Anthropic response', () => {
    const body = {
      content: [{ type: 'text', text: 'The answer is 42.' }],
    };
    expect(extractResponseText(body)).toBe('The answer is 42.');
  });

  it('joins multiple text blocks', () => {
    const body = {
      content: [
        { type: 'text', text: 'Part 1.' },
        { type: 'tool_use', id: 'x', name: 'test', input: {} },
        { type: 'text', text: 'Part 2.' },
      ],
    };
    expect(extractResponseText(body)).toBe('Part 1.\nPart 2.');
  });

  it('returns empty for null', () => {
    expect(extractResponseText(null)).toBe('');
  });
});
