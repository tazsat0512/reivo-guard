"""LangChain / LangGraph callback handler for Reivo guardrails.

Usage:
    from reivo_guard.langchain import ReivoCallbackHandler

    handler = ReivoCallbackHandler(budget_limit_usd=10.0)
    llm = ChatOpenAI(callbacks=[handler])
    # or
    chain.invoke({"input": "..."}, config={"callbacks": [handler]})
"""

from __future__ import annotations

from typing import Any, Optional, Sequence
from uuid import UUID

from .standalone import Guard, GuardDecision, estimate_cost

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.messages import BaseMessage
    from langchain_core.outputs import LLMResult
except ImportError as e:
    raise ImportError(
        "langchain-core is required for ReivoCallbackHandler. "
        "Install with: pip install reivo-guard[langchain]"
    ) from e


class ReivoCallbackHandler(BaseCallbackHandler):
    """LangChain callback that enforces budget limits and detects loops.

    Works with LangChain, LangGraph, and any framework using
    ``BaseCallbackHandler``.

    Args:
        budget_limit_usd: Maximum cumulative spend in USD. None = unlimited.
        loop_window: Number of recent requests to check for loops.
        loop_threshold: Number of identical prompts to trigger loop detection.
        raise_on_block: Raise exceptions when blocked. Default True.
        default_model: Model name for cost estimation when not available
            from LLM output metadata.
    """

    def __init__(
        self,
        budget_limit_usd: Optional[float] = None,
        loop_window: int = 20,
        loop_threshold: int = 3,
        raise_on_block: bool = True,
        default_model: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._guard = Guard(
            budget_limit_usd=budget_limit_usd,
            loop_window=loop_window,
            loop_threshold=loop_threshold,
            raise_on_block=raise_on_block,
        )
        self._default_model = default_model

    # ── LangChain hooks ───────────────────────────────────────────

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called before a chat model call. Checks budget and loops."""
        # Convert messages to serializable form for hashing
        flat: list[dict[str, str]] = []
        for batch in messages:
            for msg in batch:
                flat.append({"role": msg.type, "content": str(msg.content)})

        self._guard.before(messages=flat)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called after an LLM response. Tracks cost."""
        cost = 0.0
        model = self._default_model
        input_tokens = 0
        output_tokens = 0

        # Try to extract token usage from LLMResult
        llm_output = response.llm_output or {}

        # LiteLLM / OpenAI style
        token_usage = llm_output.get("token_usage", {})
        if token_usage:
            input_tokens = token_usage.get("prompt_tokens", 0) or 0
            output_tokens = token_usage.get("completion_tokens", 0) or 0

        if llm_output.get("model_name"):
            model = llm_output["model_name"]

        # Try AIMessage.usage_metadata (langchain-core >=0.2)
        if input_tokens == 0 and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg is not None:
                        usage = getattr(msg, "usage_metadata", None)
                        if usage and isinstance(usage, dict):
                            input_tokens = usage.get("input_tokens", 0) or 0
                            output_tokens = usage.get("output_tokens", 0) or 0
                            break
                if input_tokens > 0:
                    break

        self._guard.after(
            cost_usd=cost,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Called on LLM error. Counts the request."""
        self._guard.total_requests += 1

    # ── Utility ───────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, Any]:
        """Return current guard statistics."""
        return self._guard.stats

    def reset(self) -> None:
        """Reset all state."""
        self._guard.reset()
