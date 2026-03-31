// Standalone Guard (primary API)
export {
  Guard,
  type GuardOptions,
  type BeforeInput,
  type AfterInput,
  type GuardDecision,
  type GuardStats,
  BudgetExceeded,
  LoopDetected,
  AnomalyDetectedError,
  RateLimitExceeded,
  estimateCost,
} from './guard.js';

// Constants and shared types
export {
  type AnomalyResult,
  type BudgetStatus,
  type LoopDetectionResult,
} from './constants.js';

// Store
export { type GuardStore, createMemoryStore } from './store.js';

// Types
export type { BudgetAction, BudgetPolicy, BudgetState, LoopState, EwmaState } from './types.js';

// Loop detection
export {
  getLoopState,
  setLoopState,
  detectLoopByHash,
  detectLoopByCosine,
} from './loop-detector.js';

// Budget enforcement
export {
  getBudgetState,
  getAgentBudgetState,
  setBudgetState,
  addCost,
  updateAgentBudgetState,
  checkBudget,
  getTriggeredAlertThreshold,
} from './budget-store.js';

// Quality verification
export {
  type QualityAssessment,
  assessQuality,
  stripLogprobs,
  stripGeminiLogprobs,
} from './quality-verifier.js';

// Logprobs normalization
export {
  type NormalizedLogprobs,
  type NormalizedToken,
  normalizeLogprobs,
  normalizeOpenAILogprobs,
  normalizeGeminiLogprobs,
} from './logprobs-normalizer.js';

// Quality trend detection
export { type QualityTrend, detectQualityTrend } from './quality-trend.js';

// Anomaly detection
export { initEwmaState, updateEwma, detectAnomaly } from './anomaly-detector.js';

// Budget degradation
export {
  type DegradationLevel,
  type DegradationPolicy,
  getDegradationLevel,
} from './budget-degradation.js';

// LLM-as-Judge
export {
  type JudgeInput,
  type JudgeResult,
  buildJudgePrompt,
  parseJudgeResponse,
  extractPromptText,
  extractResponseText,
} from './llm-judge.js';

// Session lock
export { getSessionLockedModel, setSessionLockedModel, clearSessionLockedModel } from './session-lock.js';

// Session tracking
export {
  type SessionState,
  type SessionUpdateInput,
  initSessionState,
  getSessionState,
  setSessionState,
  trackRequest,
  blockSession,
  isSessionBlocked,
  getSessionMetrics,
} from './session-tracker.js';
