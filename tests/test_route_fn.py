"""Tests for the explicit routing layer (src/agents/route_fn.py)."""

from __future__ import annotations

import pytest

from src.agents.route_fn import decide_route, detect_signals, resolve_route


class TestDecideRoute:
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
            ("你好", "clarify"),
            ("how are you doing today", "clarify"),
        ],
    )
    def test_route_decision(self, question: str, expected: str) -> None:
        decision = decide_route(question)
        assert decision.route == expected
        # Every decision must carry evidence (reasons + matched signals).
        assert decision.reasons, f"decision for {question!r} must carry reasons"
        assert decision.matched, f"decision for {question!r} must carry matched signals"

    def test_policy_question_routes_to_kb(self) -> None:
        decision = decide_route("什么情况下必须升级给二线")
        assert decision.route == "kb"

    def test_confidence_bounds(self) -> None:
        decision = decide_route("随便说点什么")
        assert 0.0 <= decision.confidence <= 1.0

    def test_resolve_route_compat(self) -> None:
        assert resolve_route("帮我看 TKT-1004 工单现在状态") == "ticket"
        assert resolve_route("你好") == "clarify"


class TestDetectSignals:
    def test_signals_reported_for_trace(self) -> None:
        signals = detect_signals("客户连续两天无法登录而且影响多个用户 是否应该升级处理")
        assert "影响多个用户" in signals["strong_escalation"]
        assert "是否应该升级处理" in signals["strong_escalation"]
        assert signals["ticket_id"] == []

    def test_ticket_id_signal(self) -> None:
        signals = detect_signals("帮我看 TKT-1004 工单现在状态")
        assert signals["ticket_id"] == ["TKT-1004"]
