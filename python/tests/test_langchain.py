"""Tests for the LangChain callback handler.

These tests mock langchain_core to avoid requiring it as a hard dependency.
"""

import sys
import types
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import MagicMock
from uuid import uuid4

import pytest


# ── Mock langchain_core before importing reivo_guard.langchain ──────


class _FakeBaseCallbackHandler:
    def __init__(self):
        pass


class _FakeBaseMessage:
    def __init__(self, type: str, content: str):
        self.type = type
        self.content = content


@dataclass
class _FakeGeneration:
    text: str
    message: Any = None


@dataclass
class _FakeLLMResult:
    generations: list[list[Any]]
    llm_output: Optional[dict[str, Any]] = None


def _install_mock_langchain():
    """Install mock langchain_core modules into sys.modules."""
    callbacks_mod = types.ModuleType("langchain_core.callbacks")
    callbacks_mod.BaseCallbackHandler = _FakeBaseCallbackHandler

    messages_mod = types.ModuleType("langchain_core.messages")
    messages_mod.BaseMessage = _FakeBaseMessage

    outputs_mod = types.ModuleType("langchain_core.outputs")
    outputs_mod.LLMResult = _FakeLLMResult

    core_mod = types.ModuleType("langchain_core")
    core_mod.callbacks = callbacks_mod
    core_mod.messages = messages_mod
    core_mod.outputs = outputs_mod

    sys.modules["langchain_core"] = core_mod
    sys.modules["langchain_core.callbacks"] = callbacks_mod
    sys.modules["langchain_core.messages"] = messages_mod
    sys.modules["langchain_core.outputs"] = outputs_mod


_install_mock_langchain()

# Now safe to import
from reivo_guard.langchain import ReivoCallbackHandler
from reivo_guard import BudgetExceeded, LoopDetected


class TestLangChainHandler:
    def _make_messages(self, content: str = "Hello"):
        return [[_FakeBaseMessage(type="human", content=content)]]

    def _make_llm_result(
        self,
        model_name: str = "gpt-4o-mini",
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
    ) -> _FakeLLMResult:
        return _FakeLLMResult(
            generations=[[_FakeGeneration(text="response")]],
            llm_output={
                "token_usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                },
                "model_name": model_name,
            },
        )

    def test_allows_normal_request(self):
        h = ReivoCallbackHandler(budget_limit_usd=10.0)
        # Should not raise
        h.on_chat_model_start({}, self._make_messages(), run_id=uuid4())

    def test_tracks_cost_from_tokens(self):
        h = ReivoCallbackHandler(budget_limit_usd=10.0, default_model="gpt-4o-mini")
        h.on_chat_model_start({}, self._make_messages(), run_id=uuid4())
        h.on_llm_end(self._make_llm_result(), run_id=uuid4())
        assert h.stats["total_requests"] == 1
        assert h.stats["total_cost_usd"] > 0

    def test_blocks_on_budget(self):
        h = ReivoCallbackHandler(budget_limit_usd=0.001, raise_on_block=True)
        # Simulate spending
        h.on_llm_end(
            self._make_llm_result(prompt_tokens=100000, completion_tokens=100000),
            run_id=uuid4(),
        )
        with pytest.raises(BudgetExceeded):
            h.on_chat_model_start({}, self._make_messages(), run_id=uuid4())

    def test_blocks_on_loop(self):
        h = ReivoCallbackHandler(loop_threshold=2, raise_on_block=True)
        msgs = self._make_messages("same thing")
        h.on_chat_model_start({}, msgs, run_id=uuid4())
        with pytest.raises(LoopDetected):
            h.on_chat_model_start({}, msgs, run_id=uuid4())

    def test_different_messages_no_loop(self):
        h = ReivoCallbackHandler(loop_threshold=2, raise_on_block=True)
        h.on_chat_model_start({}, self._make_messages("msg1"), run_id=uuid4())
        h.on_chat_model_start({}, self._make_messages("msg2"), run_id=uuid4())
        h.on_chat_model_start({}, self._make_messages("msg3"), run_id=uuid4())
        # No exception

    def test_on_llm_error_counts_request(self):
        h = ReivoCallbackHandler()
        h.on_llm_error(RuntimeError("fail"), run_id=uuid4())
        assert h.stats["total_requests"] == 1

    def test_stats_and_reset(self):
        h = ReivoCallbackHandler(budget_limit_usd=100.0)
        h.on_chat_model_start({}, self._make_messages(), run_id=uuid4())
        h.on_llm_end(self._make_llm_result(), run_id=uuid4())
        assert h.stats["total_requests"] == 1
        h.reset()
        assert h.stats["total_requests"] == 0

    def test_no_raise_mode(self):
        h = ReivoCallbackHandler(budget_limit_usd=0.0001, raise_on_block=False)
        h.on_llm_end(
            self._make_llm_result(prompt_tokens=100000, completion_tokens=100000),
            run_id=uuid4(),
        )
        # Should not raise, just silently block
        h.on_chat_model_start({}, self._make_messages(), run_id=uuid4())

    def test_usage_metadata_fallback(self):
        """Test extraction from AIMessage.usage_metadata when llm_output is empty."""
        msg = MagicMock()
        msg.usage_metadata = {"input_tokens": 200, "output_tokens": 100}
        gen = _FakeGeneration(text="response", message=msg)
        result = _FakeLLMResult(
            generations=[[gen]],
            llm_output={"model_name": "gpt-4o-mini"},
        )
        h = ReivoCallbackHandler(budget_limit_usd=10.0)
        h.on_llm_end(result, run_id=uuid4())
        assert h.stats["total_cost_usd"] > 0
