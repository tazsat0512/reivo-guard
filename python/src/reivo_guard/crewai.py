"""CrewAI integration — use reivo-guard as a CrewAI step callback.

Usage:
    from crewai import Agent, Task, Crew
    from reivo_guard.crewai import ReivoCrewCallback

    callback = ReivoCrewCallback(budget_limit_usd=10.0)

    agent = Agent(
        role="Researcher",
        step_callback=callback,
        ...
    )
"""

from __future__ import annotations

from typing import Any, Optional

from .standalone import Guard, GuardDecision, estimate_cost


class ReivoCrewCallback:
    """CrewAI step_callback that enforces budget, loop, and rate limits.

    Pass as ``step_callback`` to a CrewAI Agent or Task.

    Args:
        budget_limit_usd: Maximum spend. None = unlimited.
        loop_window: Recent requests to check for loops.
        loop_threshold: Identical prompts to trigger loop detection.
        rate_limit: Max steps per rate_limit_window seconds. None = unlimited.
        rate_limit_window: Time window in seconds. Default 60.
        default_model: Model name for cost estimation when not available from output.
        on_block: Callback when a step is blocked. Receives GuardDecision.
    """

    def __init__(
        self,
        budget_limit_usd: Optional[float] = None,
        loop_window: int = 20,
        loop_threshold: int = 3,
        rate_limit: Optional[int] = None,
        rate_limit_window: float = 60.0,
        default_model: Optional[str] = None,
        on_block: Any = None,
    ) -> None:
        self._guard = Guard(
            budget_limit_usd=budget_limit_usd,
            loop_window=loop_window,
            loop_threshold=loop_threshold,
            rate_limit=rate_limit,
            rate_limit_window=rate_limit_window,
        )
        self._default_model = default_model
        self._on_block = on_block

    def __call__(self, step_output: Any) -> Any:
        """Called by CrewAI after each agent step.

        Extracts text from step output for loop detection,
        estimates cost, and checks all guards.
        """
        # Extract text for loop detection
        text = self._extract_text(step_output)
        messages = [{"role": "assistant", "content": text}] if text else None

        # Check guards
        decision = self._guard.before(messages=messages)

        if not decision.allowed:
            if self._on_block:
                self._on_block(decision)
            else:
                from .guard import BudgetExceeded, LoopDetected

                if "Budget" in (decision.reason or ""):
                    raise BudgetExceeded(
                        decision.budget_used_usd,
                        self._guard._budget.limit_usd or 0,
                    )
                elif "Loop" in (decision.reason or ""):
                    raise LoopDetected(0, 0)
                else:
                    raise RuntimeError(f"Guard blocked: {decision.reason}")

        # Estimate cost (CrewAI doesn't expose token counts directly)
        if self._default_model:
            # Rough estimation: ~4 chars per token
            estimated_tokens = len(text) // 4 if text else 0
            cost = estimate_cost(
                self._default_model,
                input_tokens=estimated_tokens,
                output_tokens=estimated_tokens,
            )
            self._guard.after(cost_usd=cost)
        else:
            self._guard.after()

        return step_output

    @staticmethod
    def _extract_text(step_output: Any) -> str:
        """Extract text from various CrewAI step output formats."""
        if isinstance(step_output, str):
            return step_output
        if hasattr(step_output, "text"):
            return str(step_output.text)
        if hasattr(step_output, "output"):
            return str(step_output.output)
        if hasattr(step_output, "result"):
            return str(step_output.result)
        return str(step_output)

    @property
    def guard(self) -> Guard:
        """Access the underlying Guard instance."""
        return self._guard

    @property
    def stats(self) -> dict:
        """Return current guard statistics."""
        return self._guard.stats
