import { describe, expect, it } from 'vitest';
import { createMemoryStore } from '../src/store.js';

describe('createMemoryStore', () => {
  it('stores and retrieves values', async () => {
    const store = createMemoryStore();
    await store.put('key1', 'value1');
    expect(await store.get('key1')).toBe('value1');
  });

  it('returns null for missing keys', async () => {
    const store = createMemoryStore();
    expect(await store.get('nonexistent')).toBeNull();
  });

  it('overwrites existing values', async () => {
    const store = createMemoryStore();
    await store.put('key', 'first');
    await store.put('key', 'second');
    expect(await store.get('key')).toBe('second');
  });
});
