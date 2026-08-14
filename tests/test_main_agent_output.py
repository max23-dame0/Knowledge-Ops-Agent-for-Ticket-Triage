"""Offline unit tests for main_agent output coercion and normalization."""

from __future__ import annotations

from src.agents.main_agent import (
    AgentAnswer,
    _coerce_agent_output,
    _extract_json_object,
    _finalize_response,
    _parse_text_response,
    _strip_think_blocks,
)


class TestStripThinkBlocks:
    def test_removes_think_blocks(self) -> None:
        text = "先思考<think>这是推理</think>再输出结论"
        assert "<think>" not in _strip_think_blocks(text)

    def test_no_think_block(self) -> None:
        assert _strip_think_blocks("正常回答") == "正常回答"


class TestExtractJsonObject:
    def test_extracts_json(self) -> None:
        text = '前文{"conclusion": "x"}后文'
        assert _extract_json_object(text) == '{"conclusion": "x"}'

    def test_no_json(self) -> None:
        assert _extract_json_object("没有 json") is None


class TestCoerceAgentOutput:
    def test_passthrough_instance(self) -> None:
        answer = AgentAnswer(conclusion="c", evidence=[], confidence=0.5, needs_clarification=False)
        assert _coerce_agent_output(answer) is answer

    def test_dict_validation(self) -> None:
        output = _coerce_agent_output(
            {"conclusion": "c", "evidence": [], "confidence": 0.5, "needs_clarification": False}
        )
        assert isinstance(output, AgentAnswer)
        assert output.conclusion == "c"

    def test_json_string(self) -> None:
        raw = '{"conclusion": "json结论", "evidence": [], "confidence": 0.9, "needs_clarification": false}'
        output = _coerce_agent_output(raw)
        assert output.conclusion == "json结论"
        assert output.confidence == 0.9

    def test_plain_text_fallback(self) -> None:
        raw = "结论：这是文本回答\n置信度：0.7"
        output = _coerce_agent_output(raw)
        assert isinstance(output, AgentAnswer)
        assert output.conclusion == "这是文本回答"
        assert output.confidence == 0.7


class TestFinalizeResponse:
    def test_clarification_route_normalized(self) -> None:
        answer = AgentAnswer(
            conclusion="c",
            evidence=[],
            confidence=0.3,
            needs_clarification=True,
            clarification_question="q",
        )
        result = _finalize_response(answer, route="clarification")
        assert result.route == "clarify"
        assert result.clarified is True
        assert result.needs_clarification is True

    def test_refusal_route_normalized(self) -> None:
        answer = AgentAnswer(conclusion="c", evidence=[], confidence=0.9, needs_clarification=False)
        result = _finalize_response(answer, route="refusal")
        assert result.route == "refuse"
        assert result.refused is True

    def test_compat_aliases_filled(self) -> None:
        answer = AgentAnswer(conclusion="c", evidence=[], confidence=0.5, needs_clarification=False)
        result = _finalize_response(answer, route="kb")
        assert result.next_actions == result.next_action
        assert result.should_handoff == result.human_handoff


class TestParseTextResponse:
    def test_parses_key_fields(self) -> None:
        raw = "结论：账号问题请重置密码\n是否需要转人工：否\n置信度：0.66\n1. 先重置密码\n2. 再联系支持"
        parsed = _parse_text_response(raw)
        assert parsed.conclusion == "账号问题请重置密码"
        assert parsed.confidence == 0.66
        assert len(parsed.next_action) >= 2

    def test_invalid_confidence_falls_back(self) -> None:
        parsed = _parse_text_response("结论：x\n置信度：abc")
        assert parsed.confidence == 0.5

    def test_empty_text_uses_fallback(self) -> None:
        parsed = _parse_text_response("")
        assert parsed.conclusion  # fallback paragraph is non-empty
