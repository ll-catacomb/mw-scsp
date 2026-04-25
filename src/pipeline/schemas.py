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
    """One discrete action in a modal Red move's execution plan."""

    actor: str
    action: str
    target: str
    timeline_days: int
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
