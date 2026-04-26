"""Pydantic schemas for pipeline structured-output stages.

Co-located with the pipeline modules so the prompt template (`src/prompts/modal_red.md`)
and the schema travel together. The wrapper enforces structured output via
`messages.parse(output_format=...)` on Anthropic and `chat.completions.parse(
response_format=...)` on OpenAI; both providers accept a Pydantic class directly.

OpenAI's structured-output validator only supports a subset of JSON Schema (no regex
constraints, no `$ref` cycles, no number bounds with `exclusiveMinimum`/etc.). Keep
fields plain — strings, ints, lists, and nested simple models — so the same schema
round-trips through both providers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModalAction(BaseModel):
    """One discrete action in a modal Red move's execution plan.

    `timeline_days` is `int | str`: the prompt asks for an integer day offset, but
    Anthropic and OpenAI both routinely emit natural-language ranges like
    "1-7", "T+72h", "Day 4". Strict `int` would fail Stage-2 parsing on those
    outputs. The Cartographer and judges read this field for context, not
    arithmetic, so accepting strings preserves audit fidelity at the cost of
    one downstream coercion if anyone needs the integer form.
    """

    actor: str
    action: str
    target: str
    timeline_days: int | str
    purpose: str


class ModalMoveSchema(BaseModel):
    """Structured output for a single modal-ensemble move.

    Mirrors the JSON contract documented at the bottom of `src/prompts/modal_red.md`.
    The `doctrine_cited` list records the passage ids whose reasoning the model
    actually drew on (subset of the top-k retrieved passages).
    """

    move_title: str
    summary: str
    actions: list[ModalAction] = Field(default_factory=list)
    intended_effect: str
    risks_red_accepts: list[str] = Field(default_factory=list)
    doctrine_cited: list[str] = Field(default_factory=list)


class OffDistributionProposal(BaseModel):
    """One off-distribution move from Stage 4. Mirrors the schema in off_distribution.md."""

    move_title: str
    summary: str
    actions: list[ModalAction] = Field(default_factory=list)
    intended_effect: str
    which_convergence_pattern_it_breaks: str
    why_a_red_planner_could_justify_this: str
    risks_red_accepts: list[str] = Field(default_factory=list)


class OffDistributionBatch(BaseModel):
    """Wrapper schema — the LLM returns a JSON object with a `proposals` array."""

    proposals: list[OffDistributionProposal]


class PlausibilityRating(BaseModel):
    """Per judge_plausibility.md — one judge's rating + rationale."""

    plausibility: int = Field(ge=1, le=5)
    rationale: str


class WouldHaveGenerated(BaseModel):
    """Per judge_off_dist_check.md — boolean + rationale, fresh context."""

    would_have_generated: bool
    rationale: str
