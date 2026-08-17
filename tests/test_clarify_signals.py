"""Tests for advisory clarification signal detection (route_fn layer)."""

from __future__ import annotations

import pytest

from src.agents.route_fn import (
    detect_clarify_signals,
    looks_like_context_poor_kb_query,
    needs_context_clarification,
)


class TestClarifySignals:
    def test_no_signals_for_concrete_questions(self) -> None:
        for question in [
            "VPN 登录失败提示 token 过期怎么办",
            "帮我看 TKT-1004 工单现在状态",
            "退款多久能到账",
            "多个用户反馈服务中断 要不要转给 L2",
        ]:
            signals = detect_clarify_signals(question)
            assert signals["hint"] is False, f"{question!r} should not trigger clarify hints"

    def test_signals_for_context_poor_questions(self) -> None:
        signals = detect_clarify_signals("VPN 有点异常")
        assert signals["hint"] is True
        assert "context_poor_kb" in signals["matched"]

        signals = detect_clarify_signals("这个账号问题")
        assert signals["hint"] is True
        assert "context_poor_theme" in signals["matched"]

    def test_vague_no_topic_signal(self) -> None:
        signals = detect_clarify_signals("系统坏了怎么办")
        assert signals["hint"] is True
        assert "vague_no_topic" in signals["matched"]

    def test_empty_input_no_hint(self) -> None:
        # Empty input is handled deterministically (verifiable missing fact),
        # not via phrasing signals.
        signals = detect_clarify_signals("")
        assert signals["hint"] is False


class TestContextPoorHelpers:
    def test_looks_like_context_poor_kb(self) -> None:
        assert looks_like_context_poor_kb_query("VPN 有点异常") is True
        assert looks_like_context_poor_kb_query("VPN 登录失败提示 token 过期怎么办") is False

    def test_needs_context_clarification(self) -> None:
        assert needs_context_clarification("这个账号问题") is True
        assert needs_context_clarification("帮我看 TKT-1004 工单现在状态") is False
        # Strong escalation signals must not trigger context clarification.
        assert needs_context_clarification("多个用户无法使用核心功能") is False
