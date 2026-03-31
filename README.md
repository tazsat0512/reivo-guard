# reivo-guard

Open-source guardrails that auto-stop runaway AI agents.

> Runaway AI agents can burn through **thousands of dollars in hours**. `reivo-guard` prevents this.

[![TypeScript CI](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci.yml)
[![Python CI](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci-python.yml/badge.svg)](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci-python.yml)

## Try It

```bash
npx reivo-guard-demo
```

<details>
<summary>Demo output (click to expand)</summary>

```
▸ Budget Enforcement
  Simulating an agent spending against a $10 budget...

  ✓ Request $2.50 → allowed   [█████░░░░░░░░░░░░░░░]  $2.50/$10.00
  ✓ Request $3.00 → allowed   [███████████░░░░░░░░░]  $5.50/$10.00
  ✓ Request $2.00 → allowed   [███████████████░░░░░]  $7.50/$10.00
  ✓ Request $1.50 → allowed   [██████████████████░░]  $9.00/$10.00
  ✗ Request $1.50 → BLOCKED   [████████████████████]  $10.50/$10.00

▸ Graceful Degradation
  50% used → normal      (aggressive=false, blockNew=false, blockAll=false)
  85% used → aggressive  (aggressive=true,  blockNew=false, blockAll=false)
  96% used → new_sessions_only  (blockNew=true)
 100% used → blocked     (blockAll=true)

▸ Loop Detection (Hash Match)
  ✓ "What is Python?"    → ok (1/5 matches)
  ✓ "Explain decorators" → ok (1/5 matches)
  ✓ "What is Python?"    → ok (2/5 matches)
  ✓ "What is Python?"    → ok (3/5 matches)
  ✗ "What is Python?"    → LOOP DETECTED (5 matches)

▸ Anomaly Detection (EWMA)
  ✓ 101 tokens/req → normal  (z-score=0.25)
  ✓  99 tokens/req → normal  (z-score=-1.61)
  ✓ 100 tokens/req → normal  (z-score=0.04)
  ✗ 800 tokens/req → ANOMALY (z-score=499.40)

▸ Performance
  ✓ checkBudget()          ~70 ns per call
  ✓ detectLoopByHash()    ~200 ns per call
  ✓ getDegradationLevel()  ~25 ns per call
```

</details>

## Packages

| Package | Language | Install | Status |
|---------|----------|---------|--------|
| [`ts/`](./ts/) | TypeScript | `npm install reivo-guard` | [![npm](https://img.shields.io/npm/v/reivo-guard)](https://www.npmjs.com/package/reivo-guard) |
| [`python/`](./python/) | Python | `pip install reivo-guard` | [![PyPI](https://img.shields.io/pypi/v/reivo-guard)](https://pypi.org/project/reivo-guard/) |

## Features

| Feature | TypeScript | Python |
|---------|-----------|--------|
| **Guard class** (before/after) | `new Guard({ budgetLimitUsd: 50 })` | `Guard(budget_limit_usd=50)` |
| Budget enforcement | Per-user, per-agent, per-session | Per-instance cumulative |
| Loop detection (hash) | SHA-256 window match | SHA-256 window match |
| Loop detection (semantic) | TF-IDF cosine similarity | TF-IDF cosine similarity |
| Quality verification | Logprobs (OpenAI/Gemini) + LLM-as-Judge (Anthropic) | — |
| Graceful degradation | 4-level progressive | 4-level progressive |
| Session tracking | Cost, quality trends, auto-upgrade | — |
| Anomaly detection | EWMA z-score (abs + warmup) | EWMA z-score (abs + warmup) |
| Rate limiting | Sliding window | Sliding window |
| Cost estimation | Built-in pricing table (20 models) | Built-in pricing table (20 models) |
| Sequence pattern detection | — | N-gram cycle detection |
| CUSUM drift detection | — | Page's algorithm with auto-threshold |
| Budget exhaustion forecasting | — | OLS regression with 95% CI |
| LiteLLM integration | — | 1-line callback |
| LangChain/LangGraph | — | BaseCallbackHandler |
| CrewAI | — | step_callback |

## Quick Start

### TypeScript

```typescript
import { Guard } from 'reivo-guard';

const guard = new Guard({ budgetLimitUsd: 50.0, loopThreshold: 5 });

const decision = guard.before({ messages: [{ role: 'user', content: 'Hello' }] });
if (!decision.allowed) throw new Error(decision.reason);
const response = await callLlm(messages);
guard.after({ costUsd: 0.003 });
// or: guard.after({ model: 'gpt-4o-mini', inputTokens: 100, outputTokens: 50 });
```

### Python

```python
from reivo_guard import Guard

guard = Guard(budget_limit_usd=50.0)
decision = guard.before(messages=[{"role": "user", "content": "Hello"}])
if decision.allowed:
    response = llm_call(messages)
    guard.after(cost_usd=0.003)
```

### LiteLLM (1 line)

```python
import litellm
from reivo_guard import ReivoGuard

litellm.callbacks = [ReivoGuard(budget_limit_usd=50.0)]
```

### LangChain / LangGraph

```python
from reivo_guard.langchain import ReivoCallbackHandler

handler = ReivoCallbackHandler(budget_limit_usd=10.0, default_model="gpt-4o")
llm = ChatOpenAI(model="gpt-4o", callbacks=[handler])
```

## Performance

All guard checks run in **nanoseconds** — zero measurable overhead vs. LLM API latency.

| Operation | TypeScript | Python |
|-----------|-----------|--------|
| `guard.before()` | ~0.5 µs | ~2.5 µs |
| `guard.after()` | ~0.1 µs | ~0.3 µs |
| `checkBudget()` | ~70 ns | — |
| `detectLoopByHash()` | ~200 ns | — |
| `getDegradationLevel()` | ~25 ns | — |

Benchmarked on Apple M3, 100K iterations. See [`bench/`](./bench/).

## Architecture

```
guard.before()     →  Budget check, loop detection, session validation
       ↓
    LLM API call
       ↓
guard.after()      →  Cost tracking, quality verification, trend analysis
```

Guard functions are side-effect-free on the hot path — state lives in a simple key-value store interface (`GuardStore`). Works in serverless (Cloudflare Workers, Lambda) or as a library.

## Blog Post

[How I Built Open-Source Guardrails That Auto-Stop Runaway AI Agents](https://dev.to/tazsat0512/how-i-built-open-source-guardrails-that-auto-stop-runaway-ai-agents-249m) — architecture deep-dive on DEV.to.

## Managed Cloud

Want managed guardrails + smart model routing + dashboard? [reivo.dev](https://reivo.dev) runs reivo-guard as a drop-in proxy — change your base URL and it works.

## Development

```bash
# TypeScript
cd ts && npm install && npm test

# Python
cd python && pip install -e ".[dev]" && pytest
```

## License

MIT
