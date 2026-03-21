"""Escalation suggestion tool definitions backed by simple local rules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EscalationDraft(BaseModel):
    """Structured escalation suggestion returned to callers."""

    severity: str = Field(description="Suggested escalation severity: low, medium, high, or urgent.")
    suggested_team: str = Field(description="Suggested receiving team for the escalation.")
    escalation_summary: str = Field(description="A short summary suitable for an escalation draft.")
    recommended_next_step: str = Field(description="The next action the operator should take.")



def create_escalation_draft(issue_summary: str, evidence: list[str]) -> dict[str, str]:
    """Generate a simple escalation draft from an issue summary and supporting evidence."""
    normalized_summary = issue_summary.strip()
    evidence_text = " ".join(evidence).strip()
    combined_text = f"{normalized_summary} {evidence_text}".lower()

    severity = _detect_severity(combined_text)
    suggested_team = _detect_team(combined_text)
    escalation_summary = _build_summary(normalized_summary, severity, suggested_team)
    recommended_next_step = _build_next_step(severity, suggested_team)

    return EscalationDraft(
        severity=severity,
        suggested_team=suggested_team,
        escalation_summary=escalation_summary,
        recommended_next_step=recommended_next_step,
    ).model_dump()



def _detect_severity(text: str) -> str:
    """Infer escalation severity from simple keyword matches."""
    urgent_keywords = ("大面积", "多个客户", "多个用户", "生产故障", "服务中断", "无法访问", "数据泄露", "紧急")
    high_keywords = ("重复扣费", "无法登录", "无法使用", "高优先级", "影响财务", "核心功能")
    medium_keywords = ("失败", "报错", "未收到", "需要人工处理", "升级")

    if any(keyword in text for keyword in urgent_keywords):
        return "urgent"
    if any(keyword in text for keyword in high_keywords):
        return "high"
    if any(keyword in text for keyword in medium_keywords):
        return "medium"
    return "low"



def _detect_team(text: str) -> str:
    """Infer the best escalation target team from simple domain keywords."""
    if any(keyword in text for keyword in ("vpn", "网络", "连接", "无法访问", "设备未注册")):
        return "l2_network"
    if any(keyword in text for keyword in ("退款", "账单", "计费", "重复扣费", "发票")):
        return "billing_ops"
    if any(keyword in text for keyword in ("账号", "密码", "验证", "邀请", "权限")):
        return "account_support"
    return "platform_support"



def _build_summary(issue_summary: str, severity: str, suggested_team: str) -> str:
    """Create a short escalation summary for operators."""
    summary = issue_summary or "未提供问题摘要"
    return f"[{severity}] Route to {suggested_team}: {summary}"



def _build_next_step(severity: str, suggested_team: str) -> str:
    """Suggest the next operational step based on severity and owning team."""
    if severity == "urgent":
        return f"立即升级到 {suggested_team}，并补充影响范围、开始时间和已完成排查步骤。"
    if severity == "high":
        return f"尽快提交给 {suggested_team} 复核，并附上关键证据和用户影响说明。"
    if severity == "medium":
        return f"整理复现步骤后提交给 {suggested_team}，等待二线确认处理方案。"
    return f"先补充更多证据，如仍需升级，再转交 {suggested_team}。"
