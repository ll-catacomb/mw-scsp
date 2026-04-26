"""Blue Interpretive Curator — Stage 6.

Per-scenario branch curator (USN reads Taiwan, USAF reads Israel) that
sorts the surviving Red menu into A/B/C wargame-prep tiers and writes a
~150-word preamble naming what the menu, taken together, says about the
branch's OPLAN. One LLM call per run; sees only surviving proposals;
does not modify `tier_surviving`.

Architectural notes:
- Doctrine retrieval is allowed in principle (the curator is downstream of
  off-distribution generation), but in practice the curator reads
  doctrinal priors statically through its persona prompt block. The
  test in tests/test_blue_curator.py asserts no `src.doctrine.*` imports
  in this file as a defensive lock.
- The curator is not a GenerativeAgent — no cross-run memory partition
  for this demo. The `agent_id` is stamped into the audit log via the
  logged_completion call, so post-demo persistent memory is a one-line
  upgrade if needed.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.agents._prompt import load_prompt
from src.llm.wrapper import logged_completion
from src.personas.branches import BluePersona

logger = logging.getLogger(__name__)


class _BranchRating(BaseModel):
    proposal_id: str
    branch: Literal["USN", "USAF", "USMC", "USA", "USSF", "CYBER"]
    wargame_prep_value: Literal["A", "B", "C"]
    assumption_it_breaks: str
    cell_to_run_it_against: str
    next_question_for_players: str
    nearest_branch_concept_to_check: str
    where_it_overstates: str
    rationale: str
    refer_to_other_cell: str | None = None


class _CuratorOutput(BaseModel):
    preamble: str
    ratings: list[_BranchRating] = Field(default_factory=list)


def _heavy_model() -> str:
    return os.environ.get("HEAVY_CLAUDE_MODEL", "claude-opus-4-7")


def _curator_temperature() -> float:
    raw = os.environ.get("CURATOR_TEMPERATURE")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return 0.4


class BlueCurator:
    """Stage 6: one-call interpretive curator per run."""

    def __init__(
        self,
        persona: BluePersona,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self.persona = persona
        self.model = model or _heavy_model()
        self.temperature = temperature if temperature is not None else _curator_temperature()
        self.agent_id = persona.agent_id

    async def curate(
        self,
        survivors: list[dict[str, Any]],
        judgments: list[dict[str, Any]],
        scenario: dict[str, Any],
        narration: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        """Run the curator on the surviving Red menu.

        Returns {"branch": str, "preamble": str, "ratings": [dict, ...]}.
        On empty survivors, returns the empty shape WITHOUT calling the LLM
        so the orchestrator's "no leaves survived" path stays cheap.
        """
        if not survivors:
            return {"branch": self.persona.branch, "preamble": "", "ratings": []}

        path, system, user = load_prompt(
            "blue_curator.md",
            persona_name=self.persona.name,
            persona_identity_seed=self.persona.identity_seed,
            persona_ethnographic_exterior=self.persona.ethnographic_exterior,
            persona_doctrinal_priors=self.persona.doctrinal_priors,
            persona_blind_spots=self.persona.blind_spots_and_ergonomics,
            scenario_block=_format_scenario(scenario),
            convergence_summary_block=_format_convergence(narration),
            survivors_block=_format_survivors(survivors, judgments),
        )
        result = await logged_completion(
            run_id=run_id,
            stage="6_blue_curator",
            agent_id=self.agent_id,
            model=self.model,
            system=system,
            user=user,
            temperature=self.temperature,
            max_tokens=16384,
            prompt_path=path,
            response_format=_CuratorOutput,
        )
        parsed: _CuratorOutput = result["parsed"]
        assert parsed is not None, "logged_completion returned parsed=None despite response_format"

        # Defensive: drop any rating whose proposal_id isn't in the survivors set.
        # The curator should only rate what it's shown; this trims any hallucinated id.
        survivor_ids = {p["proposal_id"] for p in survivors}
        ratings = [r.model_dump() for r in parsed.ratings if r.proposal_id in survivor_ids]
        # Force the branch field to match the persona's branch — guards against
        # the curator emitting USAF when it's the USN persona (rare but observed
        # when survivors describe non-Navy moves).
        for r in ratings:
            r["branch"] = self.persona.branch

        return {
            "branch": self.persona.branch,
            "preamble": parsed.preamble.strip(),
            "ratings": ratings,
        }


def _format_scenario(scenario: dict[str, Any]) -> str:
    return json.dumps(scenario, indent=2, sort_keys=True, default=str)


def _format_convergence(narration: dict[str, Any]) -> str:
    summary = (narration.get("convergence_summary") or "").strip()
    if not summary:
        return "(no convergence summary on this run)"
    absences = narration.get("notable_absences") or []
    parts: list[str] = [summary]
    if absences:
        bullets: list[str] = []
        for a in absences:
            if isinstance(a, dict):
                bullets.append(f"- {a.get('absence', '')}")
            else:
                bullets.append(f"- {a}")
        parts.append("Notable absences:\n" + "\n".join(bullets))
    return "\n\n".join(parts)


def _format_survivors(
    survivors: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
) -> str:
    """Render survivors compactly; the curator needs the move + judges' central gambits."""
    by_pid: dict[str, list[dict[str, Any]]] = {}
    for j in judgments:
        by_pid.setdefault(j["proposal_id"], []).append(j)

    blocks: list[str] = []
    for i, p in enumerate(survivors, start=1):
        pid = p["proposal_id"]
        title = p.get("move_title", "(untitled)")
        summary = p.get("summary", "")
        breaks = p.get("which_convergence_pattern_it_breaks", "")
        risks = p.get("risks_red_accepts") or []
        actions = p.get("actions") or []

        action_lines = []
        for a in actions:
            if isinstance(a, dict):
                action_lines.append(
                    f"  - T+{a.get('timeline_days', '?')}d [{a.get('actor', '?')}] "
                    f"{a.get('action', '?')} → {a.get('target', '?')} "
                    f"({a.get('purpose', '')})"
                )

        gambits: list[str] = []
        for j in by_pid.get(pid, []):
            cg = j.get("central_gambit") or ""
            if cg:
                gambits.append(f"  - {j.get('judge_id', '?')}: {cg}")

        block = [
            f"### Survivor {i} — {title}",
            f"_proposal_id: `{pid}`_",
            "",
            summary,
            "",
        ]
        if action_lines:
            block.append("**Actions:**")
            block.extend(action_lines)
            block.append("")
        if breaks:
            block.append(f"**Convergence pattern broken:** {breaks}")
            block.append("")
        if risks:
            block.append("**Risks Red accepts:**")
            for r in risks:
                block.append(f"  - {r}")
            block.append("")
        if gambits:
            block.append("**Judges' central-gambit reads:**")
            block.extend(gambits)
            block.append("")
        blocks.append("\n".join(block))

    return "\n---\n\n".join(blocks)
