import { describe, expect, it } from 'vitest';
import {
  clearSessionLockedModel,
  getSessionLockedModel,
  setSessionLockedModel,
} from '../src/session-lock.js';
import { createMemoryStore } from '../src/store.js';

describe('session-lock', () => {
  it('returns null when no lock exists', async () => {
    const store = createMemoryStore();
    const result = await getSessionLockedModel(store, 'session-1');
    expect(result).toBeNull();
  });

  it('returns null for null sessionId', async () => {
    const store = createMemoryStore();
    const result = await getSessionLockedModel(store, null);
    expect(result).toBeNull();
  });

  it('stores and retrieves locked model', async () => {
    const store = createMemoryStore();
    await setSessionLockedModel(store, 'session-1', 'gpt-4o-mini');
    const result = await getSessionLockedModel(store, 'session-1');
    expect(result).toBe('gpt-4o-mini');
  });

  it('does not set lock for null sessionId', async () => {
    const store = createMemoryStore();
    await setSessionLockedModel(store, null, 'gpt-4o-mini');
    // No error thrown, just a no-op
  });

  it('different sessions have independent locks', async () => {
    const store = createMemoryStore();
    await setSessionLockedModel(store, 'session-1', 'gpt-4o-mini');
    await setSessionLockedModel(store, 'session-2', 'gpt-4o');
    expect(await getSessionLockedModel(store, 'session-1')).toBe('gpt-4o-mini');
    expect(await getSessionLockedModel(store, 'session-2')).toBe('gpt-4o');
  });

  it('clearSessionLockedModel clears the lock', async () => {
    const store = createMemoryStore();
    await setSessionLockedModel(store, 'session-3', 'gpt-4o');
    expect(await getSessionLockedModel(store, 'session-3')).toBe('gpt-4o');

    await clearSessionLockedModel(store, 'session-3');
    const result = await getSessionLockedModel(store, 'session-3');
    expect(result).toBe(''); // empty string = no lock
  });

  it('clearSessionLockedModel handles null sessionId', async () => {
    const store = createMemoryStore();
    await clearSessionLockedModel(store, null); // should not throw
  });
});
