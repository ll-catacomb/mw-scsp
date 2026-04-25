"""GenerativeAgent base — Park et al. (2023) memory stream + retrieval + reflection hook.

Tier 1 ships: observe (with LLM-scored importance), recall (with BGE asymmetric
query prefix), summary_paragraph (cache read), reflect (NotImplementedError stub).
Tier 2 fills in reflection and the agent_summary regenerator.

See PROJECT_SPEC.md §4.
"""

from __future__ import annotations

import os
from typing import Callable, Protocol

import numpy as np
from pydantic import BaseModel, Field

from src.agents._prompt import load_prompt
from src.llm.wrapper import logged_completion
from src.memory.retrieval import Memory
from src.memory.store import MemoryStore

# Embedding callable signature: must accept (text, *, is_query: bool) and return a 1-D
# float32 vector. BGE-v1.5 wants a query prefix on queries but NOT on stored memories
# (PROJECT_SPEC.md §4 / RA-7).
EmbedFn = Callable[..., np.ndarray]


class _Embedder(Protocol):
    def __call__(self, text: str, *, is_query: bool) -> np.ndarray: ...  # pragma: no cover


class ImportanceRating(BaseModel):
    """Schema for importance_score.md — the model returns a single integer rating."""

    rating: int = Field(ge=1, le=10)


def default_importance_model() -> str:
    """Cheap, deterministic-friendly model for the 1–10 importance score."""
    return os.environ.get(
        "IMPORTANCE_MODEL",
        os.environ.get("JUDGE_CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
    )


class GenerativeAgent:
    """Base for persistent agents that accumulate analytical state across pipeline runs."""

    def __init__(
        self,
        agent_id: str,
        agent_role: str,
        embed: EmbedFn,
        store: MemoryStore,
        *,
        importance_model: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.embed = embed
        self.store = store
        self.importance_model = importance_model or default_importance_model()

    # --- core memory ops ---------------------------------------------------

    async def observe(
        self,
        description: str,
        source_run_id: str | None = None,
    ) -> str:
        """Score importance via LLM, embed (no query prefix), persist as observation."""
        importance = await self._score_importance(description, source_run_id)
        embedding = self.embed(description, is_query=False)
        return self.store.add_observation(
            agent_id=self.agent_id,
            description=description,
            importance=importance,
            embedding=embedding,
            source_run_id=source_run_id,
        )

    def recall(
        self,
        query: str,
        k: int = 8,
        memory_types: list[str] | None = None,
    ) -> list[Memory]:
        """Embed `query` (with the BGE query prefix) and retrieve top-k memories."""
        query_embedding = self.embed(query, is_query=True)
        return self.store.retrieve(
            agent_id=self.agent_id,
            query_embedding=query_embedding,
            k=k,
            memory_types=memory_types,
        )

    def summary_paragraph(self, query: str) -> str | None:
        """Most recent cached agent_summary, or None if cache empty.

        Tier 2 will plumb in the regenerator that runs the agent_summary.md prompt against
        retrievals for `query` and writes a fresh row when memory has changed materially.
        """
        _ = query  # placeholder hook; see Tier 2 brief
        return self.store.cached_summary(self.agent_id)

    async def reflect(self) -> None:
        """Reflection per Park et al. §4.2; implemented in Tier 2."""
        raise NotImplementedError("Tier 2")

    # --- internals ---------------------------------------------------------

    async def _score_importance(
        self,
        description: str,
        source_run_id: str | None,
    ) -> int:
        path, system, user = load_prompt("importance_score.md", memory_text=description)
        result = await logged_completion(
            run_id=source_run_id or "no_run",
            stage="memory_creation",
            agent_id=self.agent_id,
            model=self.importance_model,
            system=system,
            user=user,
            temperature=0.0,
            max_tokens=64,
            prompt_path=path,
            response_format=ImportanceRating,
        )
        parsed = result["parsed"]
        if parsed is None:  # pragma: no cover — wrapper would have raised first
            raise RuntimeError("importance_score returned no parsed payload")
        return max(1, min(10, int(parsed.rating)))
