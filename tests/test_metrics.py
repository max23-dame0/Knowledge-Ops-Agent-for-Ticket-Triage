"""Offline unit tests for rule-based evaluation metrics."""

from __future__ import annotations

from src.evals.metrics import (
    clarification_accuracy,
    extract_tool_names,
    grounding_applicable,
    grounding_presence,
    refusal_accuracy,
    route_accuracy,
    tool_use_accuracy,
)


def _kb_output() -> dict:
    return {
        "route": "kb",
        "evidence": ["KB source=vpn_login | passage=..."],
        "tool_calls": [{"tool": "search_kb", "results": [{"source_title": "vpn_login"}]}],
    }


def _ticket_output() -> dict:
    return {
        "route": "ticket",
        "evidence": ["Ticket ticket_id=TKT-1004 | status=resolved"],
        "tool_calls": [{"tool": "get_ticket_status", "ticket": {"ticket_id": "TKT-1004"}}],
    }


def _escalation_output() -> dict:
    return {
        "route": "escalation",
        "evidence": ["Escalation draft | severity=high"],
        "tool_calls": [{"tool": "create_escalation_draft", "output": {"suggested_team": "billing_ops"}}],
    }


class TestRouteAccuracy:
    def test_match(self) -> None:
        assert route_accuracy("kb", {"route": "kb"}) is True

    def test_mismatch(self) -> None:
        assert route_accuracy("ticket", {"route": "kb"}) is False

    def test_case_insensitive(self) -> None:
        assert route_accuracy("KB", {"route": "kb"}) is True


class TestToolUseAccuracy:
    def test_no_tool_expected_no_calls(self) -> None:
        assert tool_use_accuracy("none", False, {"tool_calls": []}) is True

    def test_no_tool_expected_but_called(self) -> None:
        assert tool_use_accuracy("none", False, {"tool_calls": [{"tool": "search_kb"}]}) is False

    def test_expected_tool_called(self) -> None:
        assert tool_use_accuracy("search_kb", True, {"tool_calls": [{"tool": "search_kb"}]}) is True

    def test_expected_tool_missing(self) -> None:
        assert tool_use_accuracy("search_kb", True, {"tool_calls": [{"tool": "get_ticket_status"}]}) is False


class TestClarificationAccuracy:
    def test_should_clarify_and_did(self) -> None:
        output = {"needs_clarification": True, "clarification_question": "请提供 ticket_id"}
        assert clarification_accuracy(True, output) is True

    def test_should_clarify_but_no_question(self) -> None:
        assert clarification_accuracy(True, {"needs_clarification": True}) is False

    def test_should_not_clarify(self) -> None:
        assert clarification_accuracy(False, {"needs_clarification": False}) is True


class TestGrounding:
    def test_kb_route_applicable(self) -> None:
        assert grounding_applicable(_kb_output()) is True

    def test_clarify_not_applicable(self) -> None:
        assert grounding_applicable({"route": "clarify"}) is False

    def test_evidence_present(self) -> None:
        assert grounding_presence(_kb_output()) is True

    def test_no_evidence(self) -> None:
        output = {"route": "kb", "evidence": [], "tool_calls": []}
        assert grounding_presence(output) is False

    def test_evidence_from_ticket_tool(self) -> None:
        assert grounding_presence(_ticket_output()) is True

    def test_evidence_from_escalation_tool(self) -> None:
        assert grounding_presence(_escalation_output()) is True


class TestRefusalAccuracy:
    def test_unsafe_refused(self) -> None:
        assert refusal_accuracy(True, {"route": "refuse"}) is True

    def test_unsafe_not_refused(self) -> None:
        assert refusal_accuracy(True, {"route": "kb", "conclusion": "ok"}) is False

    def test_safe_not_refused(self) -> None:
        assert refusal_accuracy(False, {"route": "kb", "conclusion": "ok"}) is True


class TestExtractToolNames:
    def test_extracts_names(self) -> None:
        names = extract_tool_names({"tool_calls": [{"tool": "search_kb"}, {"tool": "get_ticket_status"}]})
        assert names == ["search_kb", "get_ticket_status"]

    def test_empty(self) -> None:
        assert extract_tool_names({"tool_calls": []}) == []
        assert extract_tool_names({}) == []
