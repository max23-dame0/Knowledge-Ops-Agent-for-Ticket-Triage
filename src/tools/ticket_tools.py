"""Ticket lookup tool definitions backed by the local ticket dataset."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field


class TicketRecord(BaseModel):
    """A normalized ticket record returned to callers."""

    ticket_id: str = Field(description="The ticket identifier.")
    status: str = Field(description="The current workflow status of the ticket.")
    priority: str = Field(description="The ticket priority level.")
    owner: str = Field(description="The current ticket owner.")
    last_update: str = Field(description="The last update date in YYYY-MM-DD format.")
    summary: str = Field(description="A short summary of the ticket.")
    category: str = Field(description="The ticket category.")


class TicketLookupResponse(BaseModel):
    """Structured output returned by the ticket status lookup tool."""

    ticket_id: str = Field(description="The ticket id requested by the caller.")
    found: bool = Field(description="Whether the requested ticket was found.")
    error: str | None = Field(default=None, description="Error or not-found message when lookup fails.")
    ticket: TicketRecord | None = Field(default=None, description="The ticket record when lookup succeeds.")


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


def get_ticket_status(ticket_id: str) -> dict[str, object]:
    """Load ticket data from the local JSON file and return a tool-friendly lookup result."""
    normalized_id = normalize_ticket_id(ticket_id, allow_bare_numeric=True) or ticket_id.strip().upper()
    tickets_path = Path("data/tickets.json")

    if not tickets_path.exists():
        return TicketLookupResponse(
            ticket_id=normalized_id,
            found=False,
            error="Ticket data file not found: data/tickets.json",
            ticket=None,
        ).model_dump()

    tickets = json.loads(tickets_path.read_text(encoding="utf-8-sig"))
    for item in tickets:
        stored_id = normalize_ticket_id(str(item.get("ticket_id", "")), allow_bare_numeric=True)
        if stored_id == normalized_id:
            return TicketLookupResponse(
                ticket_id=normalized_id,
                found=True,
                error=None,
                ticket=TicketRecord(
                    ticket_id=str(item["ticket_id"]),
                    status=str(item["status"]),
                    priority=str(item["priority"]),
                    owner=str(item["owner"]),
                    last_update=str(item["last_update"]),
                    summary=str(item["summary"]),
                    category=str(item["category"]),
                ),
            ).model_dump()

    return TicketLookupResponse(
        ticket_id=normalized_id,
        found=False,
        error=f"Ticket not found: {normalized_id}",
        ticket=None,
    ).model_dump()
