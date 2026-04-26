"""Judge Pool — logical agent with 5 instances each tagged.

Per-judge calibration history (rating distribution, would-have-generated rate) is the memory.
Used to detect outlier judges and surface drift in the audit trail.
See PROJECT_SPEC.md §3, §4.5.

Each judge_N is its own agent_id in the memory store, so per-instance calibration is
independent. Two prompts per judge (`judge_plausibility.md`, `judge_off_dist_check.md`)
in fresh contexts so the two signals don't contaminate each other (PROJECT_SPEC.md §3).
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

from pydantic import BaseModel, Field

from src.agents._prompt import load_prompt
from src.agents.base import EmbedFn, GenerativeAgent
from src.llm.wrapper import logged_completion
from src.memory.store import MemoryStore

JUDGE_INSTANCES: list[tuple[str, str]] = [
    ("judge_0", "anthropic"),
    ("judge_1", "anthropic"),
    ("judge_2", "anthropic"),
    ("judge_3", "openai"),
    ("judge_4", "openai"),
]

JUDGE_ROLE = "Calibrated judge in adversarial-distribution red team"


class _PlausibilityRating(BaseModel):
    """Structured plausibility judgment.

    The judge must commit to two boolean checks (adjacency + leverage rigor) and
    name the supporting evidence BEFORE scoring. This forces the calibration matrix
    in `judge_plausibility.md` to actually run rather than being implicit prose
    that the LLM can flatline at plaus=3 with vague "I can imagine a justification"
    reasoning. The persistence layer collapses these fields into a structured
    rationale string the audit panel can read.
    """

    adjacency_found: bool = Field(
        description="True iff Red has done anything within 1-2 doctrinal degrees of "
        "this move. Set False for genuinely exotic moves; do not stretch to find an "
        "adjacency."
    )
    adjacency_evidence: str = Field(
        description="If adjacency_found=True: name the precedent (a public exercise "
        "pattern, a documented past operation, a written doctrinal concept Red has "
        "operationalized). If False: state 'no adjacency found' and explain why."
    )
    leverage_named: bool = Field(
        description="True iff the move's central instrument is named at the level of "
        "a specific identifiable thing (a named law, a named contract, a named "
        "electoral mechanism, a named financial instrument, a named unit, a named "
        "site). False if the leverage is hand-waved ('UFWD pressure', 'BRI debt', "
        "'lawfare', 'cyber attack', 'coalition fragmentation' alone)."
    )
    leverage_instrument: str = Field(
        description="If leverage_named=True: quote or paraphrase the specific "
        "instrument the move identifies. If False: state 'leverage hand-waved' and "
        "describe what was missing."
    )
    plausibility: int = Field(
        ge=1,
        le=5,
        description="Per the calibration matrix: adjacency YES + leverage YES = 3-4; "
        "adjacency YES + leverage NO = 2; adjacency NO + leverage YES = 3; "
        "adjacency NO + leverage NO = 1-2.",
    )
    rationale: str = Field(
        description="≤80 words synthesizing the two checks above into the bin. "
        "Do not restate the rubric; explain what your specific findings of "
        "adjacency and leverage mean for THIS move."
    )


class _OffDistCheck(BaseModel):
    """Structured would-have-generated judgment.

    The 'central gambit' check is the load-bearing piece — judges keep collapsing
    "would I have generated this" into "do half its actions look familiar," which
    flips the answer to YES on most moves and dissolves the survival filter. By
    requiring the judge to identify the move's CENTRAL gambit (actor + instrument
    + intended effect) and commit to whether THAT specific construction is in
    their default set, we keep the would_have_generated answer anchored to the
    right level of analysis.
    """

    central_gambit: str = Field(
        description="≤30 words naming the move's CENTRAL gambit: actor + instrument + "
        "intended effect. Not a list of every action; the load-bearing operational "
        "concept. Example: 'CCG-led law-enforcement quarantine framing of cross-"
        "strait traffic to coerce 1992 Consensus offer.'"
    )
    central_gambit_in_my_default_set: bool = Field(
        description="True iff the CENTRAL gambit (not the actions, not the framing, "
        "not the rhetorical posture — the gambit) is one you would have proposed "
        "yourself. A move that adds a third-state proxy, inverts a sequencing "
        "assumption, uses a non-default instrument, or shifts the operative clock "
        "is a False even if half its actions look familiar."
    )
    would_have_generated: bool = Field(
        description="The output signal. Should equal central_gambit_in_my_default_set "
        "in nearly all cases — if you find them disagreeing, you are letting "
        "action-level familiarity override gambit-level distinctiveness."
    )
    rationale: str = Field(
        description="≤80 words. Name the actor, instrument, sequencing choice, or "
        "framing that drove your judgment. Do not say 'it felt familiar/unfamiliar.'"
    )


def _default_judge_claude_model() -> str:
    return os.environ.get("JUDGE_CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def _default_judge_gpt_model() -> str:
    return os.environ.get("JUDGE_GPT_MODEL", "gpt-5")


def _default_judge_temperature() -> float:
    raw = os.environ.get("JUDGE_TEMPERATURE")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return 0.2


class _JudgeInstance(GenerativeAgent):
    """One of five judges. Tagged with its judge_id and model family.

    Memory is per-instance so the calibration history of judge_0 is not co-mingled with
    judge_3's. The store key is the judge_id (e.g. 'judge_0'), not 'judge_pool'.
    """

    def __init__(
        self,
        judge_id: str,
        family: str,
        embed: EmbedFn,
        store: MemoryStore,
        *,
        model: str,
        temperature: float,
    ) -> None:
        super().__init__(
            agent_id=judge_id,
            agent_role=JUDGE_ROLE,
            embed=embed,
            store=store,
        )
        self.family = family
        self.model = model
        self.temperature = temperature

    async def evaluate(
        self,
        proposal: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        """Run both judge prompts in fresh contexts, persist a calibration observation."""
        proposal_block = _format_proposal(proposal)
        scenario_block = _format_scenario(scenario)

        plaus_path, plaus_sys, plaus_usr = load_prompt(
            "judge_plausibility.md",
            scenario_block=scenario_block,
            proposal_block=proposal_block,
        )
        off_path, off_sys, off_usr = load_prompt(
            "judge_off_dist_check.md",
            scenario_block=scenario_block,
            proposal_block=proposal_block,
        )

        plaus_task = logged_completion(
            run_id=run_id,
            stage="5_judge_plausibility",
            agent_id=self.agent_id,
            model=self.model,
            system=plaus_sys,
            user=plaus_usr,
            temperature=self.temperature,
            # GPT-5 reasoning models consume the budget on reasoning tokens before
            # emitting content; 512 returned empty under LengthFinishReasonError.
            # See feature/pipeline Tier-2 follow-up notes in TASK_LEDGER.
            max_tokens=4096,
            prompt_path=plaus_path,
            response_format=_PlausibilityRating,
        )
        off_task = logged_completion(
            run_id=run_id,
            stage="5_judge_off_dist_check",
            agent_id=self.agent_id,
            model=self.model,
            system=off_sys,
            user=off_usr,
            temperature=self.temperature,
            max_tokens=4096,  # GPT-5 reasoning headroom (see plaus_task above).
            prompt_path=off_path,
            response_format=_OffDistCheck,
        )
        plaus_result, off_result = await asyncio.gather(plaus_task, off_task)

        plaus = _coerce_parsed(plaus_result, _PlausibilityRating)
        off = _coerce_parsed(off_result, _OffDistCheck)

        proposal_id = proposal.get("proposal_id", "unknown")

        # Fold the structured calibration fields into the rationale string so the
        # SQL judgments table and the UI audit panel see *why* the bin was chosen
        # — not just the synthesis prose. The structured booleans are the load-
        # bearing piece; the original string rationale is the (now-shorter)
        # synthesis on top of them.
        plaus_rationale = (
            f"adjacency: {'YES — ' + plaus.adjacency_evidence if plaus.adjacency_found else 'NO — ' + plaus.adjacency_evidence}\n"
            f"leverage: {'NAMED — ' + plaus.leverage_instrument if plaus.leverage_named else 'HAND-WAVED — ' + plaus.leverage_instrument}\n"
            f"synthesis: {plaus.rationale}"
        )
        off_rationale = (
            f"central gambit: {off.central_gambit}\n"
            f"in my default set: {'YES' if off.central_gambit_in_my_default_set else 'NO'}\n"
            f"rationale: {off.rationale}"
        )

        judgment = {
            "judgment_id": str(uuid.uuid4()),
            "proposal_id": proposal_id,
            "judge_id": self.agent_id,
            "plausibility": int(plaus.plausibility),
            "rationale": plaus_rationale,
            "would_have_generated": bool(off.would_have_generated),
            # Extra structured fields surfaced to the UI / menu builder. Not
            # persisted to the judgments SQL table (schema unchanged); the
            # llm_calls audit row has the full pydantic dump in parsed_output.
            "off_dist_rationale": off_rationale,
            "central_gambit": off.central_gambit,
            "adjacency_found": bool(plaus.adjacency_found),
            "leverage_named": bool(plaus.leverage_named),
        }

        calibration_text = (
            f"{self.agent_id} ({self.family}) rated proposal {proposal_id} "
            f"plausibility={judgment['plausibility']} "
            f"(adjacency={'Y' if plaus.adjacency_found else 'N'}, "
            f"leverage={'Y' if plaus.leverage_named else 'N'}), "
            f"would_have_generated={judgment['would_have_generated']}. "
            f"Central gambit: {off.central_gambit}"
        )
        await self.observe(calibration_text, source_run_id=run_id)
        return judgment


class JudgePool:
    """Five judge instances, mixed family. One async `judge()` per proposal."""

    def __init__(
        self,
        embed: EmbedFn,
        store: MemoryStore,
        *,
        claude_model: str | None = None,
        gpt_model: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self.store = store
        self.embed = embed
        self.claude_model = claude_model or _default_judge_claude_model()
        self.gpt_model = gpt_model or _default_judge_gpt_model()
        self.temperature = (
            temperature if temperature is not None else _default_judge_temperature()
        )
        self.judges: list[_JudgeInstance] = [
            _JudgeInstance(
                judge_id=judge_id,
                family=family,
                embed=embed,
                store=store,
                model=self.claude_model if family == "anthropic" else self.gpt_model,
                temperature=self.temperature,
            )
            for judge_id, family in JUDGE_INSTANCES
        ]

    async def judge(
        self,
        proposal: dict[str, Any],
        scenario: dict[str, Any],
        run_id: str,
        proposal_index: int = 0,
    ) -> list[dict[str, Any]]:
        """Run all 5 judges concurrently against one proposal.

        `proposal_index` toggles which family votes first (structurally) — at temp=0.2
        this is no behavior change but it preserves the spec's family-rotation rule.
        """
        ordered = self._rotate(proposal_index)
        results = await asyncio.gather(
            *(j.evaluate(proposal, scenario, run_id) for j in ordered)
        )
        # Restore the canonical judge_id ordering in the output regardless of rotation.
        results.sort(key=lambda r: r["judge_id"])
        return results

    def _rotate(self, proposal_index: int) -> list[_JudgeInstance]:
        if proposal_index % 2 == 0:
            return list(self.judges)
        # Put openai-family judges first, anthropic second.
        return [j for j in self.judges if j.family == "openai"] + [
            j for j in self.judges if j.family == "anthropic"
        ]


def _coerce_parsed(result: dict[str, Any], schema: type[BaseModel]) -> Any:
    parsed = result.get("parsed")
    if parsed is not None:
        return parsed
    return schema.model_validate(json.loads(result["raw_text"]))


def _format_proposal(proposal: dict[str, Any]) -> str:
    """Render a proposal dict for inclusion in a judge prompt.

    Strip system-level metadata that biases the judge:
      - `proposal_id` (synthetic uuid; pure noise)
      - `persona_id` (which Red planner authored it — judge would otherwise know
        whether the move came from rocket-force-doctrinaire vs political-officer
        and anchor on persona stereotype)
      - `parent_proposal_id` / `expansion_axis` / `tree_depth` (tree-search
        metadata — telling the judge "this is an actor-axis sibling at depth 1"
        biases the gambit-level analysis the off-dist check is supposed to do)
    The judge sees only the move *content* — title, summary, actions, justification —
    and rates from there.
    """
    REDACTED_KEYS = {
        "proposal_id",
        "persona_id",
        "parent_proposal_id",
        "expansion_axis",
        "tree_depth",
    }
    redacted = {k: v for k, v in proposal.items() if k not in REDACTED_KEYS}
    return json.dumps(redacted, indent=2, sort_keys=True, default=str)


def _format_scenario(scenario: dict[str, Any]) -> str:
    return json.dumps(scenario, indent=2, sort_keys=True, default=str)
