/**
 * GuardStore — platform-agnostic key-value storage interface.
 *
 * Cloudflare KVNamespace is structurally compatible (no adapter needed).
 * For testing or non-CF environments, use createMemoryStore().
 */
export interface GuardStore {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
}

/**
 * In-memory GuardStore for testing and non-Cloudflare environments.
 */
export function createMemoryStore(): GuardStore {
  const data = new Map<string, { value: string; expiresAt?: number }>();

  return {
    async get(key: string): Promise<string | null> {
      const entry = data.get(key);
      if (!entry) return null;
      if (entry.expiresAt && Date.now() > entry.expiresAt * 1000) {
        data.delete(key);
        return null;
      }
      return entry.value;
    },
    async put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void> {
      data.set(key, {
        value,
        expiresAt: options?.expirationTtl ? Math.floor(Date.now() / 1000) + options.expirationTtl : undefined,
      });
    },
  };
}
