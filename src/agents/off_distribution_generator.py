"""Off-Distribution Generator — generative agent for Stage 4.

Memory: previously proposed off-distribution moves with their plausibility / survival
outcomes. Instructed not to repeat near-duplicates. See PROJECT_SPEC.md §3, §4.5.

NOTE (Tier 2 cross-worktree): per the worktree split, `feature/memory` owns this file.
This implementation was authored on `feature/pipeline` because end-to-end runs are
gated on it. Interface matches the contract in `worktree-prompts/memory.md` so the
memory worktree's version can supersede via merge with no caller-side changes.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from src.agents._prompt import load_prompt
from src.agents.base import EmbedFn, GenerativeAgent
from src.llm.wrapper import logged_completion
from src.memory.retrieval import Memory
from src.memory.store import MemoryStore
from src.pipeline.schemas import OffDistributionBatch

AGENT_ID = "off_distribution_generator"
AGENT_ROLE = "Off-distribution generator for adversarial-distribution red team"


def _default_heavy_model() -> str:
    return os.environ.get("HEAVY_CLAUDE_MODEL", "claude-opus-4-7")


class OffDistributionGenerator(GenerativeAgent):
    """Stage-4 agent. Reads the convergence summary and proposes K plausible-but-off moves."""

    def __init__(
        self,
        embed: EmbedFn,
        store: MemoryStore,
        *,
        generator_model: str | None = None,
    ) -> None:
        super().__init__(
            agent_id=AGENT_ID,
            agent_role=AGENT_ROLE,
            embed=embed,
            store=store,
        )
        self.generator_model = generator_model or _default_heavy_model()

    async def propose(
        self,
        convergence_summary: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
        k: int = 10,
    ) -> list[dict[str, Any]]:
        """Generate K off-distribution proposals; persist each as an observation. Returns dicts."""
        query = self._scenario_query(scenario, convergence_summary)
        prior = self.recall(query, k=8)

        path, system, user = load_prompt(
            "off_distribution.md",
            convergence_summary_block=_format_convergence(convergence_summary),
            notable_absences_block=_format_absences(convergence_summary.get("notable_absences", [])),
            scenario_block=_format_scenario(scenario),
            prior_proposals_block=_format_prior(prior),
            k=str(k),
        )
        result = await logged_completion(
            run_id=run_id,
            stage="off_distribution",
            agent_id=self.agent_id,
            model=self.generator_model,
            system=system,
            user=user,
            temperature=1.0,
            max_tokens=8192,
            prompt_path=path,
            response_format=OffDistributionBatch,
        )
        parsed: OffDistributionBatch = result["parsed"]

        out: list[dict[str, Any]] = []
        for prop in parsed.proposals:
            d = prop.model_dump()
            d["proposal_id"] = str(uuid.uuid4())
            out.append(d)
            await self.observe(
                description=f"Proposed off-distribution move: {d['move_title']}. {d['summary']}",
                source_run_id=run_id,
            )
        return out

    @staticmethod
    def _scenario_query(scenario: dict[str, Any], convergence: dict[str, Any]) -> str:
        title = scenario.get("title") or scenario.get("scenario_id") or "scenario"
        summary = (convergence.get("convergence_summary") or "").strip()
        return f"Past off-distribution proposals relevant to {title}. {summary}".strip()


def _format_convergence(c: dict[str, Any]) -> str:
    summary = c.get("convergence_summary") or "(no summary)"
    clusters = c.get("clusters") or []
    lines = [summary, ""]
    if clusters:
        lines.append("### Clusters")
        for cl in clusters:
            theme = cl.get("theme", "?")
            members = cl.get("member_move_ids") or []
            lines.append(f"- cluster {cl.get('cluster_id', '?')}: {theme} (members: {len(members)})")
    return "\n".join(lines)


def _format_absences(absences: list[dict[str, Any]]) -> str:
    if not absences:
        return "(no absences identified)"
    lines: list[str] = []
    for a in absences:
        lines.append(
            f"- **{a.get('absence', '?')}** — might be proposed because: "
            f"{a.get('why_it_might_be_proposed', '')}; ensemble missed it because: "
            f"{a.get('why_the_ensemble_missed_it', '')}"
        )
    return "\n".join(lines)


def _format_scenario(scenario: dict[str, Any]) -> str:
    payload = {k: v for k, v in scenario.items() if k != "red_team_question"}
    try:
        import yaml
        return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False).strip()
    except Exception:
        return json.dumps(payload, indent=2, sort_keys=True)


def _format_prior(memories: list[Memory]) -> str:
    if not memories:
        return "(no prior proposals retrieved)"
    lines: list[str] = []
    for m in memories:
        lines.append(f"- ({m.created_at.date().isoformat()}) {m.description}")
    return "\n".join(lines)
