"""RedPlanner — one GenerativeAgent instance per Red-side persona.

Each persona becomes its own agent_id in the memory store, so the persona's
proposal history accumulates independently across runs. The persona's identity
seed + ethnographic exterior + doctrinal priors get prepended to every prompt
that planner generates from (Park et al. 2023 Appendix A).

Two methods:
  - propose_initial(scenario, convergence, run_id, k) — first-pass generation
  - propose_siblings(parent, axis, scenario, run_id, k, sibling_history) —
    tree-search expansion (per Brenner et al. 2026 §2.2 negative-prompting)
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
from src.personas.index import Persona

AGENT_ROLE = "Red-side planner (persona)"


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
    why_a_red_planner_could_justify_this: str
    which_convergence_pattern_it_breaks: str
    risks_red_accepts: list[str] = Field(default_factory=list)


class _PersonaProposals(BaseModel):
    proposals: list[_Proposal]


class _Sibling(BaseModel):
    move_title: str
    summary: str
    actions: list[_Action] = Field(default_factory=list)
    intended_effect: str
    how_it_diverges_from_original: str
    why_a_red_planner_could_justify_this: str
    which_convergence_pattern_it_breaks: str
    risks_red_accepts: list[str] = Field(default_factory=list)


class _SiblingProposals(BaseModel):
    siblings: list[_Sibling]


def _heavy_model() -> str:
    return os.environ.get("HEAVY_CLAUDE_MODEL", "claude-opus-4-7")


def _persona_temperature() -> float:
    raw = os.environ.get("PERSONA_TEMPERATURE")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return 1.0


class RedPlanner(GenerativeAgent):
    """One Red-side planner. Persona-grounded; doctrine-free (PROJECT_SPEC.md §5)."""

    def __init__(
        self,
        persona: Persona,
        embed: EmbedFn,
        store: MemoryStore,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> None:
        super().__init__(
            agent_id=persona.agent_id(),
            agent_role=f"{AGENT_ROLE} — {persona.name}",
            embed=embed,
            store=store,
        )
        self.persona = persona
        self.model = model or _heavy_model()
        self.temperature = temperature if temperature is not None else _persona_temperature()

    async def propose_initial(
        self,
        scenario: dict[str, Any],
        convergence_summary: dict[str, Any],
        run_id: str,
        k: int = 2,
    ) -> list[dict[str, Any]]:
        """First-pass generation: K proposals from this persona's POV."""
        query = self._recall_query(scenario, convergence_summary)
        prior = self.recall(query, k=8)

        path, system, user = load_prompt(
            "red_planner_persona.md",
            persona_name=self.persona.name,
            persona_identity_seed=self.persona.identity_seed,
            persona_ethnographic_exterior=self.persona.ethnographic_exterior,
            persona_doctrinal_priors=self.persona.doctrinal_priors,
            persona_blind_spots=self.persona.blind_spots_and_ergonomics,
            scenario_block=_format_scenario(scenario),
            convergence_summary_block=_format_convergence_summary(convergence_summary),
            notable_absences_block=_format_absences(convergence_summary),
            prior_proposals_block=_format_prior_proposals(prior),
            k=str(k),
        )
        result = await logged_completion(
            run_id=run_id,
            stage="4_persona_initial",
            agent_id=self.agent_id,
            model=self.model,
            system=system,
            user=user,
            temperature=self.temperature,
            max_tokens=16384,  # Opus + multi-proposal JSON outgrows 4096 (saw EOF mid-string)
            prompt_path=path,
            response_format=_PersonaProposals,
        )
        parsed: _PersonaProposals = result["parsed"] or _PersonaProposals.model_validate(
            json.loads(result["raw_text"])
        )
        out: list[dict[str, Any]] = []
        for p in parsed.proposals:
            d = p.model_dump()
            d["proposal_id"] = str(uuid.uuid4())
            d["persona_id"] = self.persona.id
            d["parent_proposal_id"] = None
            d["expansion_axis"] = None
            d["tree_depth"] = 0
            out.append(d)
            await self.observe(_proposal_memory_text(d), source_run_id=run_id)
        return out

    async def propose_siblings(
        self,
        parent_proposal: dict[str, Any],
        axis_name: str,
        axis_description: str,
        scenario: dict[str, Any],
        run_id: str,
        k: int = 2,
        sibling_history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Tree-search expansion: K siblings of `parent_proposal` along `axis_name`."""
        path, system, user = load_prompt(
            "sibling_expansion.md",
            persona_name=self.persona.name,
            persona_identity_seed=self.persona.identity_seed,
            persona_doctrinal_priors=self.persona.doctrinal_priors,
            scenario_block=_format_scenario(scenario),
            original_proposal_block=_format_proposal_block(parent_proposal),
            sibling_history_block=_format_sibling_history(sibling_history or []),
            axis_name=axis_name,
            axis_description=axis_description,
            k=str(k),
        )
        result = await logged_completion(
            run_id=run_id,
            stage="4_sibling_expansion",
            agent_id=self.agent_id,
            model=self.model,
            system=system,
            user=user,
            temperature=self.temperature,
            max_tokens=16384,  # Opus + multi-proposal JSON outgrows 4096 (saw EOF mid-string)
            prompt_path=path,
            response_format=_SiblingProposals,
        )
        parsed: _SiblingProposals = result["parsed"] or _SiblingProposals.model_validate(
            json.loads(result["raw_text"])
        )
        parent_depth = int(parent_proposal.get("tree_depth", 0))
        out: list[dict[str, Any]] = []
        for s in parsed.siblings:
            d = s.model_dump()
            d["proposal_id"] = str(uuid.uuid4())
            d["persona_id"] = self.persona.id
            d["parent_proposal_id"] = parent_proposal["proposal_id"]
            d["expansion_axis"] = axis_name
            d["tree_depth"] = parent_depth + 1
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


# ---- formatters ----


def _format_scenario(scenario: dict[str, Any]) -> str:
    return json.dumps(scenario, indent=2, sort_keys=True, default=str)


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
            cluster_lines.append(f"- cluster {cid} — {theme}")
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


def _format_prior_proposals(prior: list[Memory]) -> str:
    if not prior:
        return "(no prior proposals retrieved — first run for this persona)"
    lines: list[str] = []
    for m in prior:
        lines.append(f"- ({m.created_at.date().isoformat()}) {m.description}")
    return "\n".join(lines)


def _format_proposal_block(proposal: dict[str, Any]) -> str:
    """Render a proposal compactly for the sibling-expansion prompt."""
    return json.dumps(
        {
            "move_title": proposal.get("move_title"),
            "summary": proposal.get("summary"),
            "actions": proposal.get("actions"),
            "intended_effect": proposal.get("intended_effect"),
            "why_a_red_planner_could_justify_this": proposal.get(
                "why_a_red_planner_could_justify_this"
            ),
            "which_convergence_pattern_it_breaks": proposal.get(
                "which_convergence_pattern_it_breaks"
            ),
            "risks_red_accepts": proposal.get("risks_red_accepts"),
        },
        indent=2,
        default=str,
    )


def _format_sibling_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "(no other siblings yet — this is the first expansion of the original)"
    return "\n\n---\n\n".join(_format_proposal_block(s) for s in history)


def _proposal_memory_text(p: dict[str, Any]) -> str:
    title = p.get("move_title", "(untitled)")
    summary = p.get("summary", "")
    breaks = p.get("which_convergence_pattern_it_breaks", "")
    return (
        f"Proposed off-distribution move '{title}': {summary} "
        f"(breaks pattern: {breaks})"
    )
