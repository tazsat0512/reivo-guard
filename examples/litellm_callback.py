"""LiteLLM integration — 1 line to guard all LLM calls.

pip install reivo-guard[litellm]
export OPENAI_API_KEY=sk-...
python examples/litellm_callback.py
"""

import litellm
from reivo_guard import ReivoGuard

# One line to enable guardrails
guard = ReivoGuard(
    budget_limit_usd=1.0,
    loop_threshold=3,
)
litellm.callbacks = [guard]


def main():
    messages = [{"role": "user", "content": "What is 2+2?"}]

    try:
        response = litellm.completion(
            model="gpt-4o-mini",
            messages=messages,
        )
        print(f"Response: {response.choices[0].message.content}")
        print(f"Stats: {guard.stats}")

    except Exception as e:
        print(f"Error: {e}")
        print(f"Stats: {guard.stats}")


if __name__ == "__main__":
    main()
