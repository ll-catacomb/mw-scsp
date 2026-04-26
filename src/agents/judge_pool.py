"""Judge Pool — logical agent with 5 instances each tagged.

Per-judge calibration history (rating distribution, would-have-generated rate) is the
memory. Used to detect outlier judges and surface drift in the audit trail.
See PROJECT_SPEC.md §3, §4.5.

NOTE (Tier 2 cross-worktree): per the worktree split, `feature/memory` owns this file.
This implementation was authored on `feature/pipeline` because end-to-end runs are
gated on it. Interface matches the contract in `worktree-prompts/memory.md` so the
memory worktree's version can supersede via merge with no caller-side changes.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

from src.agents._prompt import load_prompt
from src.agents.base import EmbedFn, GenerativeAgent
from src.llm.wrapper import logged_completion
from src.memory.store import MemoryStore
from src.pipeline.schemas import PlausibilityRating, WouldHaveGenerated

# (judge_id, family). Family rotation per proposal_index reduces cross-proposal compounding.
JUDGE_INSTANCES: list[tuple[str, str]] = [
    ("judge_0", "anthropic"),
    ("judge_1", "anthropic"),
    ("judge_2", "anthropic"),
    ("judge_3", "openai"),
    ("judge_4", "openai"),
]

POOL_AGENT_ID = "judge_pool"
POOL_AGENT_ROLE = "Five-judge calibration pool for adversarial-distribution red team"


def _judge_claude_model() -> str:
    return os.environ.get("JUDGE_CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def _judge_gpt_model() -> str:
    return os.environ.get("JUDGE_GPT_MODEL", "gpt-5")


def _model_for(family: str) -> str:
    if family == "anthropic":
        return _judge_claude_model()
    if family == "openai":
        return _judge_gpt_model()
    raise ValueError(f"Unknown judge family: {family!r}")


def _judge_temperature(family: str) -> float:
    """Spec calls for 0.2; GPT-5/o-series reject non-default temperature, pin to 1.0 there."""
    if family == "openai":
        return 1.0
    return 0.2


class JudgePool(GenerativeAgent):
    """Stage-5 logical agent — fans out to 5 calibrated judge instances per proposal."""

    def __init__(
        self,
        embed: EmbedFn,
        store: MemoryStore,
    ) -> None:
        super().__init__(
            agent_id=POOL_AGENT_ID,
            agent_role=POOL_AGENT_ROLE,
            embed=embed,
            store=store,
        )

    async def judge(
        self,
        proposal: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
        proposal_index: int = 0,
    ) -> list[dict[str, Any]]:
        """Return 5 judgment dicts for one proposal. Persists per-judge calibration observations."""
        instances = list(JUDGE_INSTANCES)
        # Family rotation: alternate which family votes first, so cross-proposal bias doesn't compound.
        if proposal_index % 2 == 1:
            instances = instances[3:] + instances[:3]

        return await asyncio.gather(
            *(
                self._one_judgment(judge_id, family, proposal, scenario, run_id)
                for judge_id, family in instances
            )
        )

    async def _one_judgment(
        self,
        judge_id: str,
        family: str,
        proposal: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        proposal_block = _format_proposal(proposal)
        scenario_block = _format_scenario(scenario)
        model = _model_for(family)
        temperature = _judge_temperature(family)

        # Two independent calls per judge — fresh contexts on each so the two signals
        # are not allowed to drift toward each other (PROJECT_SPEC.md §3 / prompt notes).
        plaus_path, plaus_system, plaus_user = load_prompt(
            "judge_plausibility.md",
            scenario_block=scenario_block,
            proposal_block=proposal_block,
        )
        check_path, check_system, check_user = load_prompt(
            "judge_off_dist_check.md",
            scenario_block=scenario_block,
            proposal_block=proposal_block,
        )

        plaus_task = logged_completion(
            run_id=run_id,
            stage="5_judging",
            agent_id=judge_id,
            model=model,
            system=plaus_system,
            user=plaus_user,
            temperature=temperature,
            max_tokens=4096,
            prompt_path=plaus_path,
            response_format=PlausibilityRating,
        )
        check_task = logged_completion(
            run_id=run_id,
            stage="5_judging",
            agent_id=judge_id,
            model=model,
            system=check_system,
            user=check_user,
            temperature=temperature,
            max_tokens=4096,
            prompt_path=check_path,
            response_format=WouldHaveGenerated,
        )

        plaus_result, check_result = await asyncio.gather(plaus_task, check_task)
        plaus: PlausibilityRating = plaus_result["parsed"]
        check: WouldHaveGenerated = check_result["parsed"]

        judgment: dict[str, Any] = {
            "judgment_id": str(uuid.uuid4()),
            "proposal_id": proposal["proposal_id"],
            "judge_id": judge_id,
            "judge_family": family,
            "plausibility": int(plaus.plausibility),
            "rationale": plaus.rationale,
            "would_have_generated": bool(check.would_have_generated),
            "would_have_generated_rationale": check.rationale,
        }

        # Per-judge calibration observation. Recorded under judge_id (not POOL_AGENT_ID) so each
        # judge has its own memory stream of past ratings — the calibration history visible
        # in the audit trail.
        await self._observe_calibration(judge_id, judgment, run_id)
        return judgment

    async def _observe_calibration(
        self, judge_id: str, judgment: dict[str, Any], run_id: str
    ) -> None:
        description = (
            f"{judge_id} rated proposal {judgment['proposal_id'][:8]} "
            f"plausibility={judgment['plausibility']}, "
            f"would_have_generated={judgment['would_have_generated']}."
        )
        importance = await self._score_importance(description, run_id)
        embedding = self.embed(description, is_query=False)
        self.store.add_observation(
            agent_id=judge_id,
            description=description,
            importance=importance,
            embedding=embedding,
            source_run_id=run_id,
        )


def _format_proposal(p: dict[str, Any]) -> str:
    """Render a proposal dict as a readable markdown block for the judge prompts."""
    actions = p.get("actions") or []
    actions_lines: list[str] = []
    for a in actions:
        if isinstance(a, dict):
            actions_lines.append(
                f"- **{a.get('actor', '?')}** — {a.get('action', '')} "
                f"(target: {a.get('target', '?')}, day {a.get('timeline_days', '?')}, "
                f"purpose: {a.get('purpose', '')})"
            )
        else:
            actions_lines.append(f"- {a}")
    actions_block = "\n".join(actions_lines) if actions_lines else "(no actions specified)"

    risks = p.get("risks_red_accepts") or []
    risks_block = "\n".join(f"- {r}" for r in risks) if risks else "(none specified)"

    parts = [
        f"**{p.get('move_title', '(untitled)')}**",
        "",
        p.get("summary", ""),
        "",
        "### Actions",
        actions_block,
        "",
        f"**Intended effect:** {p.get('intended_effect', '')}",
    ]
    if "which_convergence_pattern_it_breaks" in p:
        parts.append(
            f"**Convergence pattern broken:** {p.get('which_convergence_pattern_it_breaks', '')}"
        )
    if "why_a_red_planner_could_justify_this" in p:
        parts.append(
            f"**Red planner's justification:** {p.get('why_a_red_planner_could_justify_this', '')}"
        )
    parts.extend(["", "### Risks Red accepts", risks_block])
    return "\n".join(parts)


def _format_scenario(scenario: dict[str, Any]) -> str:
    payload = {k: v for k, v in scenario.items() if k != "red_team_question"}
    try:
        import yaml
        return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False).strip()
    except Exception:
        return json.dumps(payload, indent=2, sort_keys=True)
