# reivo-guard

Open-source guardrails that auto-kill runaway AI agents.

> A developer's autonomous agent ran up a **$47,000 bill overnight**. `reivo-guard` prevents this.

[![TypeScript CI](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci.yml)
[![Python CI](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci-python.yml/badge.svg)](https://github.com/tazsat0512/reivo-guard/actions/workflows/ci-python.yml)

## Packages

| Package | Language | Install | Status |
|---------|----------|---------|--------|
| [`ts/`](./ts/) | TypeScript | `npm install reivo-guard` | [![npm](https://img.shields.io/npm/v/reivo-guard)](https://www.npmjs.com/package/reivo-guard) |
| [`python/`](./python/) | Python | `pip install reivo-guard` | [![PyPI](https://img.shields.io/pypi/v/reivo-guard)](https://pypi.org/project/reivo-guard/) |

## Features

| Feature | TypeScript | Python |
|---------|-----------|--------|
| Budget enforcement | Per-user, per-agent, per-session | Per-instance cumulative |
| Loop detection (hash) | SHA-256 window match | SHA-256 window match |
| Loop detection (semantic) | TF-IDF cosine similarity | — |
| Quality verification | Logprobs (OpenAI/Gemini) + LLM-as-Judge (Anthropic) | — |
| Graceful degradation | 4-level progressive | — |
| Session tracking | Cost, quality trends, auto-upgrade | — |
| Anomaly detection | EWMA z-score | — |
| Cost estimation | — | Built-in pricing table (25 models) |
| LiteLLM integration | — | 1-line callback |
| LangChain/LangGraph | — | BaseCallbackHandler |

## Quick Start

### TypeScript

```typescript
import { checkBudget, getBudgetState, detectLoopByHash } from 'reivo-guard';

const state = await getBudgetState(store, userId);
const status = checkBudget(state, 50.0);
if (status.blocked) throw new Error('Budget exceeded');
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

## Architecture

```
guard.before()     →  Budget check, loop detection, session validation
       ↓
    LLM API call
       ↓
guard.after()      →  Cost tracking, quality verification, trend analysis
```

All functions are pure and stateless — state lives in a simple key-value store interface (`GuardStore`). Works in serverless (Cloudflare Workers, Lambda) or as a library.

## Development

```bash
# TypeScript
cd ts && npm install && npm test

# Python
cd python && pip install -e ".[dev]" && pytest
```

## License

MIT
