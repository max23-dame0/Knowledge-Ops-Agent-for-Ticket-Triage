"""Ticket lookup tool definitions backed by the local ticket dataset."""

from __future__ import annotations

import json
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



def get_ticket_status(ticket_id: str) -> dict[str, object]:
    """Load ticket data from the local JSON file and return a tool-friendly lookup result."""
    normalized_id = ticket_id.strip().upper()
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
        if str(item.get("ticket_id", "")).upper() == normalized_id:
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
        error=f"Ticket not found: {ticket_id}",
        ticket=None,
    ).model_dump()
