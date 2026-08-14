"""FastAPI service facade for the knowledge-ops-agent.

Endpoints:
- GET  /healthz          - liveness/readiness probe (no auth)
- POST /agent/ask        - run the agent on a question (auth + rate limit)

Run (local):
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from src.agents.main_agent import run_agent
from src.api.auth import require_api_key
from src.api.ratelimit import rate_limit
from src.utils.logging import get_logger, get_request_id, set_request_id

logger = get_logger("knowledge_ops.api")

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")


class AskRequest(BaseModel):
    """Request payload for the /agent/ask endpoint."""

    question: str = Field(min_length=1, max_length=2000, description="User question for the agent.")


class AskResponse(BaseModel):
    """Response payload mirroring the normalized AgentAnswer fields."""

    request_id: str
    answer: dict[str, Any]


app = FastAPI(
    title="knowledge-ops-agent API",
    version=APP_VERSION,
    description="Support agent service: KB Q&A, ticket lookup, escalation suggestions.",
)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    """Generate a request_id, bind it for logging, and echo it in the response."""
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    set_request_id(request_id)
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    set_request_id(None)
    return response


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, Any]:
    """Liveness/readiness probe used by orchestrators and load balancers."""
    from src.repositories.kb_repository import get_kb_repository
    from src.repositories.ticket_repository import get_ticket_repository

    kb_available = get_kb_repository().available()
    ticket_count = get_ticket_repository().count()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "kb_index_available": kb_available,
        "ticket_records": ticket_count,
    }


@app.post("/agent/ask", tags=["agent"], dependencies=[Depends(require_api_key), Depends(rate_limit)])
def agent_ask(payload: AskRequest) -> AskResponse:
    """Run the support agent once and return the normalized structured output."""
    question = payload.question.strip()
    if not question:
        return AskResponse(request_id="", answer={"error": "question is empty"})

    answer = run_agent(question)
    return AskResponse(
        request_id=get_request_id() or "",
        answer=answer.model_dump(),
    )
