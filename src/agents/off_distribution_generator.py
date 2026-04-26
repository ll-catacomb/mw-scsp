"""Off-Distribution Generator — generative agent for Stage 4.

Memory: previously proposed off-distribution moves with their plausibility / survival outcomes.
Instructed not to repeat near-duplicates. See PROJECT_SPEC.md §3, §4.5.

Architectural commitment (PROJECT_SPEC.md §5): this stage does NOT do doctrine retrieval.
The job is to escape the modal cluster, not to stay in it.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from pydantic import BaseModel, Field

from src.agents._prompt import load_prompt
from src.agents.base import EmbedFn, GenerativeAgent
from src.llm.wrapper import logged_completion
from src.memory.retrieval import Memory
from src.memory.store import MemoryStore

AGENT_ID = "off_distribution_generator"
AGENT_ROLE = "Off-distribution generator for adversarial-distribution red team"


class _Action(BaseModel):
    actor: str
    action: str
    target: str
    timeline_days: int | str
    purpose: str


class _Proposal(BaseModel):
    move_title: str
    summary: str
    actions: list[_Action] = Field(default_factory=list)
    intended_effect: str
    which_convergence_pattern_it_breaks: str
    why_a_red_planner_could_justify_this: str
    risks_red_accepts: list[str] = Field(default_factory=list)


class OffDistributionProposals(BaseModel):
    """Mirrors off_distribution.md's required JSON schema."""

    proposals: list[_Proposal]


def _default_heavy_model() -> str:
    return os.environ.get("HEAVY_CLAUDE_MODEL", "claude-opus-4-7")


def _default_temperature() -> float:
    raw = os.environ.get("OFF_DIST_TEMPERATURE")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return 1.0


class OffDistributionGenerator(GenerativeAgent):
    """Stage-4 agent. Reads the convergence summary and proposes K off-distribution moves."""

    def __init__(
        self,
        embed: EmbedFn,
        store: MemoryStore,
        *,
        generation_model: str | None = None,
        temperature: float | None = None,
    ) -> None:
        super().__init__(
            agent_id=AGENT_ID,
            agent_role=AGENT_ROLE,
            embed=embed,
            store=store,
        )
        self.generation_model = generation_model or _default_heavy_model()
        self.temperature = temperature if temperature is not None else _default_temperature()

    async def propose(
        self,
        convergence_summary: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """Generate K candidate off-distribution moves. Persists each as an observation."""
        query = self._recall_query(scenario, convergence_summary)
        prior_proposals = self.recall(query, k=8)

        path, system, user = load_prompt(
            "off_distribution.md",
            convergence_summary_block=_format_convergence_summary(convergence_summary),
            notable_absences_block=_format_absences(convergence_summary),
            scenario_block=_format_scenario(scenario),
            prior_proposals_block=_format_prior_proposals(prior_proposals),
            k=str(k),
        )
        result = await logged_completion(
            run_id=run_id,
            stage="4_off_distribution",
            agent_id=self.agent_id,
            model=self.generation_model,
            system=system,
            user=user,
            temperature=self.temperature,
            max_tokens=4096,
            prompt_path=path,
            response_format=OffDistributionProposals,
        )
        parsed = result["parsed"]
        if parsed is not None:
            proposals = parsed.proposals
        else:
            data = json.loads(result["raw_text"])
            proposals = OffDistributionProposals.model_validate(data).proposals

        # Defensive truncation: the prompt asks for K, but the schema has no
        # max-length and a model that overshoots silently 5×s downstream judge
        # cost (5 judges × 2 questions per extra proposal). The contract is "k
        # is an upper bound" — enforce it here.
        proposals = proposals[:k]

        out: list[dict[str, Any]] = []
        for p in proposals:
            d = p.model_dump()
            d["proposal_id"] = str(uuid.uuid4())
            out.append(d)
            await self.observe(_proposal_memory_text(d), source_run_id=run_id)
        return out

    @staticmethod
    def _recall_query(
        scenario: dict[str, Any], convergence_summary: dict[str, Any]
    ) -> str:
        title = scenario.get("title") or scenario.get("scenario_id") or "scenario"
        summary = (
            convergence_summary.get("convergence_summary")
            or scenario.get("summary")
            or scenario.get("description")
            or ""
        )
        return f"Off-distribution proposals for {title}. {summary}".strip()


def _format_convergence_summary(convergence_summary: dict[str, Any]) -> str:
    summary = convergence_summary.get("convergence_summary")
    clusters = convergence_summary.get("clusters") or []
    parts: list[str] = []
    if summary:
        parts.append(str(summary))
    if clusters:
        cluster_lines = []
        for c in clusters:
            cid = c.get("cluster_id", "?")
            theme = c.get("theme", "(no theme)")
            members = c.get("member_move_ids") or c.get("members") or []
            cluster_lines.append(f"- cluster {cid} — {theme} (members: {members})")
        parts.append("Clusters:\n" + "\n".join(cluster_lines))
    return "\n\n".join(parts) if parts else "(no convergence summary)"


def _format_absences(convergence_summary: dict[str, Any]) -> str:
    absences = convergence_summary.get("notable_absences") or []
    if not absences:
        return "(no notable absences)"
    lines: list[str] = []
    for a in absences:
        absence = a.get("absence", "")
        why_proposed = a.get("why_it_might_be_proposed", "")
        why_missed = a.get("why_the_ensemble_missed_it", "")
        lines.append(
            f"- {absence}\n  why it might be proposed: {why_proposed}\n  why the ensemble missed it: {why_missed}"
        )
    return "\n".join(lines)


def _format_scenario(scenario: dict[str, Any]) -> str:
    return json.dumps(scenario, indent=2, sort_keys=True, default=str)


def _format_prior_proposals(prior: list[Memory]) -> str:
    if not prior:
        return "(no prior proposals retrieved)"
    lines: list[str] = []
    for m in prior:
        lines.append(f"- ({m.created_at.date().isoformat()}) {m.description}")
    return "\n".join(lines)


def _proposal_memory_text(p: dict[str, Any]) -> str:
    """One-line natural-language summary for the memory stream."""
    title = p.get("move_title", "(untitled)")
    summary = p.get("summary", "")
    breaks = p.get("which_convergence_pattern_it_breaks", "")
    return (
        f"Proposed off-distribution move '{title}': {summary} "
        f"(breaks pattern: {breaks})"
    )
