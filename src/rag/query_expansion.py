"""C3: rule-based query expansion for short, vague KB queries."""

from __future__ import annotations

import re

from src.utils.logging import get_logger
from src.utils.ticket_id import normalize_ticket_id

logger = get_logger(__name__)

#: Synonym terms appended when a trigger word appears (query grows by these).
SYNONYM_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("改密", ("修改密码",)),
    ("重置密码", ("改密",)),
    ("登录不上", ("登录失败",)),
    ("登录不了", ("无法登录",)),
    ("登录失败", ("无法登录",)),
    ("连不上", ("连接失败",)),
    ("连接不上", ("连接失败",)),
    ("打不开", ("无法访问",)),
    ("访问不了", ("无法访问",)),
    ("退款多久到账", ("退款到账时间",)),
    ("多久到账", ("到账时间",)),
)

#: Abbreviation expansions applied case-insensitively as whole words.
ABBREVIATION_RULES: tuple[tuple[str, str], ...] = (
    ("VPN", "虚拟专用网络"),
)

#: Minimum length for a query to be considered "explicit" (skip expansion).
EXPLICIT_QUERY_MIN_LENGTH = 20


def _ticket_id_pattern(query: str) -> bool:
    """Return True when the query contains a ticket id pattern."""
    return normalize_ticket_id(query, allow_bare_numeric=True) is not None


def should_skip_expansion(query: str) -> bool:
    """Decide whether expansion should be skipped for an explicit query."""
    if _ticket_id_pattern(query):
        return True
    return len(query.strip()) >= EXPLICIT_QUERY_MIN_LENGTH


def expand_query(query: str) -> str:
    """Expand a short query with synonym and abbreviation terms (rule-based).

    Explicit queries (ticket ids or long sentences) are returned unchanged.
    """
    if not query or not query.strip():
        return query
    if should_skip_expansion(query):
        logger.debug("query_expansion | action=skip | query=%s", query)
        return query

    lowered = query.lower()
    matched_triggers = [
        trigger
        for trigger, _ in SYNONYM_RULES
        if trigger.lower() in lowered
    ]
    # Drop short triggers contained by a longer matched trigger (overlap guard).
    matched_triggers = [
        trigger
        for trigger in matched_triggers
        if not any(
            other != trigger and trigger.lower() in other.lower()
            for other in matched_triggers
        )
    ]
    extra_terms: list[str] = []
    for trigger, terms in SYNONYM_RULES:
        if trigger in matched_triggers:
            extra_terms.extend(term for term in terms if term not in query)
    for abbrev, full in ABBREVIATION_RULES:
        if re.search(rf"(?<![a-z0-9]){abbrev.lower()}(?![a-z0-9])", lowered) and full not in query:
            extra_terms.append(full)

    if not extra_terms:
        return query

    expanded = f"{query} {' '.join(dict.fromkeys(extra_terms))}"
    logger.debug("query_expansion | action=expand | query=%s | expanded=%s", query, expanded)
    return expanded
