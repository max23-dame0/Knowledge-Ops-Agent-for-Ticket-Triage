"""Offline unit tests for rule-based escalation draft generation."""

from __future__ import annotations

import pytest

from src.tools.escalation_tools import (
    _detect_severity,
    _detect_team,
    create_escalation_draft,
)


class TestSeverityDetection:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("生产故障 服务中断 多个用户无法访问", "urgent"),
            ("大面积用户受影响 紧急", "urgent"),
            ("无法登录 核心功能不可用", "high"),
            ("重复扣费 影响财务", "high"),
            ("登录失败 报错 需要人工处理", "medium"),
            ("常规咨询", "low"),
        ],
    )
    def test_keyword_severity(self, text: str, expected: str) -> None:
        assert _detect_severity(text) == expected


class TestTeamDetection:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("vpn 无法访问 网络连接失败", "l2_network"),
            ("重复扣费 账单异常", "billing_ops"),
            ("密码重置失败 账号被锁", "account_support"),
            ("未知问题", "platform_support"),
        ],
    )
    def test_keyword_team(self, text: str, expected: str) -> None:
        assert _detect_team(text) == expected


class TestCreateEscalationDraft:
    def test_draft_shape(self) -> None:
        draft = create_escalation_draft("多个用户无法登录", ["服务中断 30 分钟"])
        assert set(draft.keys()) == {
            "severity",
            "suggested_team",
            "escalation_summary",
            "recommended_next_step",
            "needs_human_confirmation",
        }
        assert draft["severity"] in {"urgent", "high", "medium", "low"}
        assert draft["suggested_team"] in {
            "l2_network",
            "billing_ops",
            "account_support",
            "platform_support",
        }
        assert draft["escalation_summary"]
        assert draft["recommended_next_step"]

    def test_urgent_draft_recommends_immediate_action(self) -> None:
        draft = create_escalation_draft("生产环境服务中断 多个用户无法访问", [])
        assert draft["severity"] == "urgent"
        assert "立即升级" in draft["recommended_next_step"]

    def test_high_severity_requires_human_confirmation(self) -> None:
        draft = create_escalation_draft("无法登录 核心功能不可用", [])
        assert draft["severity"] == "high"
        assert draft["needs_human_confirmation"] is True

    def test_low_severity_no_confirmation_required(self) -> None:
        draft = create_escalation_draft("常规咨询", [])
        assert draft["severity"] == "low"
        assert draft["needs_human_confirmation"] is False

    def test_empty_summary_does_not_crash(self) -> None:
        draft = create_escalation_draft("   ", [])
        assert draft["escalation_summary"]
