"""GenerativeAgent base — Park et al. (2023) memory stream + retrieval + reflection.

Tier 1 shipped: observe (with LLM-scored importance), recall (with BGE asymmetric
query prefix), summary_paragraph (cache read), reflect (NotImplementedError stub).
Tier 2 fills in:
  - reflect()                       — Park et al. §4.2 two-step (questions → insights).
  - regenerate_summary()            — Park et al. Appendix A three-query summary.
  - regenerate_summary_if_stale()   — every-3-runs OR new-reflection trigger.
  - summary_paragraph()             — async; falls back to fresh generation if cache empty.

See PROJECT_SPEC.md §4.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Protocol

import numpy as np
from pydantic import BaseModel, Field

from src.agents._prompt import load_prompt
from src.llm.wrapper import logged_completion
from src.memory.retrieval import Memory
from src.memory.store import MemoryStore, connect

# Embedding callable signature: must accept (text, *, is_query: bool) and return a 1-D
# float32 vector. BGE-v1.5 wants a query prefix on queries but NOT on stored memories
# (PROJECT_SPEC.md §4 / RA-7).
EmbedFn = Callable[..., np.ndarray]


class _Embedder(Protocol):
    def __call__(self, text: str, *, is_query: bool) -> np.ndarray: ...  # pragma: no cover


class ImportanceRating(BaseModel):
    """Schema for importance_score.md — the model returns a single integer rating."""

    rating: int = Field(ge=1, le=10)


class _ReflectionQuestions(BaseModel):
    """Schema for reflection_questions.md."""

    questions: list[str] = Field(min_length=1)


class _ReflectionInsight(BaseModel):
    insight: str
    cited_memory_indices: list[int] = Field(default_factory=list)


class _ReflectionInsights(BaseModel):
    """Schema for reflection_insights.md."""

    insights: list[_ReflectionInsight] = Field(min_length=1)


class _AgentSummaryParagraph(BaseModel):
    """Schema for agent_summary.md."""

    paragraph: str


# Park et al. §4.3 default thresholds — exposed so tests can dial them down.
REFLECTION_IMPORTANCE_THRESHOLD = 50
REFLECTION_N_QUESTIONS = 3
REFLECTION_N_INSIGHTS_PER_QUESTION = 5
REFLECTION_RECALL_K = 12
REFLECTION_RECENT_WINDOW = 100
SUMMARY_RECALL_K = 8
SUMMARY_REGEN_EVERY_N_RUNS = 3


def default_importance_model() -> str:
    """Cheap, deterministic-friendly model for the 1–10 importance score."""
    return os.environ.get(
        "IMPORTANCE_MODEL",
        os.environ.get("JUDGE_CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
    )


def default_reflection_model() -> str:
    """Reflection benefits from a model that handles open-ended synthesis well."""
    return os.environ.get(
        "REFLECTION_MODEL",
        os.environ.get("HEAVY_CLAUDE_MODEL", "claude-opus-4-7"),
    )


def default_summary_model() -> str:
    """Summary is short paragraphs; the cheap importance model is fine."""
    return os.environ.get("SUMMARY_MODEL", default_importance_model())


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
        reflection_model: str | None = None,
        summary_model: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.embed = embed
        self.store = store
        self.importance_model = importance_model or default_importance_model()
        self.reflection_model = reflection_model or default_reflection_model()
        self.summary_model = summary_model or default_summary_model()

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

    async def summary_paragraph(
        self, query: str, source_run_id: str | None = None
    ) -> str | None:
        """Most recent cached agent_summary, or a freshly generated one if cache is empty.

        The cached version is the concatenation of three queries (Park et al. Appendix A).
        On a cold cache we generate a single paragraph for the supplied query rather than
        firing all three calls — the pipeline can call `regenerate_summary()` explicitly
        when it wants the full three-query refresh.
        """
        cached = self.store.cached_summary(self.agent_id)
        if cached:
            return cached
        retrieved = self.recall(query, k=SUMMARY_RECALL_K)
        if not retrieved:
            return None
        return await self._summary_for(query, retrieved, source_run_id)

    # --- reflection (Park et al. §4.2) -------------------------------------

    async def reflect(self, source_run_id: str | None = None) -> list[str]:
        """Two-step reflection. Returns the new reflection memory_ids.

        1. Generate `REFLECTION_N_QUESTIONS` questions over the agent's most recent memories.
        2. For each question: recall top-k by relevance, extract insights with cited indices.
        3. Persist each insight as a reflection-type memory with `cited_memory_ids` set.
        """
        recent = self.store.recent(self.agent_id, n=REFLECTION_RECENT_WINDOW)
        if not recent:
            return []

        questions = await self._reflection_questions(recent, source_run_id)

        new_ids: list[str] = []
        for question in questions:
            retrieved = self.recall(question, k=REFLECTION_RECALL_K)
            if not retrieved:
                continue
            insights = await self._reflection_insights(question, retrieved, source_run_id)
            for ins in insights:
                cited_ids = [
                    retrieved[i - 1].memory_id
                    for i in ins.cited_memory_indices
                    if 1 <= i <= len(retrieved)
                ]
                importance = await self._score_importance(ins.insight, source_run_id)
                embedding = self.embed(ins.insight, is_query=False)
                mid = self.store.add_reflection(
                    agent_id=self.agent_id,
                    description=ins.insight,
                    importance=importance,
                    embedding=embedding,
                    cited_memory_ids=cited_ids,
                    source_run_id=source_run_id,
                )
                new_ids.append(mid)
        return new_ids

    async def reflect_if_due(
        self,
        source_run_id: str | None = None,
        threshold: int = REFLECTION_IMPORTANCE_THRESHOLD,
    ) -> list[str]:
        """Run reflect() iff unreflected importance crosses `threshold`."""
        if self.store.unreflected_importance_sum(self.agent_id) < threshold:
            return []
        return await self.reflect(source_run_id=source_run_id)

    # --- agent summary (Park et al. Appendix A) ----------------------------

    async def regenerate_summary(self, source_run_id: str | None = None) -> int:
        """Run the three Appendix-A queries, concatenate, write a versioned row.

        Returns the new version number.
        """
        queries = [
            f"{self.agent_role}'s core analytical disposition",
            f"{self.agent_role}'s recent focus",
            f"{self.agent_role}'s observed blind spots and tendencies",
        ]
        paragraphs: list[str] = []
        for q in queries:
            retrieved = self.recall(q, k=SUMMARY_RECALL_K)
            paragraph = await self._summary_for(q, retrieved, source_run_id)
            if paragraph:
                paragraphs.append(paragraph)
        combined = " ".join(p.strip() for p in paragraphs if p)
        if not combined:
            combined = (
                f"No memories yet for {self.agent_id} ({self.agent_role}); "
                "summary will populate on the next run."
            )
        return self.store.write_summary(self.agent_id, combined)

    async def regenerate_summary_if_stale(
        self,
        run_count: int,
        source_run_id: str | None = None,
    ) -> bool:
        """Regenerate summary every `SUMMARY_REGEN_EVERY_N_RUNS` runs OR after a reflection.

        Returns True iff a new summary was written.
        """
        due_by_runs = (
            run_count > 0 and run_count % SUMMARY_REGEN_EVERY_N_RUNS == 0
        )
        if due_by_runs or self._has_new_reflection_since_summary():
            await self.regenerate_summary(source_run_id=source_run_id)
            return True
        return False

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

    async def _reflection_questions(
        self,
        recent_memories: list[Memory],
        source_run_id: str | None,
    ) -> list[str]:
        path, system, user = load_prompt(
            "reflection_questions.md",
            agent_role=self.agent_role,
            n_memories=str(len(recent_memories)),
            memories_block=_format_memories_for_questions(recent_memories),
        )
        result = await logged_completion(
            run_id=source_run_id or "no_run",
            stage="reflection_questions",
            agent_id=self.agent_id,
            model=self.reflection_model,
            system=system,
            user=user,
            temperature=0.4,
            max_tokens=512,
            prompt_path=path,
            response_format=_ReflectionQuestions,
        )
        parsed = _coerce_parsed(result, _ReflectionQuestions)
        return list(parsed.questions)[:REFLECTION_N_QUESTIONS]

    async def _reflection_insights(
        self,
        question: str,
        retrieved: list[Memory],
        source_run_id: str | None,
    ) -> list[_ReflectionInsight]:
        path, system, user = load_prompt(
            "reflection_insights.md",
            agent_name=self.agent_id,
            n_insights=str(REFLECTION_N_INSIGHTS_PER_QUESTION),
            numbered_memories_block=_format_numbered_memories(retrieved),
            question=question,
        )
        result = await logged_completion(
            run_id=source_run_id or "no_run",
            stage="reflection_insights",
            agent_id=self.agent_id,
            model=self.reflection_model,
            system=system,
            user=user,
            temperature=0.4,
            max_tokens=2048,
            prompt_path=path,
            response_format=_ReflectionInsights,
        )
        parsed = _coerce_parsed(result, _ReflectionInsights)
        return list(parsed.insights)[:REFLECTION_N_INSIGHTS_PER_QUESTION]

    async def _summary_for(
        self,
        query: str,
        retrieved: list[Memory],
        source_run_id: str | None,
    ) -> str:
        path, system, user = load_prompt(
            "agent_summary.md",
            agent_name=self.agent_id,
            agent_role=self.agent_role,
            memories_block=_format_memories_for_summary(retrieved),
            query=query,
        )
        result = await logged_completion(
            run_id=source_run_id or "no_run",
            stage="agent_summary",
            agent_id=self.agent_id,
            model=self.summary_model,
            system=system,
            user=user,
            temperature=0.3,
            max_tokens=512,
            prompt_path=path,
            response_format=_AgentSummaryParagraph,
        )
        parsed = _coerce_parsed(result, _AgentSummaryParagraph)
        return parsed.paragraph

    def _has_new_reflection_since_summary(self) -> bool:
        """True iff there's a reflection memory newer than the most recent cached summary.

        Compared as ISO-8601 strings so microsecond precision survives the round-trip.
        """
        with connect(self.store.path) as conn:
            row = conn.execute(
                "SELECT MAX(created_at) AS last_summary "
                "FROM agent_summary WHERE agent_id = ?",
                (self.agent_id,),
            ).fetchone()
            last_summary = row["last_summary"] if row else None
            params: list[Any] = [self.agent_id]
            sql = (
                "SELECT 1 FROM agent_memory "
                "WHERE agent_id = ? AND memory_type = 'reflection'"
            )
            if last_summary is not None:
                sql += " AND created_at > ?"
                params.append(last_summary)
            sql += " LIMIT 1"
            return conn.execute(sql, params).fetchone() is not None


def _coerce_parsed(result: dict[str, Any], schema: type[BaseModel]) -> Any:
    parsed = result.get("parsed")
    if parsed is not None:
        return parsed
    return schema.model_validate(json.loads(result["raw_text"]))


def _format_memories_for_questions(memories: list[Memory]) -> str:
    """Bullet list with date stamp; matches the spec's free-form recent-memory block."""
    if not memories:
        return "(no memories)"
    lines: list[str] = []
    for m in memories:
        lines.append(f"- ({m.created_at.date().isoformat()}) {m.description}")
    return "\n".join(lines)


def _format_numbered_memories(memories: list[Memory]) -> str:
    """1-based numbered list — `cited_memory_indices` references these positions."""
    if not memories:
        return "(no memories)"
    lines: list[str] = []
    for i, m in enumerate(memories, start=1):
        lines.append(f"{i}. {m.description}")
    return "\n".join(lines)


def _format_memories_for_summary(memories: list[Memory]) -> str:
    if not memories:
        return "(no memories)"
    lines: list[str] = []
    for m in memories:
        lines.append(f"- {m.description}")
    return "\n".join(lines)
