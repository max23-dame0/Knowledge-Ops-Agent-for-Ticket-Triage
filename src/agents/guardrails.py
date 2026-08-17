"""Guardrails and validation helpers for agents.

The guardrail layer is the only deterministic layer that may overrule the
LLM. Rules are declared in one policy table instead of scattered if/elif
branches:

- hard=True  -> the rule decides (action applied, LLM is not consulted)
- hard=False -> the rule only produces a hint; the LLM makes the final call

Every rule carries an id so decisions are auditable and replayable. The
keyword/pattern checks below are a cheap first line of defense; the golden
eval set keeps adversarial variants covered so regressions surface quickly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

# Phrasing that tries to extract internal system context.
SYSTEM_EXFILTRATION_PATTERNS = (
    re.compile(r"(system|system prompt|系统).{0,12}(prompt|提示词|指令|规则)", re.IGNORECASE),
    re.compile(r"(prompt|提示词|指令|规则).{0,12}(泄露|导出|输出|复制|打印|展示)", re.IGNORECASE),
    re.compile(r"(api\s*key|密钥|令牌|token).{0,12}(泄露|导出|全部|所有)", re.IGNORECASE),
    re.compile(r"(隐藏|内部|未公开).{0,6}(指令|规则|配置)", re.IGNORECASE),
)

# Phrasing that tries to bypass policy through encoding / roleplay / injection.
BYPASS_PATTERNS = (
    re.compile(r"(base64|rot13|编码|解码|加密|十六进制|hex)\s*(输出|回复|形式|方式)", re.IGNORECASE),
    re.compile(r"(忽略|无视|跳过|忘记).{0,8}(之前|先前|上面|以上|设定|指令)", re.IGNORECASE),
    re.compile(r"(现在|接下来)\s*(你是|扮演|假装)\s*(一个|一名)?\s*(不受限制|没有约束|自由)", re.IGNORECASE),
    re.compile(r"(jailbreak|越狱|越权|绕过|突破).{0,8}(限制|规则|审核)", re.IGNORECASE),
)

# Multilingual injection patterns (EN / DE / ES / FR) - covers roleplay
# override, instruction discarding, and context/data extraction requests.
MULTILINGUAL_BYPASS_PATTERNS = (
    # EN: ignore/forget/disregard + (previous/prior/all/your/my) + instructions/rules/...
    re.compile(
        r"\b(ignore|forget|disregard|don'?t follow|do not follow)\b.{0,40}"
        r"\b(previous|prior|earlier|all|above|given|provided|your|my|any)\b.{0,30}"
        r"\b(instructions?|rules?|prompts?|directions?|orders?|context)\b",
        re.IGNORECASE,
    ),
    # DE: ignorieren/vergessen + Anweisungen/Befehle
    re.compile(
        r"\b(ignorieren|ignoriere|vergessen|vergiss)\b.{0,40}"
        r"\b(anweisungen|befehle|instruktionen|regeln|angaben|obigen)\b",
        re.IGNORECASE,
    ),
    # ES: olvida/olvide/ignora + instrucciones/reglas/dije
    re.compile(
        r"\b(olvida|olvide|olvidar|ignora|ignorar)\b.{0,40}"
        r"\b(instrucciones|reglas|dije|dicho|anterior|todo)\b",
        re.IGNORECASE,
    ),
    # FR: oublie/oubliez/ignore + instructions/règles
    re.compile(
        r"\b(oublie|oubliez|ignorer|ignore)\b.{0,40}"
        r"\b(instructions|règles|regles|directives|précédentes|precedentes)\b",
        re.IGNORECASE,
    ),
    # Extraction requests: show/print/reveal/return/output system internals.
    re.compile(
        r"\b(show|print|reveal|return|output|repeat|tell me|give me)\b.{0,30}"
        r"\b(system prompt|your prompt|embeddings?|system instructions|hidden instructions)\b",
        re.IGNORECASE,
    ),
)

# Bulk-sensitive-data requests (CN + EN).
BULK_DATA_PATTERNS = (
    re.compile(r"(所有|全部|每个).{0,10}(用户|客户|账号).{0,10}(账单|邮箱|密码|手机号|地址)", re.IGNORECASE),
    re.compile(r"(导出|下载|拉取).{0,12}(所有|全部).{0,8}(数据|记录|信息)", re.IGNORECASE),
    re.compile(
        r"\b(all|every|each)\b.{0,12}\b(users?|customers?|accounts?)\b.{0,12}"
        r"\b(billings?|emails?|passwords?|credentials?|addresses?|phone numbers?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(export|download|extract|dump)\b.{0,12}\b(all|every|full)\b.{0,8}\b(data|records?|information|database)\b",
        re.IGNORECASE,
    ),
)


def looks_like_injection_attack(user_input: str) -> bool:
    """Return True when the input resembles a prompt-injection / exfiltration attempt."""
    lowered = user_input.lower()
    return (
        any(pattern.search(lowered) for pattern in SYSTEM_EXFILTRATION_PATTERNS)
        or any(pattern.search(lowered) for pattern in BYPASS_PATTERNS)
        or any(pattern.search(lowered) for pattern in MULTILINGUAL_BYPASS_PATTERNS)
        or any(pattern.search(lowered) for pattern in BULK_DATA_PATTERNS)
    )


def _legacy_refusal_keywords_hit(user_input: str) -> bool:
    """Keyword check equivalent to the legacy REFUSAL_KEYWORDS precheck."""
    keywords = (
        "泄露系统提示词",
        "系统提示词",
        "提示词",
        "隐藏指令",
        "系统配置",
        "内部规则",
        "内部升级规则",
        "prompt",
        "越狱",
        "绕过限制",
        "api key",
        "密钥",
        "内部配置",
        "别人账号权限",
        "所有用户",
        "账单和邮箱",
        "伪造工单状态",
    )
    return any(keyword in user_input or keyword in user_input.lower() for keyword in keywords)


@dataclass(frozen=True)
class GuardrailResult:
    """Outcome of running one guardrail rule against an input."""

    rule_id: str
    action: str  # refuse | clarify | hint
    hard: bool
    matched: bool
    detail: str = ""


def run_guardrails(user_input: str) -> list[GuardrailResult]:
    """Run the guardrail policy table and return one result per rule."""
    lowered = user_input.lower()
    checks: list[tuple[str, str, bool, Callable[[str], bool], str]] = [
        (
            "g_injection",
            "refuse",
            True,
            lambda text: looks_like_injection_attack(text),
            "prompt injection / exfiltration pattern matched",
        ),
        (
            "g_legacy_refusal_keywords",
            "refuse",
            True,
            _legacy_refusal_keywords_hit,
            "legacy refusal keyword matched",
        ),
        (
            "g_bulk_data_export",
            "refuse",
            True,
            lambda text: any(pattern.search(text) for pattern in BULK_DATA_PATTERNS),
            "bulk sensitive data request matched",
        ),
        (
            "g_empty_input",
            "clarify",
            False,
            lambda text: not text.strip(),
            "empty input",
        ),
    ]
    results: list[GuardrailResult] = []
    for rule_id, action, hard, check, detail in checks:
        matched = check(lowered)
        results.append(
            GuardrailResult(
                rule_id=rule_id,
                action=action,
                hard=hard,
                matched=matched,
                detail=detail if matched else "",
            )
        )
    return results


def evaluate_guardrails(user_input: str) -> dict[str, Any]:
    """Return the aggregate guardrail decision for a user input.

    Hard rules fire first and always win. The decision is serializable so it
    can be embedded in decision traces and replayed offline.
    """
    results = run_guardrails(user_input)
    hard_hits = [r for r in results if r.hard and r.matched]
    soft_hits = [r for r in results if not r.hard and r.matched]

    decision: dict[str, Any] = {
        "blocked": bool(hard_hits),
        "action": None,
        "rules_hit": [r.rule_id for r in hard_hits],
        "hints": [
            {"rule_id": r.rule_id, "action": r.action, "detail": r.detail}
            for r in soft_hits
        ],
        "details": [
            {
                "rule_id": r.rule_id,
                "action": r.action,
                "hard": r.hard,
                "matched": r.matched,
                "detail": r.detail,
            }
            for r in results
        ],
    }
    if hard_hits:
        decision["action"] = hard_hits[0].action
    return decision
