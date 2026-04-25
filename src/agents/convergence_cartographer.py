"""Convergence Cartographer — generative agent for Stage 3.

Memory: past convergence patterns, scenario summaries, prior reflections.
See PROJECT_SPEC.md §3, §4.5.

Tier 1: observation + retrieval + structured narration call. No reflection yet
(that's Tier 2). The narration prompt receives any prior reflections from this
agent's memory, retrieved by relevance to the current scenario.
"""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field

from src.agents._prompt import load_prompt
from src.agents.base import EmbedFn, GenerativeAgent
from src.llm.wrapper import logged_completion
from src.memory.retrieval import Memory
from src.memory.store import MemoryStore

AGENT_ID = "convergence_cartographer"
AGENT_ROLE = "Convergence Cartographer for adversarial-distribution red team"


class _Cluster(BaseModel):
    cluster_id: int
    theme: str
    # `list[Any]` does not translate to Anthropic's strict JSON-schema (no `type` resolves);
    # member ids are UUID strings from modal_moves.move_id.
    member_move_ids: list[str] = Field(default_factory=list)
    representative_actions: list[str] = Field(default_factory=list)


class _Absence(BaseModel):
    absence: str
    why_it_might_be_proposed: str
    why_the_ensemble_missed_it: str


class ConvergenceNarration(BaseModel):
    """Mirrors convergence_summary.md's required JSON schema."""

    convergence_summary: str
    clusters: list[_Cluster]
    notable_absences: list[_Absence]
    cross_run_observations: list[str] = Field(default_factory=list)


def _default_heavy_model() -> str:
    return os.environ.get("HEAVY_CLAUDE_MODEL", "claude-opus-4-7")


class ConvergenceCartographer(GenerativeAgent):
    """Stage-3 agent. Reads modal moves + cluster assignments, narrates convergence."""

    def __init__(
        self,
        embed: EmbedFn,
        store: MemoryStore,
        *,
        narration_model: str | None = None,
    ) -> None:
        super().__init__(
            agent_id=AGENT_ID,
            agent_role=AGENT_ROLE,
            embed=embed,
            store=store,
        )
        self.narration_model = narration_model or _default_heavy_model()

    async def narrate_convergence(
        self,
        modal_moves: list[dict[str, Any]],
        cluster_assignments: list[dict[str, Any]] | dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        """Run convergence_summary.md against this run's moves + prior reflections.

        Returns the parsed JSON object.
        """
        query = self._scenario_query(scenario)
        prior_reflections = self.recall(query, k=8, memory_types=["reflection"])

        path, system, user = load_prompt(
            "convergence_summary.md",
            modal_moves_block=_format_moves(modal_moves),
            cluster_block=_format_clusters(cluster_assignments),
            retrieved_reflections_block=_format_reflections(prior_reflections),
        )
        result = await logged_completion(
            run_id=run_id,
            stage="3_convergence",
            agent_id=self.agent_id,
            model=self.narration_model,
            system=system,
            user=user,
            temperature=0.4,
            max_tokens=4096,
            prompt_path=path,
            response_format=ConvergenceNarration,
        )
        parsed = result["parsed"]
        if parsed is not None:
            return parsed.model_dump()
        # The wrapper raises StructuredOutputParseError before getting here, but be safe.
        return json.loads(result["raw_text"])

    @staticmethod
    def _scenario_query(scenario: dict[str, Any]) -> str:
        title = scenario.get("title") or scenario.get("scenario_id") or "scenario"
        summary = scenario.get("summary") or scenario.get("description") or ""
        return f"Convergence patterns relevant to {title}. {summary}".strip()


def _format_moves(modal_moves: list[dict[str, Any]]) -> str:
    if not modal_moves:
        return "(none)"
    lines: list[str] = []
    for i, mv in enumerate(modal_moves):
        mid = mv.get("move_id", f"m{i}")
        body = mv.get("move_json") or mv.get("move") or mv
        if not isinstance(body, str):
            body = json.dumps(body, sort_keys=True)
        lines.append(f"- [{mid}] {body}")
    return "\n".join(lines)


def _format_clusters(clusters: list[dict[str, Any]] | dict[str, Any]) -> str:
    if not clusters:
        return "(no clusters)"
    if isinstance(clusters, dict):
        return json.dumps(clusters, indent=2, sort_keys=True)
    lines: list[str] = []
    for c in clusters:
        cid = c.get("cluster_id", "?")
        members = c.get("member_move_ids") or c.get("members") or []
        lines.append(f"- cluster {cid}: members {members}")
    return "\n".join(lines)


def _format_reflections(reflections: list[Memory]) -> str:
    if not reflections:
        return "(no prior reflections retrieved)"
    lines: list[str] = []
    for r in reflections:
        lines.append(f"- ({r.created_at.date().isoformat()}) {r.description}")
    return "\n".join(lines)
