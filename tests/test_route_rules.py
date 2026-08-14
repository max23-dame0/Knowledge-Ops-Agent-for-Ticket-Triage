"""Offline unit tests for main_agent routing rules (pure functions, no LLM)."""

from __future__ import annotations

import pytest

from src.agents.main_agent import (
    _extract_ticket_id,
    _has_strong_escalation_signal,
    _looks_like_context_poor_kb_query,
    _looks_like_escalation_policy_query,
    _looks_like_escalation_query,
    _looks_like_kb_policy_query,
    _looks_like_ticket_query,
    _needs_context_clarification,
    _resolve_route,
)


class TestResolveRoute:
    @pytest.mark.parametrize(
        ("question", "expected"),
        [
            ("帮我看 TKT-1004 工单现在状态", "ticket"),
            ("帮我看 tkt-1004 工单现在状态", "ticket"),
            ("TKT1004 现在是谁在处理", "ticket"),
            ("工单 1004 现在状态", "ticket"),
            ("多个用户反馈服务中断 要不要转给 L2", "escalation"),
            ("客户连续两天无法登录 是否应该升级处理", "escalation"),
            ("VPN 登录失败提示 token 过期怎么办", "kb"),
            ("退款多久能到账", "kb"),
            ("发票开错抬头还能改吗", "kb"),
            ("sla 首次响应时限是多少", "kb"),
        ],
    )
    def test_route_resolution(self, question: str, expected: str) -> None:
        is_ticket = _looks_like_ticket_query(question)
        is_escalation = _looks_like_escalation_query(question)
        assert _resolve_route(question, is_ticket, is_escalation) == expected

    def test_route_fallback_defaults_to_clarify(self) -> None:
        # No business keywords (chit-chat / out-of-domain) must not be
        # hard-routed to kb, where an empty retrieval invites hallucination.
        assert _resolve_route("你好", False, False) == "clarify"
        assert _resolve_route("how are you doing today", False, False) == "clarify"

    def test_bare_policy_question_routes_to_kb(self) -> None:
        assert _resolve_route("sla 首次响应时限是多少", False, False) == "kb"


class TestTicketIdExtraction:
    @pytest.mark.parametrize(
        ("question", "expected"),
        [
            ("帮我看 TKT-1004 工单现在状态", "TKT-1004"),
            ("帮我看 tkt-1004 工单现在状态", "TKT-1004"),
            ("帮我看 TKT1004 工单现在状态", "TKT-1004"),
            ("帮我看 TKT 1004 工单现在状态", "TKT-1004"),
            ("工单 1004 现在状态", "TKT-1004"),
            ("1004", "TKT-1004"),
        ],
    )
    def test_extract_variants(self, question: str, expected: str) -> None:
        assert _extract_ticket_id(question) == expected

    def test_no_ticket_id(self) -> None:
        assert _extract_ticket_id("帮我查一下工单状态") is None


class TestEscalationSignals:
    @pytest.mark.parametrize(
        "question",
        [
            "是否应该升级处理",
            "多个用户无法使用核心功能",
            "服务中断 连续失败",
            "需要转给 l2",
        ],
    )
    def test_strong_signals(self, question: str) -> None:
        assert _has_strong_escalation_signal(question) is True

    def test_escalation_policy_is_not_case(self) -> None:
        # Policy questions about escalation rules should not look like concrete cases.
        assert _looks_like_escalation_policy_query("什么情况下必须升级给二线") is True
        assert _looks_like_escalation_query("什么情况下必须升级给二线") is False


class TestKBPolicyAndContext:
    def test_kb_policy_query(self) -> None:
        assert _looks_like_kb_policy_query("工单的 sla 首次响应时限是多少") is True

    def test_context_poor_kb(self) -> None:
        assert _looks_like_context_poor_kb_query("VPN 有点异常") is True
        assert _looks_like_context_poor_kb_query("VPN 登录失败提示 token 过期怎么办") is False

    def test_needs_context_clarification(self) -> None:
        assert _needs_context_clarification("这个账号问题") is True
        assert _needs_context_clarification("帮我看 TKT-1004 工单现在状态") is False
