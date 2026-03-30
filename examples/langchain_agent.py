"""LangChain / LangGraph integration — budget-aware agents.

pip install reivo-guard[langchain] langchain-openai
export OPENAI_API_KEY=sk-...
python examples/langchain_agent.py
"""

from langchain_openai import ChatOpenAI
from reivo_guard.langchain import ReivoCallbackHandler
from reivo_guard import BudgetExceeded, LoopDetected

# Create handler with $5 budget
handler = ReivoCallbackHandler(
    budget_limit_usd=5.0,
    loop_threshold=3,
    raise_on_block=True,
    default_model="gpt-4o-mini",
)

# Attach to any LangChain LLM
llm = ChatOpenAI(model="gpt-4o-mini", callbacks=[handler])


def main():
    questions = [
        "What is the capital of France?",
        "Explain quantum computing in one sentence.",
        "What is 42 * 42?",
    ]

    for q in questions:
        try:
            response = llm.invoke(q)
            print(f"Q: {q}")
            print(f"A: {response.content}")
            print(f"   Cost: ${handler.stats['budget_used_usd']:.6f}")
            print()
        except BudgetExceeded as e:
            print(f"Budget exceeded: ${e.used:.4f} / ${e.limit:.2f}")
            break
        except LoopDetected as e:
            print(f"Loop detected: {e.match_count} repeats")
            break

    print(f"Final stats: {handler.stats}")


if __name__ == "__main__":
    main()
