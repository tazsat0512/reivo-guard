# reivo-guard

Open-source guardrails for AI agents — Python SDK.

> A developer's autonomous agent ran up a **$47,000 bill overnight**. `reivo-guard` prevents this.

## Install

```bash
pip install reivo-guard

# Optional integrations
pip install reivo-guard[litellm]    # LiteLLM callback
pip install reivo-guard[langchain]  # LangChain / LangGraph handler
```

**Requirements**: Python >= 3.9. Core library has zero dependencies.

---

## Quick Start

### Standalone Guard (any framework)

```python
from reivo_guard import Guard

guard = Guard(budget_limit_usd=50.0, loop_threshold=3)

messages = [{"role": "user", "content": "Hello"}]

decision = guard.before(messages=messages)
if not decision.allowed:
    print(f"Blocked: {decision.reason}")
else:
    response = your_llm_call(messages)
    guard.after(cost_usd=0.003)
    # or estimate from tokens:
    # guard.after(model="gpt-4o", input_tokens=100, output_tokens=50)
```

### LiteLLM (1 line)

```python
import litellm
from reivo_guard import ReivoGuard

litellm.callbacks = [ReivoGuard(budget_limit_usd=50.0)]

response = litellm.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

### LangChain / LangGraph

```python
from langchain_openai import ChatOpenAI
from reivo_guard.langchain import ReivoCallbackHandler

handler = ReivoCallbackHandler(budget_limit_usd=10.0, default_model="gpt-4o")
llm = ChatOpenAI(model="gpt-4o", callbacks=[handler])
response = llm.invoke("What is 2+2?")
```

Works with LangGraph agents, chains, and any component that accepts callbacks.

---

## API Reference

### `Guard` class

Framework-agnostic guardrail with before/after pattern.

```python
from reivo_guard import Guard
```

#### Constructor

```python
Guard(
    budget_limit_usd: float | None = None,  # None = unlimited
    loop_window: int = 20,                   # recent requests to check
    loop_threshold: int = 3,                 # identical prompts to trigger (>= 2)
    raise_on_block: bool = False,            # raise exceptions instead of returning decision
)
```

| Parameter | Type | Default | Constraints |
|-----------|------|---------|-------------|
| `budget_limit_usd` | `float \| None` | `None` | Must be > 0 or None |
| `loop_window` | `int` | `20` | Must be >= 1 |
| `loop_threshold` | `int` | `3` | Must be >= 2 |
| `raise_on_block` | `bool` | `False` | — |

#### `guard.before(messages=None, prompt_hash=None) → GuardDecision`

Check budget and loop before an LLM call. Provide either `messages` (auto-hashed) or a pre-computed `prompt_hash`. If neither is given, only budget check runs.

```python
@dataclass
class GuardDecision:
    allowed: bool
    reason: str | None = None
    budget_used_usd: float = 0.0
    budget_remaining_usd: float | None = None
```

When `raise_on_block=True`, raises `BudgetExceeded` or `LoopDetected` instead of returning a blocked decision.

#### `guard.after(cost_usd=0.0, model=None, input_tokens=0, output_tokens=0)`

Record cost after an LLM call. If `cost_usd` is 0 and token counts are provided, cost is estimated from the built-in pricing table.

| Parameter | Type | Description |
|-----------|------|-------------|
| `cost_usd` | `float` | Direct cost. NaN/Inf/negative silently ignored |
| `model` | `str \| None` | Model name for cost estimation |
| `input_tokens` | `int` | Input token count |
| `output_tokens` | `int` | Output token count |

#### `guard.stats → dict`

```python
{
    "total_requests": 42,
    "total_cost_usd": 3.14,
    "budget_used_usd": 3.14,
    "budget_limit_usd": 100.0,
    "budget_remaining_usd": 96.86,
    "blocked_requests": 0,
}
```

#### `guard.reset()`

Reset all state (counters, budget, loop history).

---

### `ReivoGuard` class (LiteLLM)

LiteLLM callback. Internally uses `Guard`.

```python
from reivo_guard import ReivoGuard
```

#### Constructor

```python
ReivoGuard(
    budget_limit_usd: float | None = None,
    loop_window: int = 20,
    loop_threshold: int = 3,
    on_budget_exceeded: Callable[[float, float], None] | None = None,
    on_loop_detected: Callable[[int, int], None] | None = None,
)
```

When no callback is provided, raises `BudgetExceeded` / `LoopDetected` by default.

#### Custom callbacks

```python
def on_budget(used, limit):
    print(f"Warning: ${used:.2f} / ${limit:.2f}")

def on_loop(count, window):
    slack.post(f"Loop: {count} repeats in {window} requests")

guard = ReivoGuard(
    budget_limit_usd=100.0,
    on_budget_exceeded=on_budget,
    on_loop_detected=on_loop,
)
```

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `stats` | `dict` | Same format as `Guard.stats` |
| `total_requests` | `int` | Total requests processed |
| `total_cost_usd` | `float` | Cumulative cost |
| `blocked_requests` | `int` | Requests blocked by guards |

---

### `ReivoCallbackHandler` class (LangChain)

LangChain `BaseCallbackHandler`. Works with LangChain, LangGraph, and any framework using the callback protocol.

```python
from reivo_guard.langchain import ReivoCallbackHandler
```

#### Constructor

```python
ReivoCallbackHandler(
    budget_limit_usd: float | None = None,
    loop_window: int = 20,
    loop_threshold: int = 3,
    raise_on_block: bool = True,
    default_model: str | None = None,  # for cost estimation
)
```

**Cost estimation**: Uses token counts from `LLMResult.llm_output["token_usage"]` or `AIMessage.usage_metadata`, combined with the model name, to estimate cost via the built-in pricing table.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `stats` | `dict` | Same format as `Guard.stats` |

---

### `estimate_cost(model, input_tokens, output_tokens) → float`

Estimate cost in USD from token counts. Returns 0.0 for unknown models.

```python
from reivo_guard import estimate_cost

cost = estimate_cost("gpt-4o", input_tokens=1000, output_tokens=500)
# → 0.0075
```

#### Supported models

| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|---------------|
| gpt-4o | 2.50 | 10.00 |
| gpt-4o-mini | 0.15 | 0.60 |
| gpt-4-turbo | 10.00 | 30.00 |
| gpt-4 | 30.00 | 60.00 |
| gpt-3.5-turbo | 0.50 | 1.50 |
| o1 | 15.00 | 60.00 |
| o1-mini | 3.00 | 12.00 |
| o3-mini | 1.10 | 4.40 |
| claude-3-5-sonnet-20241022 | 3.00 | 15.00 |
| claude-3-5-haiku-20241022 | 0.80 | 4.00 |
| claude-3-opus-20240229 | 15.00 | 75.00 |
| claude-sonnet-4-20250514 | 3.00 | 15.00 |
| claude-opus-4-20250514 | 15.00 | 75.00 |
| gemini-1.5-pro | 1.25 | 5.00 |
| gemini-1.5-flash | 0.075 | 0.30 |
| gemini-2.0-flash | 0.10 | 0.40 |

Model names with date suffixes (e.g., `gpt-4o-mini-2024-07-18`) are matched by longest prefix.

---

### Exceptions

```python
from reivo_guard import BudgetExceeded, LoopDetected
```

#### `BudgetExceeded`

| Attribute | Type | Description |
|-----------|------|-------------|
| `used` | `float` | Amount spent in USD |
| `limit` | `float` | Budget limit in USD |

#### `LoopDetected`

| Attribute | Type | Description |
|-----------|------|-------------|
| `match_count` | `int` | Number of identical prompts found |
| `window` | `int` | Window size checked |

---

### Pure functions

```python
from reivo_guard import detect_loop, check_budget, hash_messages
```

#### `detect_loop(hashes, current_hash, threshold=3) → tuple[bool, int]`

Check if `current_hash` appears >= `threshold` times in `hashes + [current_hash]`.

#### `check_budget(used_usd, limit_usd) → tuple[bool, float | None]`

Returns `(exceeded: bool, remaining_usd: float | None)`. `remaining` is None if no limit set.

#### `hash_messages(messages) → str`

SHA-256 hex digest of JSON-serialized messages.

---

## License

MIT
