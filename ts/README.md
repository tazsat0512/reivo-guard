# reivo-guard

Open-source guardrails that auto-kill runaway AI agents.

> Last month, a developer's autonomous coding agent ran up a **$47,000 bill overnight**. A single misconfigured loop burned through tokens for 8 hours before anyone noticed. `reivo-guard` prevents this.

## Install

```bash
npm install reivo-guard
```

## Quick Start

```typescript
import { checkBudget, getBudgetState, detectLoopByHash } from 'reivo-guard';

// Check budget before each request
const state = await getBudgetState(store, userId);
const status = checkBudget(state, 50.0); // $50 limit
if (status.blocked) throw new Error('Budget exceeded');

// Detect loops
const result = detectLoopByHash(recentHashes, currentHash);
if (result.isLoop) throw new Error('Loop detected');
```

## Python SDK

```bash
pip install reivo-guard
```

```python
from reivo_guard import Guard

guard = Guard(budget_limit_usd=50.0)
decision = guard.before(messages=[{"role": "user", "content": "Hello"}])
if decision.allowed:
    response = llm_call(messages)
    guard.after(cost_usd=0.003)
```

See [`packages/guard-python`](../guard-python/) for LiteLLM, LangChain, and LangGraph integrations.

## Features

| Feature | Description |
|---------|-------------|
| **Loop Detection** | Hash-match and TF-IDF cosine similarity detect when agents get stuck repeating prompts |
| **Budget Enforcement** | Per-user, per-agent, per-session budget limits with configurable actions |
| **Quality Verification** | Logprob-based scoring (OpenAI, Gemini) + LLM-as-Judge (Anthropic) |
| **Graceful Degradation** | Progressive restrictions: aggressive routing (80%), block new sessions (95%), full block (100%) |
| **Session Management** | Per-session cost, quality trends, model usage tracking. Auto-upgrade on quality degradation |
| **Anomaly Detection** | EWMA-based spike detection for unusual token consumption |

## Architecture

```
guard.before()     →  Budget check, loop detection, session validation
       ↓
    LLM API call
       ↓
guard.after()      →  Cost tracking, quality verification, trend analysis
```

All guard functions are pure and stateless — state lives in the GuardStore. Works in serverless environments (Cloudflare Workers, AWS Lambda) or as a library in any Node.js application.

---

## API Reference

### GuardStore Interface

All state operations use a simple key-value store. Cloudflare KV is structurally compatible — no adapter needed.

```typescript
interface GuardStore {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
}

// For testing:
import { createMemoryStore } from 'reivo-guard';
const store = createMemoryStore();
```

### Budget

```typescript
import { getBudgetState, checkBudget, addCost, getDegradationLevel } from 'reivo-guard';
```

#### `getBudgetState(store, userId) → Promise<BudgetState>`

Read current budget state from store.

| Parameter | Type | Description |
|-----------|------|-------------|
| `store` | `GuardStore` | Key-value store |
| `userId` | `string` | User identifier |

Returns `BudgetState`: `{ usedUsd: number, blockedUntil: number | null, lastAlertThreshold: number }`

#### `checkBudget(state, limitUsd) → BudgetStatus`

Check if budget is exceeded.

| Parameter | Type | Description |
|-----------|------|-------------|
| `state` | `BudgetState` | Current budget state |
| `limitUsd` | `number` | Budget limit in USD |

Returns `{ blocked: boolean, usedUsd: number, remainingUsd: number, limitUsd: number }`

#### `addCost(store, userId, costUsd) → Promise<BudgetState>`

Add cost to user's budget.

| Parameter | Type | Description |
|-----------|------|-------------|
| `store` | `GuardStore` | Key-value store |
| `userId` | `string` | User identifier |
| `costUsd` | `number` | Cost in USD (must be finite, non-negative) |

#### `getDegradationLevel(usedUsd, limitUsd) → DegradationPolicy`

Get progressive degradation level based on budget usage.

| Parameter | Type | Description |
|-----------|------|-------------|
| `usedUsd` | `number` | Current spend |
| `limitUsd` | `number` | Budget limit |

Returns `DegradationPolicy`:

| `usageRatio` | `level` | `forceAggressiveRouting` | `blockNewSessions` | `blockAll` |
|---|---|---|---|---|
| < 0.8 | `normal` | false | false | false |
| 0.8–0.95 | `aggressive` | true | false | false |
| 0.95–1.0 | `new_sessions_only` | true | true | false |
| >= 1.0 | `blocked` | true | true | true |

### Loop Detection

```typescript
import { detectLoopByHash, detectLoopByCosine } from 'reivo-guard';
```

#### `detectLoopByHash(hashHistory, currentHash, threshold?) → LoopResult`

Detect loops by counting identical hashes in recent history.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hashHistory` | `string[]` | — | Recent prompt hashes |
| `currentHash` | `string` | — | Hash of current prompt |
| `threshold` | `number` | `3` | Match count to trigger |

Returns `{ isLoop: boolean, matchCount: number }`

#### `detectLoopByCosine(texts, currentText, threshold?) → CosineResult`

Detect loops by TF-IDF cosine similarity.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `texts` | `string[]` | — | Recent prompt texts |
| `currentText` | `string` | — | Current prompt text |
| `threshold` | `number` | `0.95` | Similarity threshold |

Returns `{ isLoop: boolean, similarity: number }`

### Quality Verification

```typescript
import { assessQuality, buildJudgePrompt, parseJudgeResponse } from 'reivo-guard';
```

#### `assessQuality(response, provider) → QualityAssessment`

Assess response quality using logprobs.

| Parameter | Type | Description |
|-----------|------|-------------|
| `response` | `unknown` | Parsed API response body |
| `provider` | `'openai' \| 'google'` | Provider format |

Returns `{ score: number, shouldFallback: boolean, meanLogprob: number, reason: string }`

#### `buildJudgePrompt(input) → OpenAIRequest`

Build a GPT-4o-mini prompt to judge response quality (for Anthropic responses without logprobs).

| Parameter | Type | Description |
|-----------|------|-------------|
| `input.prompt` | `string` | Original user prompt |
| `input.response` | `string` | Model response text |
| `input.model` | `string` | Model that generated response |

Returns `{ model: string, messages: Array<{role, content}>, max_tokens: number, temperature: number }`

#### `parseJudgeResponse(text) → JudgeResult`

Parse the judge model's JSON response.

Returns `{ score: number, shouldFallback: boolean, reason: string }`

### Session Tracking

```typescript
import { trackRequest, blockSession, getSessionMetrics } from 'reivo-guard';
```

#### `trackRequest(store, sessionId, userId, input) → Promise<SessionState>`

Record a request in a session.

| Parameter | Type | Description |
|-----------|------|-------------|
| `store` | `GuardStore` | Key-value store |
| `sessionId` | `string` | Session identifier |
| `userId` | `string` | User identifier |
| `input.costUsd` | `number` | Request cost |
| `input.model` | `string` | Model used |
| `input.qualityScore` | `number` | Quality score (0–1) |

#### `blockSession(store, sessionId, reason) → Promise<void>`

Force-stop a session.

#### `getSessionMetrics(session) → SessionMetrics`

Get aggregated session metrics.

Returns `{ requestCount, totalCostUsd, avgQualityScore, ... }`

### Quality Trend Detection

```typescript
import { detectQualityTrend } from 'reivo-guard';
```

#### `detectQualityTrend(scores) → QualityTrend`

Detect quality degradation from recent scores.

Returns `{ trend: 'stable' | 'degrading' | 'improving', shouldUpgrade: boolean, delta: number }`

### Anomaly Detection

```typescript
import { initEwmaState, updateEwma, detectAnomaly } from 'reivo-guard';
```

#### `detectAnomaly(state, value, zThreshold?) → { isAnomaly, zScore }`

EWMA-based spike detection.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `state` | `EwmaState` | — | Current EWMA state |
| `value` | `number` | — | New observation |
| `zThreshold` | `number` | `3.0` | Z-score threshold |

---

## Self-Hosted Proxy

Use `reivo-guard` as a standalone proxy between your agents and LLM providers:

```
Agent → Reivo Proxy → OpenAI / Anthropic / Google
                ↓
        Budget + Loop + Quality checks
```

Set `OPENAI_BASE_URL=https://your-proxy/openai/v1` and every request is automatically guarded.

## License

MIT
