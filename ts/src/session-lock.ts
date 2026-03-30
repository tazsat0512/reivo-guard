import type { GuardStore } from './store.js';

const SESSION_LOCK_TTL = 3600; // 1 hour

export async function getSessionLockedModel(
  store: GuardStore,
  sessionId: string | null,
): Promise<string | null> {
  if (!sessionId) return null;
  return store.get(`session:${sessionId}`);
}

export async function setSessionLockedModel(
  store: GuardStore,
  sessionId: string | null,
  model: string,
): Promise<void> {
  if (!sessionId) return;
  await store.put(`session:${sessionId}`, model, { expirationTtl: SESSION_LOCK_TTL });
}

/**
 * Clear the session model lock, allowing the next request to re-evaluate routing.
 * Used by auto-upgrade when quality is degrading — unlocks the session so
 * the router can pick a better model.
 */
export async function clearSessionLockedModel(
  store: GuardStore,
  sessionId: string | null,
): Promise<void> {
  if (!sessionId) return;
  // Write empty string with short TTL to effectively clear
  await store.put(`session:${sessionId}`, '', { expirationTtl: 1 });
}
