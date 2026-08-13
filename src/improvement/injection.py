"""A4: experience injection text builder and toggle.

The injection is prompt augmentation only: it appends pattern-level
experience context to the agent input and never dictates routing decisions
(ADR D004). Disabled by default via EXPERIENCE_INJECTION_ENABLED.
"""

from __future__ import annotations

import os

from src.improvement.schemas import ExperienceEntry
from src.utils.logging import get_logger

logger = get_logger(__name__)

ENV_INJECTION_ENABLED = "EXPERIENCE_INJECTION_ENABLED"


def injection_enabled() -> bool:
    """Return True when the experience injection toggle is switched on."""
    value = os.getenv(ENV_INJECTION_ENABLED, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def build_experience_injection(entries: list[ExperienceEntry]) -> str:
    """Build a stable injection block from experience entries.

    Entries are rendered as plain key=value lines (no markdown headers,
    no routing instructions). Empty input produces an empty string.
    """
    if not entries:
        return ""

    lines = ["历史经验（仅作参考，不改变你的行为规则）："]
    for entry in entries:
        lines.append(
            f"- situation={entry.situation} | action={entry.action} | lesson={entry.lesson}"
        )
    return "\n".join(lines)
