"""Ticket lookup tool definitions backed by the local ticket dataset."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.repositories.ticket_repository import TicketRepository, get_ticket_repository
from src.utils.ticket_id import normalize_ticket_id


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


# Shared repository instance; tests can swap it via monkeypatch.
_repo: TicketRepository = get_ticket_repository()


def get_ticket_status(ticket_id: str) -> dict[str, object]:
    """Load ticket data through the repository and return a tool-friendly lookup result."""
    normalized_id = normalize_ticket_id(ticket_id, allow_bare_numeric=True) or ticket_id.strip().upper()

    if not _repo.loaded:
        return TicketLookupResponse(
            ticket_id=normalized_id,
            found=False,
            error=f"Ticket data file not found: {_repo.path}",
            ticket=None,
        ).model_dump()

    item = _repo.find_by_id(normalized_id)
    if item is None:
        return TicketLookupResponse(
            ticket_id=normalized_id,
            found=False,
            error=f"Ticket not found: {normalized_id}",
            ticket=None,
        ).model_dump()

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
