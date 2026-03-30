import { describe, expect, it } from 'vitest';
import { detectLoopByCosine, detectLoopByHash } from '../src/loop-detector.js';

describe('loop-detector', () => {
  describe('detectLoopByHash', () => {
    it('does not flag unique hashes', () => {
      const hashes = ['a', 'b', 'c', 'd', 'e'];
      const result = detectLoopByHash(hashes, 'f');
      expect(result.isLoop).toBe(false);
      expect(result.matchCount).toBe(1);
    });

    it('detects loop when hash appears 5 times', () => {
      const hashes = ['x', 'x', 'x', 'x', 'a', 'b'];
      const result = detectLoopByHash(hashes, 'x');
      expect(result.isLoop).toBe(true);
      expect(result.matchCount).toBe(5);
    });

    it('does not flag below threshold', () => {
      const hashes = ['x', 'x', 'x', 'a', 'b'];
      const result = detectLoopByHash(hashes, 'x');
      expect(result.isLoop).toBe(false);
      expect(result.matchCount).toBe(4);
    });

    it('respects window size of 20', () => {
      // 25 hashes, but only last 20 considered
      const hashes = Array(21).fill('y').concat(['a', 'b', 'c', 'd']);
      const result = detectLoopByHash(hashes, 'z');
      expect(result.matchCount).toBe(1);
    });
  });

  describe('detectLoopByCosine', () => {
    it('detects similar prompts with high cosine similarity', () => {
      // Use prompts that share most words but have enough unique tokens for IDF
      const base =
        'explain the quicksort algorithm step by step with examples showing the partition phase';
      const prompts = [
        'describe the mergesort algorithm step by step with examples showing the merge phase',
        base,
        `${base} and complexity analysis`,
        `${base} please`,
        `${base} in detail`,
      ];
      const result = detectLoopByCosine(prompts, base);
      // Similarity should be high between the repeated base prompts
      expect(result.similarity).toBeGreaterThan(0.5);
    });

    it('does not flag different prompts', () => {
      const prompts = [
        'Write a sorting algorithm',
        'Create a REST API endpoint',
        'Deploy to production',
      ];
      const result = detectLoopByCosine(prompts, 'Configure the database connection');
      expect(result.isLoop).toBe(false);
    });

    it('handles empty history', () => {
      const result = detectLoopByCosine([], 'hello');
      expect(result.isLoop).toBe(false);
    });

    it('handles single item history', () => {
      const result = detectLoopByCosine(['hello'], 'hello');
      expect(result.isLoop).toBe(false);
    });
  });
});
