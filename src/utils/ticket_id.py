"""Canonical ticket id normalization helpers (shared by tools and repositories)."""

from __future__ import annotations

import re
import unicodedata


def normalize_ticket_id(value: str, allow_bare_numeric: bool = True) -> str | None:
    """Normalize common ticket id variants into the canonical TKT-1234 form.

    Supported variants include examples such as:
    - TKT-1004
    - tkt-1004
    - TKT1004
    - TKT 1004
    - TKT_1004
    - TKT:1004
    - bare numeric ids like 1004 when allowed
    """
    normalized = unicodedata.normalize("NFKC", value or "").strip().upper()
    if not normalized:
        return None

    prefixed = re.search(r"(?<![A-Z0-9])TKT\s*[-_:]?\s*(\d{3,6})(?!\d)", normalized)
    if prefixed:
        return f"TKT-{prefixed.group(1)}"

    if allow_bare_numeric:
        numeric = re.search(r"(?<!\d)(\d{3,6})(?!\d)", normalized)
        if numeric:
            return f"TKT-{numeric.group(1)}"

    return None
