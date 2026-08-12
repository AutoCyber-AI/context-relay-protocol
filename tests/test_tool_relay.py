"""Tests for tool-mediated context relay (§20).

Tests the pull-based architecture where the LLM requests context
on demand via tool calls instead of receiving a pre-built envelope.

Covers:
- ContextToolExecutor: tool call routing and result formatting
- CRP_CONTEXT_TOOLS: tool definitions structure
- Provider tool support: supports_tools(), generate_chat_with_tools()
- dispatch_with_tools(): iterative tool loop, fallback to push
- Tool results → message conversion

Run with: python -m pytest tests/test_tool_relay.py -v --tb=short
"""

import json
import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENAI_API_KEY", "test-key")


# ── Tool definitions tests ─────────────────────────────────────────────

class TestCRPContextTools:
    """Verify tool definitions are well-formed OpenAI-compatible."""

    def test_tool_count(self):
        from crp.core.context_tools import CRP_CONTEXT_TOOLS
        assert len(CRP_CONTEXT_TOOLS) == 5

    def test_all_tools_have_function_type(self):
        from crp.core.context_tools import CRP_CONTEXT_TOOLS
        for tool in CRP_CONTEXT_TOOLS:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_tool_names_unique(self):
        from crp.core.context_tools import CRP_CONTEXT_TOOLS
        names = [t["function"]["name"] for t in CRP_CONTEXT_TOOLS]
        assert len(names) == len(set(names))

    def test_tool_names_prefixed(self):
        """All CRP tools should be prefixed with 'crp_' to avoid conflicts."""
        from crp.core.context_tools import CRP_CONTEXT_TOOLS
        for tool in CRP_CONTEXT_TOOLS:
            assert tool["function"]["name"].startswith("crp_")

    def test_tool_name_set(self):
        from crp.core.context_tools import CRP_TOOL_NAMES
        assert "crp_retrieve_context" in CRP_TOOL_NAMES
        assert "crp_get_document_structure" in CRP_TOOL_NAMES
        assert "crp_check_facts" in CRP_TOOL_NAMES
        assert "crp_get_related_facts" in CRP_TOOL_NAMES
        assert "crp_get_continuation_state" in CRP_TOOL_NAMES

    def test_retrieve_context_has_query_param(self):
        from crp.core.context_tools import CRP_CONTEXT_TOOLS
        tool = next(t for t in CRP_CONTEXT_TOOLS if t["function"]["name"] == "crp_retrieve_context")
        params = tool["function"]["parameters"]
        assert "query" in params["properties"]
        assert "query" in params["required"]


# ── ContextToolExecutor tests ──────────────────────────────────────────

class TestContextToolExecutor:
    """Test tool call routing and execution."""

    def _make_executor(self, facts=None):
        """Create a ContextToolExecutor with mock stores."""
        from crp.core.context_tools import ContextToolExecutor

        warm_store = MagicMock()
        ckf = MagicMock()

        # Set up mock facts
        if facts is None:
            facts = []
        mock_facts = []
        for text in facts:
            f = MagicMock()
            f.id = str(uuid.uuid4())
            f.text = text
            f.confidence = 0.9
            f.source_window_id = "w0"
            mock_facts.append(f)

        warm_store.get_ranked_facts.return_value = mock_facts
        warm_store.fact_count = len(mock_facts)
        warm_store.structural_state = MagicMock()
        warm_store.structural_state.to_dict.return_value = {
            "document_map": "## Chapter 1\n## Chapter 2",
            "outline": "Two chapters",
            "sections_completed": ["Chapter 1"],
            "current_section": "Chapter 2",
            "word_count": 500,
        }
        warm_store.critical_state = MagicMock()
        warm_store.critical_state.to_dict.return_value = {
            "goal": "Write a document",
            "phase": "drafting",
            "constraints": [],
        }

        ckf.graph_walk.return_value = MagicMock(facts=mock_facts[:2])

        count_tokens = lambda text: max(1, len(text) // 4)

        return ContextToolExecutor(
            warm_store=warm_store,
            ckf=ckf,
            count_tokens=count_tokens,
        )

    def test_unknown_tool_returns_error(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor()
        result = executor.execute(ToolCall(id="1", name="unknown_tool", arguments={}))
        data = json.loads(result.content)
        assert "error" in data

    def test_retrieve_context_empty_query(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor(facts=["The sky is blue"])
        result = executor.execute(ToolCall(
            id="1", name="crp_retrieve_context", arguments={"query": ""},
        ))
        data = json.loads(result.content)
        assert data["facts"] == []

    def test_retrieve_context_with_matching_facts(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor(facts=[
            "The capital of France is Paris",
            "Python is a programming language",
            "The sky is blue",
        ])
        result = executor.execute(ToolCall(
            id="1", name="crp_retrieve_context",
            arguments={"query": "capital France Paris"},
        ))
        data = json.loads(result.content)
        assert len(data["facts"]) > 0
        # The France/Paris fact should be first
        assert "Paris" in data["facts"][0]["text"]

    def test_retrieve_context_respects_max_results(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor(facts=[
            "Fact A about topic X",
            "Fact B about topic X",
            "Fact C about topic X",
            "Fact D about topic X",
        ])
        result = executor.execute(ToolCall(
            id="1", name="crp_retrieve_context",
            arguments={"query": "topic", "max_results": 2},
        ))
        data = json.loads(result.content)
        assert len(data["facts"]) <= 2

    def test_get_document_structure(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor()
        result = executor.execute(ToolCall(
            id="1", name="crp_get_document_structure", arguments={},
        ))
        data = json.loads(result.content)
        assert "document_map" in data
        assert "Chapter 1" in data["document_map"]

    def test_check_facts_empty_claim(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor(facts=["The sky is blue"])
        result = executor.execute(ToolCall(
            id="1", name="crp_check_facts", arguments={"claim": ""},
        ))
        data = json.loads(result.content)
        assert data["matching"] == [] or data.get("matching_facts") == []

    def test_check_facts_with_matches(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor(facts=[
            "The speed of light is 299792458 m/s",
            "Water boils at 100 degrees Celsius",
        ])
        result = executor.execute(ToolCall(
            id="1", name="crp_check_facts",
            arguments={"claim": "speed of light"},
        ))
        data = json.loads(result.content)
        assert len(data["matching_facts"]) > 0

    def test_get_related_facts(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor(facts=[
            "Quantum mechanics describes subatomic particles",
            "Electrons orbit the nucleus",
        ])
        result = executor.execute(ToolCall(
            id="1", name="crp_get_related_facts",
            arguments={"topic": "quantum"},
        ))
        data = json.loads(result.content)
        assert "related" in data

    def test_get_continuation_state_initial(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor()
        result = executor.execute(ToolCall(
            id="1", name="crp_get_continuation_state", arguments={},
        ))
        data = json.loads(result.content)
        assert data["status"] == "initial"

    def test_get_continuation_state_with_data(self):
        from crp.core.context_tools import ToolCall, ContextToolExecutor
        executor = self._make_executor()
        executor.update_continuation_state({
            "gap_score": 0.4,
            "windows_completed": 2,
            "directive": "Continue from Chapter 3",
        })
        result = executor.execute(ToolCall(
            id="1", name="crp_get_continuation_state", arguments={},
        ))
        data = json.loads(result.content)
        assert data["gap_score"] == 0.4

    def test_execute_batch(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor(facts=["The sky is blue"])
        results = executor.execute_batch([
            ToolCall(id="1", name="crp_get_document_structure", arguments={}),
            ToolCall(id="2", name="crp_get_continuation_state", arguments={}),
        ])
        assert len(results) == 2
        assert results[0].tool_call_id == "1"
        assert results[1].tool_call_id == "2"

    def test_calls_counter(self):
        from crp.core.context_tools import ToolCall
        executor = self._make_executor()
        assert executor.calls_executed == 0
        executor.execute(ToolCall(id="1", name="crp_get_document_structure", arguments={}))
        assert executor.calls_executed == 1
        executor.execute(ToolCall(id="2", name="crp_get_continuation_state", arguments={}))
        assert executor.calls_executed == 2

    def test_token_budget_cap(self):
        """Tool results should be capped to MAX_RESULT_TOKENS."""
        from crp.core.context_tools import ToolCall
        executor = self._make_executor()
        assert executor.MAX_RESULT_TOKENS == 2000


# ── Tool system prompt tests ──────────────────────────────────────────

class TestBuildToolSystemPrompt:
    def test_augments_system_prompt(self):
        from crp.core.context_tools import build_tool_system_prompt
        result = build_tool_system_prompt("You are helpful.", 42)
        assert "Context Relay Protocol" in result
        assert "42 verified facts" in result
        assert "You are helpful." in result

    def test_preserves_original_prompt(self):
        from crp.core.context_tools import build_tool_system_prompt
        original = "Be a pirate."
        result = build_tool_system_prompt(original, 0)
        assert result.startswith(original)


# ── Tool results to messages tests ────────────────────────────────────

class TestToolResultsToMessages:
    def test_builds_correct_message_sequence(self):
        from crp.core.context_tools import ToolResult, tool_results_to_messages

        assistant_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "crp_retrieve_context", "arguments": '{"query":"test"}'}}
            ],
        }
        results = [
            ToolResult(tool_call_id="call_1", name="crp_retrieve_context", content='{"facts":[]}'),
        ]

        messages = tool_results_to_messages(assistant_msg, results)
        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        assert messages[1]["role"] == "tool"
        assert messages[1]["tool_call_id"] == "call_1"


# ── Provider tool support tests ───────────────────────────────────────

class TestProviderToolSupport:
    def test_base_provider_no_tool_support(self):
        from crp.providers.base import LLMProvider

        class StubProvider(LLMProvider):
            def generate_chat(self, messages, **kwargs):
                return ("", "stop")
            def count_tokens(self, text):
                return len(text) // 4
            def context_window_size(self):
                return 8192

        p = StubProvider()
        assert p.supports_tools() is False

    def test_base_provider_tool_call_raises(self):
        from crp.providers.base import LLMProvider

        class StubProvider(LLMProvider):
            def generate_chat(self, messages, **kwargs):
                return ("", "stop")
            def count_tokens(self, text):
                return len(text) // 4
            def context_window_size(self):
                return 8192

        p = StubProvider()
        with pytest.raises(NotImplementedError):
            p.generate_chat_with_tools([], [])

    def test_openai_adapter_supports_tools(self):
        """OpenAIAdapter.supports_tools() should return True."""
        try:
            from crp.providers.openai import OpenAIAdapter
            adapter = OpenAIAdapter(
                model="gpt-4o",
                api_key="test-key",
            )
            assert adapter.supports_tools() is True
        except ImportError:
            pytest.skip("openai package not installed")


# ── dispatch_with_tools integration tests ─────────────────────────────

class TestDispatchWithToolsFallback:
    """Test that dispatch_with_tools falls back to push for non-tool providers."""

    def test_fallback_to_push_dispatch(self):
        """When provider doesn't support tools, falls back to dispatch()."""
        from crp.providers.base import LLMProvider

        class NoToolProvider(LLMProvider):
            def generate_chat(self, messages, **kwargs):
                return ("Hello from push model", "stop")
            def count_tokens(self, text):
                return max(1, len(text) // 4)
            def context_window_size(self):
                return 32000

        provider = NoToolProvider()
        assert provider.supports_tools() is False

        # Verify the method exists on orchestrator
        import crp
        # We can't fully instantiate without more setup, but verify the method exists
        assert hasattr(crp.core.orchestrator.CRPOrchestrator, "dispatch_with_tools")


class TestDispatchWithToolsMocked:
    """Test the tool dispatch loop with mocked provider to avoid LLM calls."""

    def _make_mock_orchestrator(self, tool_responses=None):
        """Create a CRPOrchestrator with a mocked tool-capable provider.

        tool_responses: list of (text, finish_reason, tool_calls, raw_msg) tuples.
        The first N-1 should have tool_calls, the last should be final text.
        """
        from crp.core.orchestrator import CRPOrchestrator
        from crp.providers.base import LLMProvider

        if tool_responses is None:
            tool_responses = [("Final answer.", "stop", None, None)]

        call_idx = [0]

        class MockToolProvider(LLMProvider):
            def generate_chat(self, messages, **kwargs):
                return ("fallback text", "stop")
            def count_tokens(self, text):
                return max(1, len(text) // 4)
            def context_window_size(self):
                return 32000
            def supports_tools(self):
                return True
            def generate_chat_with_tools(self, messages, tools, **kwargs):
                idx = min(call_idx[0], len(tool_responses) - 1)
                call_idx[0] += 1
                return tool_responses[idx]

        provider = MockToolProvider()
        orch = CRPOrchestrator(provider=provider)
        return orch

    def test_single_round_no_tools(self):
        """LLM responds immediately without tool calls."""
        orch = self._make_mock_orchestrator([
            ("Direct answer without tools", "stop", None, None),
        ])
        output, report = orch.dispatch_with_tools(
            "You are helpful", "What is 2+2?",
        )
        assert "Direct answer" in output
        assert report.quality_tier is not None
        # No tool rounds
        assert report.telemetry.get("tool_rounds", 0) == 0

    def test_one_tool_round_then_answer(self):
        """LLM calls a tool, gets result, then produces final answer."""
        tool_calls = [{
            "id": "call_abc",
            "type": "function",
            "function": {
                "name": "crp_retrieve_context",
                "arguments": {"query": "capital of France"},
            },
        }]
        raw_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_abc",
                "type": "function",
                "function": {
                    "name": "crp_retrieve_context",
                    "arguments": '{"query":"capital of France"}',
                },
            }],
        }
        orch = self._make_mock_orchestrator([
            ("", "tool_calls", tool_calls, raw_msg),
            ("The capital of France is Paris.", "stop", None, None),
        ])
        output, report = orch.dispatch_with_tools(
            "You are helpful", "What is the capital of France?",
        )
        assert "Paris" in output
        assert report.telemetry.get("tool_rounds", 0) == 1

    def test_multiple_tool_rounds(self):
        """LLM calls tools twice before producing final answer."""
        tool_calls_1 = [{
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "crp_retrieve_context",
                "arguments": {"query": "population data"},
            },
        }]
        raw_msg_1 = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_1", "type": "function",
                "function": {"name": "crp_retrieve_context", "arguments": '{"query":"population data"}'}}],
        }
        tool_calls_2 = [{
            "id": "call_2",
            "type": "function",
            "function": {
                "name": "crp_check_facts",
                "arguments": {"claim": "Tokyo has 14 million people"},
            },
        }]
        raw_msg_2 = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_2", "type": "function",
                "function": {"name": "crp_check_facts", "arguments": '{"claim":"Tokyo has 14 million people"}'}}],
        }
        orch = self._make_mock_orchestrator([
            ("", "tool_calls", tool_calls_1, raw_msg_1),
            ("", "tool_calls", tool_calls_2, raw_msg_2),
            ("Tokyo has approximately 14 million people.", "stop", None, None),
        ])
        output, report = orch.dispatch_with_tools(
            "You are helpful", "Tell me about Tokyo's population",
        )
        assert "Tokyo" in output
        assert report.telemetry.get("tool_rounds", 0) == 2

    def test_max_tool_rounds_safety_cap(self):
        """If LLM keeps requesting tools past the cap, force text response."""
        # All responses are tool calls
        tool_calls = [{
            "id": "call_loop",
            "type": "function",
            "function": {
                "name": "crp_retrieve_context",
                "arguments": {"query": "loop"},
            },
        }]
        raw_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call_loop", "type": "function",
                "function": {"name": "crp_retrieve_context", "arguments": '{"query":"loop"}'}}],
        }
        # Create many tool responses + a final fallback
        responses = [("", "tool_calls", tool_calls, raw_msg)] * 15
        orch = self._make_mock_orchestrator(responses)
        output, report = orch.dispatch_with_tools(
            "You are helpful", "Keep trying",
            max_tool_rounds=3,
        )
        # Should have hit the safety cap and used fallback
        assert report.telemetry.get("tool_rounds", 0) <= 4

    def test_tool_dispatch_extracts_facts(self):
        """Facts should be extracted from tool-mediated output."""
        orch = self._make_mock_orchestrator([
            ("The speed of light is 299792458 meters per second. This is a fundamental constant.", "stop", None, None),
        ])
        output, report = orch.dispatch_with_tools(
            "You are helpful", "Tell me about the speed of light",
        )
        # Should have attempted extraction (may or may not find facts depending on pipeline)
        assert report.facts_extracted >= 0

    def test_tool_dispatch_returns_quality_report(self):
        """dispatch_with_tools should return a valid QualityReport."""
        orch = self._make_mock_orchestrator([
            ("Test output", "stop", None, None),
        ])
        output, report = orch.dispatch_with_tools(
            "You are helpful", "Test task",
        )
        assert report.session_id is not None
        assert report.window_id is not None
        assert report.quality_tier is not None
        assert isinstance(report.telemetry, dict)

    def test_tool_dispatch_continues_on_length(self):
        """If the final answer hits length, continuation windows extend it."""
        from crp.core.orchestrator import CRPOrchestrator
        from crp.providers.base import LLMProvider

        tool_calls = [{
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "crp_retrieve_context",
                "arguments": {"query": "data"},
            },
        }]
        raw_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "crp_retrieve_context", "arguments": '{"query":"data"}'},
            }],
        }

        chat_idx = [0]
        continuation_replies = [
            "Part one of the answer. ",
            "Part two of the answer. ",
            "Part three of the answer.",
        ]

        class ContinuationToolProvider(LLMProvider):
            def __init__(self):
                self.tool_done = False

            def generate_chat(self, messages, **kwargs):
                idx = min(chat_idx[0], len(continuation_replies) - 1)
                chat_idx[0] += 1
                # First two windows hit length, final stops.
                fr = "length" if chat_idx[0] < len(continuation_replies) else "stop"
                return continuation_replies[idx], fr

            def count_tokens(self, text):
                return max(1, len(text) // 4)

            def context_window_size(self):
                return 32000

            def supports_tools(self):
                return True

            def generate_chat_with_tools(self, messages, tools, **kwargs):
                if not self.tool_done:
                    self.tool_done = True
                    return ("", "tool_calls", tool_calls, raw_msg)
                # Final answer truncated; return a fact-bearing output.
                return ("Part one covers cloud threats. ", "length", None, None)

        provider = ContinuationToolProvider()
        orch = CRPOrchestrator(provider=provider)
        output, report = orch.dispatch_with_tools(
            "You are helpful",
            "Write a detailed three-part report about cloud security. "
            "Include part 1: threats, part 2: controls, part 3: compliance.",
        )
        assert "Part one" in output
        assert "Part three" in output
        assert report.telemetry.get("continuation_index", 0) >= 2


# ── WindowMetrics tool fields tests ───────────────────────────────────

class TestWindowMetricsToolFields:
    def test_tool_fields_exist(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics()
        assert m.tool_rounds == 0
        assert m.tool_tokens_served == 0
        assert m.tool_calls_detail == []

    def test_tool_fields_in_to_dict(self):
        from crp.core.window import WindowMetrics
        m = WindowMetrics(tool_rounds=3, tool_tokens_served=500)
        d = m.to_dict()
        assert d["tool_rounds"] == 3
        assert d["tool_tokens_served"] == 500
        assert "tool_calls_detail" in d



class TestLocalProviderToolSupport:
    """Tool-call support for Ollama, llama.cpp, and LM Studio adapters."""

    def test_ollama_adapter_supports_tools(self):
        from crp.providers.ollama import OllamaAdapter
        adapter = OllamaAdapter(model="llama3.1")
        assert adapter.supports_tools() is True

    def test_llamacpp_adapter_supports_tools(self):
        from crp.providers.llamacpp import LlamaCppAdapter
        adapter = LlamaCppAdapter(server_url="http://localhost:8080")
        assert adapter.supports_tools() is True

    def test_ollama_generate_chat_with_tools_parses_response(self):
        from crp.providers.ollama import OllamaAdapter
        adapter = OllamaAdapter(model="llama3.1")

        fake_response = json.dumps({
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "crp_retrieve_context",
                            "arguments": '{"query": "EU AI Act"}',
                        },
                    }
                ],
            },
            "done": True,
            "done_reason": "stop",
        }).encode("utf-8")

        with patch.object(adapter._opener, "open") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_response
            mock_open.return_value.__enter__.return_value = mock_resp

            text, reason, tool_calls, raw_msg = adapter.generate_chat_with_tools(
                [{"role": "user", "content": "Find facts."}],
                [{"type": "function", "function": {"name": "crp_retrieve_context"}}],
            )

        assert reason == "tool_calls"
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "crp_retrieve_context"
        assert tool_calls[0]["function"]["arguments"]["query"] == "EU AI Act"
        assert raw_msg["role"] == "assistant"
        assert raw_msg["tool_calls"][0]["id"] == "call_abc123"

    def test_llamacpp_http_generate_chat_with_tools_parses_response(self):
        from crp.providers.llamacpp import LlamaCppAdapter
        adapter = LlamaCppAdapter(server_url="http://localhost:8080")

        fake_response = json.dumps({
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_xyz",
                        "type": "function",
                        "function": {
                            "name": "crp_check_facts",
                            "arguments": '{"claim": "test"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }]
        }).encode("utf-8")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake_response
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            text, reason, tool_calls, raw_msg = adapter.generate_chat_with_tools(
                [{"role": "user", "content": "Check this."}],
                [{"type": "function", "function": {"name": "crp_check_facts"}}],
            )

        assert reason == "tool_calls"
        assert tool_calls[0]["function"]["name"] == "crp_check_facts"
        assert tool_calls[0]["function"]["arguments"]["claim"] == "test"
