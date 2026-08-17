"""Explicit, evidence-producing routing function (L2 layer).

Replaces the scattered keyword tables in main_agent with one function that
returns a structured RouteDecision. The decision carries the signal ids and
reasons that fired, so evaluations and replays can explain *why* a route was
proposed. Behavior precedence mirrors the legacy _resolve_route exactly:

    1. KB policy query      -> kb
    2. KB policy hints      -> kb
    3. ticket + id, no strong escalation -> ticket
    4. escalation query     -> escalation
    5. ticket query         -> ticket
    6. KB keywords          -> kb
    7. otherwise            -> clarify
"""

from __future__ import annotations

import re

from src.agents.contracts import RouteDecision, RouteName
from src.utils.ticket_id import normalize_ticket_id

# --- signal tables (kept for traceability; decisions come from decide()) ---

KB_KEYWORDS = (
    "VPN", "vpn", "密码", "退款", "发票", "权限", "账号", "邀请", "验证", "计费", "账单", "补开", "到账",
)

KB_POLICY_HINTS = (
    "sla", "SLA", "p1", "P1",
    "首次响应", "响应时限", "多久必须", "多久需要", "规则", "政策", "标准",
)

TICKET_HINTS = (
    "ticket", "Ticket", "工单", "状态", "谁在处理", "负责人", "priority", "owner", "进度",
)

ESCALATION_HINTS = (
    "升级", "升级处理", "是否升级处理", "是否应该升级处理",
    "需要转 team", "转给 l2", "需要转给 l2", "严重程度",
    "服务中断", "多个用户", "影响多个用户", "影响范围扩大",
    "核心功能", "无法使用核心功能", "连续失败", "多次失败",
    "billing team", "network team", "escalation", "l2",
)

ESCALATION_POLICY_HINTS = (
    "什么情况下", "哪些情况下", "什么场景", "哪些场景",
    "规则", "政策", "标准", "必须升级", "升级给二线",
)

STRONG_ESCALATION_TERMS = (
    "是否升级处理", "是否应该升级处理", "需要转 team", "转给 l2", "需要转给 l2",
    "严重程度", "服务中断", "多个用户", "影响多个用户", "影响范围扩大",
    "核心功能", "无法使用核心功能", "连续失败", "多次失败",
    "billing team", "network team", "l2",
)

# Legacy refusal signals (soft rule id list, shared with guardrails.py).
REFUSAL_SIGNALS = (
    "泄露系统提示词", "系统提示词", "提示词", "隐藏指令", "系统配置",
    "内部规则", "内部升级规则", "prompt", "越狱", "绕过限制",
    "api key", "密钥", "内部配置", "别人账号权限", "所有用户",
    "账单和邮箱", "伪造工单状态",
)


def _has_strong_escalation_signal(user_input: str) -> bool:
    """Return True when the phrasing strongly signals an escalation case."""
    lowered = user_input.lower().strip()
    return any(term in lowered for term in STRONG_ESCALATION_TERMS)


def _extract_ticket_id(user_input: str) -> str | None:
    """Extract a ticket id from flexible input variants (see utils.ticket_id)."""
    normalized_input = user_input.strip()
    allow_bare_numeric = bool(
        _looks_like_ticket_hint_only(normalized_input)
        or re.fullmatch(r"\d{3,6}", normalized_input)
    )
    return normalize_ticket_id(normalized_input, allow_bare_numeric=allow_bare_numeric)


def _looks_like_ticket_hint_only(user_input: str) -> bool:
    """Return True when ticket hints exist (used for bare numeric ids)."""
    lowered = user_input.lower()
    return any(hint.lower() in lowered for hint in TICKET_HINTS)


def _looks_like_kb_policy_query(user_input: str) -> bool:
    """Return True for policy-style KB questions that should not be ticket lookups."""
    lowered = user_input.lower()
    if "工单" not in user_input and "ticket" not in lowered and "升级" not in user_input:
        return False
    return any(hint.lower() in lowered for hint in KB_POLICY_HINTS)


def _looks_like_escalation_policy_query(user_input: str) -> bool:
    """Return True when the user asks about escalation policy rather than a case."""
    lowered = user_input.lower()
    if "升级" not in user_input and "二线" not in user_input and "team" not in lowered:
        return False
    concrete_case_terms = (
        "多个用户", "服务中断", "核心功能", "连续失败", "影响范围", "无法使用", "客户", "问题",
    )
    if any(token in lowered for token in concrete_case_terms):
        return False
    return any(hint.lower() in lowered for hint in ESCALATION_POLICY_HINTS)


def detect_signals(user_input: str) -> dict[str, list[str]]:
    """Return the signal ids that fire for an input (for traces and evals)."""
    lowered = user_input.lower().strip()
    signals: dict[str, list[str]] = {
        "kb_keywords": [k for k in KB_KEYWORDS if k in user_input or k.lower() in lowered],
        "kb_policy_hints": [h for h in KB_POLICY_HINTS if h in user_input or h.lower() in lowered],
        "ticket_hints": [h for h in TICKET_HINTS if h in user_input or h.lower() in lowered],
        "escalation_hints": [h for h in ESCALATION_HINTS if h in user_input or h.lower() in lowered],
        "strong_escalation": [t for t in STRONG_ESCALATION_TERMS if t.lower() in lowered],
        "escalation_policy_hints": [
            h for h in ESCALATION_POLICY_HINTS if h in user_input or h.lower() in lowered
        ],
        "refusal_signals": [k for k in REFUSAL_SIGNALS if k in user_input or k.lower() in lowered],
        "ticket_id": [],
    }
    ticket_id = _extract_ticket_id(user_input)
    if ticket_id:
        signals.setdefault("ticket_id", []).append(ticket_id)
    return signals


def _looks_like_ticket_query(user_input: str) -> bool:
    """Return True when the request appears to ask about a ticket."""
    lowered = user_input.lower()
    if _looks_like_kb_policy_query(user_input):
        return False
    return any(hint.lower() in lowered for hint in TICKET_HINTS) or _extract_ticket_id(user_input) is not None


def _looks_like_escalation_query(user_input: str) -> bool:
    """Return True when the request appears to ask for escalation advice."""
    lowered = user_input.lower().strip()
    if _looks_like_escalation_policy_query(user_input):
        return False
    return _has_strong_escalation_signal(user_input) or any(
        hint.lower() in lowered for hint in ESCALATION_HINTS
    )


def decide_route(user_input: str) -> RouteDecision:
    """Propose a route with evidence (precedence mirrors legacy _resolve_route)."""
    is_ticket_query = _looks_like_ticket_query(user_input)
    is_escalation_query = _looks_like_escalation_query(user_input)
    ticket_id = _extract_ticket_id(user_input)
    route: RouteName
    reasons: list[str] = []
    matched: list[str] = []

    if _looks_like_kb_policy_query(user_input):
        route = "kb"
        matched.append("kb_policy_query")
        reasons.append("policy-style KB question")
    elif _looks_like_escalation_policy_query(user_input):
        # Escalation *policy* questions are KB questions (fixes eval E009).
        route = "kb"
        matched.append("escalation_policy_query")
        reasons.append("escalation policy question answered from KB")
    elif any(hint in user_input for hint in KB_POLICY_HINTS):
        route = "kb"
        matched.append("kb_policy_hint")
        reasons.append("KB policy hint present")
    elif is_ticket_query and ticket_id is not None and not _has_strong_escalation_signal(user_input):
        route = "ticket"
        matched.extend(["ticket_query", "ticket_id"])
        reasons.append(f"ticket query with id {ticket_id}")
    elif is_escalation_query:
        route = "escalation"
        matched.append("escalation_query")
        reasons.append("escalation query signal")
    elif is_ticket_query:
        route = "ticket"
        matched.append("ticket_query")
        reasons.append("ticket query without id")
    elif any(keyword in user_input for keyword in KB_KEYWORDS):
        route = "kb"
        matched.append("kb_keyword")
        reasons.append("KB keyword present")
    else:
        route = "clarify"
        matched.append("no_signal")
        reasons.append("no business signal detected")

    confidence = 1.0 if matched else 0.0
    if len(matched) <= 1 and matched[:1] == ["no_signal"]:
        confidence = 0.3

    return RouteDecision(
        route=route,
        confidence=confidence,
        needs_clarify=route == "clarify",
        reasons=reasons,
        matched=matched,
    )


def resolve_route(user_input: str) -> str:
    """Compatibility wrapper returning the proposed route name only."""
    return decide_route(user_input).route


# --- clarification signal detection (advisory, not decisive) ---
#
# These helpers answer "what clarification hints fire?" rather than "must we
# clarify?". The LLM makes the final clarify decision (L4); the deterministic
# precheck only handles verifiable missing facts (empty input, missing
# ticket_id). Keeping the phrase lists here makes them testable and keeps
# main_agent free of heuristic keyword branches.

CONTEXT_POOR_TERMS = (
    "账号问题",
    "这个账号问题",
    "这个 billing",
    "billing 的事",
    "billing问题",
    "这个单子有没有进展",
    "想问下这个单子有没有进展",
    "这个问题需要升级吗",
    "发票这里有问题",
    "这个问题现在进度如何",
    "这个问题进度如何",
)

VAGUE_PHRASES_KB = (
    "有点异常",
    "这里有问题",
    "帮我看下",
    "帮我看一下",
    "账号问题",
    "这个账号问题",
    "有问题",
    "不对劲",
    "异常",
)

VAGUE_MARKERS = ("怎么办", "坏了", "有问题", "不行", "异常")

EXPLICIT_ACTION_TERMS = ("怎么", "如何", "多久", "申请", "补开", "重置", "谁可以", "能否", "可以", "在哪", "登录失败")


def looks_like_context_poor_kb_query(user_input: str) -> bool:
    """Return True for short KB-topic questions that still lack actionable detail."""
    lowered = user_input.lower().strip()
    if not any(keyword.lower() in lowered for keyword in KB_KEYWORDS):
        return False
    if any(term in user_input for term in EXPLICIT_ACTION_TERMS):
        return False
    return any(phrase in lowered for phrase in VAGUE_PHRASES_KB)


def needs_context_clarification(user_input: str) -> bool:
    """Return True for theme-known but context-poor requests."""
    if _has_strong_escalation_signal(user_input):
        return False
    lowered = user_input.lower().strip()
    if not lowered:
        return False
    return any(term in lowered for term in CONTEXT_POOR_TERMS)


def detect_clarify_signals(user_input: str) -> dict:
    """Return advisory clarification hints for the LLM (never decisive)."""
    if not user_input:
        return {"hint": False, "reasons": [], "matched": []}
    matched: list[str] = []
    reasons: list[str] = []

    # Escalation intent wins: asking whether to escalate is a concrete action
    # request, not a context-poor KB question.
    is_escalation_intent = _looks_like_escalation_query(user_input)

    if needs_context_clarification(user_input):
        matched.append("context_poor_theme")
        reasons.append("主题明确但缺少关键上下文(影响对象/范围/单号)")
    if not is_escalation_intent and looks_like_context_poor_kb_query(user_input):
        matched.append("context_poor_kb")
        reasons.append("KB 主题问题缺少具体症状或操作步骤")
    if is_escalation_intent and len(user_input.strip()) < 12 and not _has_strong_escalation_signal(user_input):
        matched.append("escalation_short")
        reasons.append("升级意图但缺少问题摘要与影响范围")
    if (
        not is_escalation_intent
        and any(marker in user_input for marker in VAGUE_MARKERS)
        and not any(keyword in user_input for keyword in KB_KEYWORDS)
    ):
        matched.append("vague_no_topic")
        reasons.append("模糊表述且无明确支持主题")

    return {"hint": bool(matched), "reasons": reasons, "matched": matched}
