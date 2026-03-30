"""Standalone Guard usage — no framework dependencies.

pip install reivo-guard
python examples/standalone.py
"""

from reivo_guard import Guard, BudgetExceeded, LoopDetected

# Create a guard with $10 budget and loop detection
guard = Guard(budget_limit_usd=10.0, loop_threshold=3, raise_on_block=True)


def fake_llm_call(messages: list[dict]) -> str:
    """Simulate an LLM call."""
    return f"Response to: {messages[-1]['content']}"


def run_agent():
    prompts = [
        "What is Python?",
        "Explain decorators",
        "What are generators?",
        "What are generators?",  # repeated
        "What are generators?",  # will trigger loop detection
    ]

    for prompt in prompts:
        messages = [{"role": "user", "content": prompt}]

        try:
            # Check before calling LLM
            decision = guard.before(messages=messages)
            print(f"[ALLOWED] {prompt}")

            # Call LLM
            response = fake_llm_call(messages)

            # Record cost after call
            guard.after(model="gpt-4o-mini", input_tokens=50, output_tokens=100)
            print(f"  → Cost so far: ${guard.stats['budget_used_usd']:.6f}")

        except BudgetExceeded as e:
            print(f"[BLOCKED] Budget exceeded: ${e.used:.4f} / ${e.limit:.2f}")
            break
        except LoopDetected as e:
            print(f"[BLOCKED] Loop detected: {e.match_count} identical prompts")
            break

    print(f"\nFinal stats: {guard.stats}")


if __name__ == "__main__":
    run_agent()
