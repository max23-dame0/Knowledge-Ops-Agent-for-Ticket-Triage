"""Decision contracts for the agent pipeline.

These models are the single source of truth for what the deterministic layers
produce and what the LLM layer is allowed to consume. They keep decisions
structured, serializable, and replayable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RouteName = Literal["kb", "ticket", "escalation", "clarify", "refuse"]


class RouteDecision(BaseModel):
    """The route resolved by the deterministic routing layer (L2).

    The LLM makes the final decision (L4); this structure records the
    deterministic prior so both can be compared in evaluation and replays.
    """

    route: RouteName = Field(description="Proposed route.")
    confidence: float = Field(ge=0.0, le=1.0, description="Deterministic confidence of the proposal.")
    needs_clarify: bool = Field(default=False, description="Whether context is missing for this route.")
    reasons: list[str] = Field(default_factory=list, description="Human-readable explanations.")
    matched: list[str] = Field(default_factory=list, description="Signal ids that fired.")


class ToolPlanStep(BaseModel):
    """One tool invocation budgeted by the orchestration layer (L3)."""

    tool: str = Field(description="Tool name: search_kb | get_ticket_status | create_escalation_draft.")
    budget: int = Field(ge=0, description="Maximum number of times the LLM may call this tool.")
    reason: str = Field(default="", description="Why this step was planned.")


class ToolPlan(BaseModel):
    """An ordered tool budget for one agent run."""

    steps: list[ToolPlanStep] = Field(default_factory=list)


class AgentContract(BaseModel):
    """Static contract shared by the runtime and the evaluation harness.

    Evaluation and replay assert against these values instead of trusting
    prompt text, so behavior expectations live in code.
    """

    tool_names: tuple[str, ...] = Field(description="Tool names the LLM may call.")
    output_schema: str = Field(description="Qualified name of the output schema.")
    budget_limit: int = Field(ge=1, description="Global tool-call budget for one run.")
    evidence_required: bool = Field(description="Whether conclusions must carry evidence.")
    behavior_rules: tuple[str, ...] = Field(
        default_factory=tuple, description="Behavior rules that evaluation can verify."
    )
