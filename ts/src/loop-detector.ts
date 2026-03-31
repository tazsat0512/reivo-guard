import {
  LOOP_COSINE_THRESHOLD,
  LOOP_HASH_THRESHOLD,
  LOOP_HASH_WINDOW,
  type LoopDetectionResult,
} from './constants.js';
import type { GuardStore } from './store.js';
import type { LoopState } from './types.js';

const LOOP_KEY_PREFIX = 'loop:';

export async function getLoopState(store: GuardStore, userId: string): Promise<LoopState> {
  const raw = await store.get(`${LOOP_KEY_PREFIX}${userId}`);
  if (!raw) return { hashes: [], blocked: false };
  try {
    const parsed = JSON.parse(raw) as LoopState;
    if (!Array.isArray(parsed.hashes)) return { hashes: [], blocked: false };
    return parsed;
  } catch {
    return { hashes: [], blocked: false };
  }
}

export async function setLoopState(
  store: GuardStore,
  userId: string,
  state: LoopState,
): Promise<void> {
  await store.put(`${LOOP_KEY_PREFIX}${userId}`, JSON.stringify(state));
}

export function detectLoopByHash(hashes: string[], newHash: string): LoopDetectionResult {
  const window = hashes.slice(-LOOP_HASH_WINDOW);
  const matchCount = window.filter((h) => h === newHash).length + 1; // +1 for current
  return {
    isLoop: matchCount >= LOOP_HASH_THRESHOLD,
    matchCount,
  };
}

// TF-IDF based cosine similarity (no external API needed)
export function detectLoopByCosine(
  previousPrompts: string[],
  currentPrompt: string,
): LoopDetectionResult {
  if (previousPrompts.length < 2) {
    return { isLoop: false, matchCount: 0 };
  }

  const allDocs = [...previousPrompts, currentPrompt];
  const vectors = buildTfIdfVectors(allDocs);
  const currentVector = vectors[vectors.length - 1];

  let maxSim = 0;
  let highSimCount = 0;

  for (let i = 0; i < vectors.length - 1; i++) {
    const sim = cosineSimilarity(currentVector, vectors[i]);
    if (sim > maxSim) maxSim = sim;
    if (sim >= LOOP_COSINE_THRESHOLD) highSimCount++;
  }

  return {
    isLoop: highSimCount >= LOOP_HASH_THRESHOLD - 1,
    matchCount: highSimCount + 1,
    similarity: maxSim,
  };
}

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/\W+/)
    .filter((t) => t.length > 1);
}

function buildTfIdfVectors(docs: string[]): Map<string, number>[] {
  const tokenizedDocs = docs.map(tokenize);
  const df = new Map<string, number>();

  for (const tokens of tokenizedDocs) {
    const seen = new Set(tokens);
    for (const token of seen) {
      df.set(token, (df.get(token) ?? 0) + 1);
    }
  }

  const n = docs.length;
  return tokenizedDocs.map((tokens) => {
    const tf = new Map<string, number>();
    for (const token of tokens) {
      tf.set(token, (tf.get(token) ?? 0) + 1);
    }
    const vector = new Map<string, number>();
    for (const [token, freq] of tf) {
      const idf = Math.log(1 + n / (df.get(token) ?? 1));
      vector.set(token, (freq / tokens.length) * idf);
    }
    return vector;
  });
}

function cosineSimilarity(a: Map<string, number>, b: Map<string, number>): number {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (const [key, valA] of a) {
    normA += valA * valA;
    const valB = b.get(key);
    if (valB !== undefined) {
      dotProduct += valA * valB;
    }
  }

  for (const [, valB] of b) {
    normB += valB * valB;
  }

  const magnitude = Math.sqrt(normA) * Math.sqrt(normB);
  return magnitude === 0 ? 0 : dotProduct / magnitude;
}
