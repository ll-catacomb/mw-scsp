"""Per-leaf context-pack export.

After a run completes, this module writes one self-contained markdown file per
*surviving* leaf to `data/runs/{run_id}/context_packs/{slug}.md`. Each pack
contains everything a downstream model instance would need to continue that
option's reasoning when the wargame moves into player counter-moves:

  • The persona's identity seed + ethnographic exterior + doctrinal priors +
    blind spots (the same material the system prompt carried at generation
    time).
  • The scenario block + Cartographer convergence summary + notable absences
    (the Stage-4 input the persona saw).
  • The proposed move itself (title, summary, actions, justification, risks,
    convergence pattern broken).
  • Tree-search lineage — root vs. which-axis-sibling-of-which-parent, and
    for siblings, how the move diverges from its parent along the named axis.
  • All five judges' structured rationales — adjacency / leverage / central
    gambit visible inline, plus the survival math.
  • A footer telling a downstream model how to react to a Blue counter-move
    while keeping the persona's "chain of thought" intact.

The packs are independent of the SQL audit trail; they are derived artifacts
that consolidate the full provenance into a single re-feedable document.

Use:
    from src.pipeline.context_pack import write_context_packs
    paths = write_context_packs(
        run_id=run_id, run_dir=run_dir, proposals=all_proposals,
        judgments=all_judgments, scenario=scenario, narration=narration,
        persona_index=load_persona_index(),
    )
"""

from __future__ import annotations

import collections
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.personas.index import Persona, PersonaIndex

logger = logging.getLogger(__name__)


def write_context_packs(
    *,
    run_id: str,
    run_dir: Path,
    proposals: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    scenario: dict[str, Any],
    narration: dict[str, Any],
    persona_index: PersonaIndex | None,
    branch_curation: dict[str, dict[str, Any]] | None = None,
) -> list[Path]:
    """Write one markdown context pack per surviving leaf.

    A leaf "survives" if either:
      - It carries `tier_surviving=True` from per-tier judging (the new round-
        based path), OR
      - Its judgments produce median_plausibility >= 3 AND
        would_have_gen_count < ceil(N/2) (final survival filter, legacy path).

    Returns the list of written paths.
    """
    out_dir = run_dir / "context_packs"
    out_dir.mkdir(parents=True, exist_ok=True)

    j_by_pid: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for j in judgments:
        j_by_pid[j["proposal_id"]].append(j)

    proposals_by_id: dict[str, dict[str, Any]] = {p["proposal_id"]: p for p in proposals}

    surviving = [p for p in proposals if _is_surviving(p, j_by_pid.get(p["proposal_id"], []))]
    if not surviving:
        logger.info("context_pack: no surviving leaves for run %s; no packs written.", run_id)
        return []

    written: list[Path] = []
    for proposal in surviving:
        persona = (
            persona_index.by_id.get(proposal.get("persona_id", ""))
            if persona_index is not None
            else None
        )
        parent = (
            proposals_by_id.get(proposal.get("parent_proposal_id", ""))
            if proposal.get("parent_proposal_id")
            else None
        )
        proposal_judgments = j_by_pid.get(proposal["proposal_id"], [])
        rating = (
            branch_curation.get(proposal["proposal_id"])
            if branch_curation is not None
            else None
        )
        md = _render_pack(
            proposal=proposal,
            persona=persona,
            parent=parent,
            proposal_judgments=proposal_judgments,
            scenario=scenario,
            narration=narration,
            run_id=run_id,
            branch_rating=rating,
        )
        slug = _slugify(proposal.get("move_title", "untitled"))
        path = out_dir / f"{slug}-{proposal['proposal_id'][:8]}.md"
        path.write_text(md, encoding="utf-8")
        written.append(path)

    logger.info("context_pack: wrote %d packs for run %s to %s", len(written), run_id, out_dir)
    return written


# ---- internals ----


def _is_surviving(proposal: dict[str, Any], proposal_judgments: list[dict[str, Any]]) -> bool:
    """Survival check that handles both the new round-based tree (tier_surviving
    is set inline) and the legacy final-judging path (compute from judgments).
    """
    if proposal.get("tier_surviving") is True:
        return True
    if proposal.get("tier_surviving") is False:
        return False
    if not proposal_judgments:
        return False
    plaus = [int(j["plausibility"]) for j in proposal_judgments]
    n = len(plaus)
    plaus.sort()
    med = plaus[n // 2] if n % 2 == 1 else (plaus[n // 2 - 1] + plaus[n // 2]) / 2
    wgen = sum(1 for j in proposal_judgments if j.get("would_have_generated"))
    import math as _math
    return (med >= 3) and (wgen < _math.ceil(n / 2))


def _render_pack(
    *,
    proposal: dict[str, Any],
    persona: Persona | None,
    parent: dict[str, Any] | None,
    proposal_judgments: list[dict[str, Any]],
    scenario: dict[str, Any],
    narration: dict[str, Any],
    run_id: str,
    branch_rating: dict[str, Any] | None = None,
) -> str:
    """Render one context pack as markdown."""
    lines: list[str] = []
    title = proposal.get("move_title", "(untitled move)")
    lines.append(f"# Context pack: {title}")
    lines.append("")
    lines.append(
        "> Self-contained brief on one surviving Red move. Designed to be re-fed "
        "to a new model instance to continue the option's reasoning when the "
        "wargame moves into player counter-moves."
    )
    lines.append("")

    if branch_rating is not None:
        branch = branch_rating.get("branch", "?")
        tier = branch_rating.get("wargame_prep_value", "?")
        lines.append(f"## Wargame-prep read ({branch}) — tier {tier}")
        lines.append("")
        if assumption := branch_rating.get("assumption_it_breaks", "").strip():
            lines.append(f"- **Assumption it breaks:** {assumption}")
        if cell := branch_rating.get("cell_to_run_it_against", "").strip():
            lines.append(f"- **Cell to run it against:** {cell}")
        if question := branch_rating.get("next_question_for_players", "").strip():
            lines.append(f"- **Question for players:** {question}")
        if concept := branch_rating.get("nearest_branch_concept_to_check", "").strip():
            lines.append(f"- **Branch concept stressed:** {concept}")
        if overstates := branch_rating.get("where_it_overstates", "").strip():
            lines.append(f"- **Where it overstates:** {overstates}")
        if rationale := branch_rating.get("rationale", "").strip():
            lines.append(f"- **Curator's rationale:** {rationale}")
        if refer := (branch_rating.get("refer_to_other_cell") or "").strip():
            lines.append(f"- **Refer to other cell:** {refer}")
        lines.append("")

    # ---- Persona ----
    if persona is not None:
        lines.append(f"## You are {persona.name}")
        lines.append("")
        lines.append("### Identity (Park et al. §A.1 identity seed)")
        lines.append("")
        lines.append(persona.identity_seed.strip())
        lines.append("")
        lines.append("### How you live and read")
        lines.append("")
        lines.append(persona.ethnographic_exterior.strip())
        lines.append("")
        lines.append("### Your doctrinal priors")
        lines.append("")
        lines.append(persona.doctrinal_priors.strip())
        lines.append("")
        lines.append("### What you know you don't see")
        lines.append("")
        lines.append(persona.blind_spots_and_ergonomics.strip())
        lines.append("")
    else:
        lines.append(
            "## Persona: (unknown — this proposal came through the legacy "
            "single-call generator, not a tagged persona)"
        )
        lines.append("")

    # ---- Scenario ----
    lines.append("## The scenario you were briefing")
    lines.append("")
    lines.append(_render_scenario(scenario))
    lines.append("")

    # ---- Convergence summary + absences ----
    if convergence_summary := narration.get("convergence_summary", "").strip():
        lines.append("## What the modal ensemble produced (the convergence pattern you were trying to escape)")
        lines.append("")
        lines.append(convergence_summary)
        lines.append("")

    absences = narration.get("notable_absences") or []
    if absences:
        lines.append("### Notable absences (the Stage-4 input alongside your formation)")
        lines.append("")
        for a in absences:
            line = f"- **{a.get('absence', '')}**"
            if w := a.get("why_it_might_be_proposed"):
                line += f"\n  - *Why a planner might propose:* {w}"
            if w := a.get("why_the_ensemble_missed_it"):
                line += f"\n  - *Why the ensemble missed it:* {w}"
            lines.append(line)
        lines.append("")

    cross_run = narration.get("cross_run_observations") or []
    if cross_run:
        lines.append("### Cross-run observations the Cartographer surfaced")
        lines.append("")
        for c in cross_run:
            lines.append(f"- {c}")
        lines.append("")

    # ---- The move ----
    lines.append("## Your move")
    lines.append("")
    lines.append(f"### {title}")
    lines.append("")
    if summary := proposal.get("summary", "").strip():
        lines.append(summary)
        lines.append("")

    actions = proposal.get("actions") or []
    if actions:
        lines.append("#### Actions")
        lines.append("")
        for a in actions:
            actor = a.get("actor", "?")
            action = a.get("action", "?")
            target = a.get("target", "?")
            timeline = a.get("timeline_days", "?")
            purpose = a.get("purpose", "?")
            lines.append(f"- **T+{timeline}d** [{actor}] {action}")
            lines.append(f"  - Target: {target}")
            lines.append(f"  - Purpose: {purpose}")
        lines.append("")

    if eff := proposal.get("intended_effect", "").strip():
        lines.append("#### Intended effect")
        lines.append("")
        lines.append(eff)
        lines.append("")

    if why := proposal.get("why_a_red_planner_could_justify_this", "").strip():
        lines.append("#### Why a Red planner could justify this")
        lines.append("")
        lines.append(why)
        lines.append("")

    if breaks := proposal.get("which_convergence_pattern_it_breaks", "").strip():
        lines.append("#### Convergence pattern this move breaks")
        lines.append("")
        lines.append(breaks)
        lines.append("")

    risks = proposal.get("risks_red_accepts") or []
    if risks:
        lines.append("#### Risks Red accepts")
        lines.append("")
        for r in risks:
            lines.append(f"- {r}")
        lines.append("")

    # ---- Tree lineage ----
    lines.append("## How this move came about (tree-search lineage)")
    lines.append("")
    if proposal.get("tree_depth", 0) == 0:
        lines.append(
            "First-pass option from your formation. You read the scenario and "
            "the convergence pattern, then briefed honestly from inside your "
            "doctrinal priors and ethnographic formation — without being asked "
            "to 'be off-distribution'."
        )
    else:
        axis = proposal.get("expansion_axis", "?")
        diverge = proposal.get("how_it_diverges_from_original", "")
        if parent is not None:
            parent_title = parent.get("move_title", "(unknown parent)")
            lines.append(
                f"Sibling expansion of **{parent_title}** along the **{axis}** axis "
                f"(tier {proposal.get('tree_depth', '?')}). The negative-prompting "
                f"constraint was: *generate a sibling that differs along the {axis} "
                f"axis from the original*. Your divergence: {diverge}"
            )
        else:
            lines.append(
                f"Sibling expansion (tier {proposal.get('tree_depth', '?')}) along "
                f"the **{axis}** axis. Divergence: {diverge}"
            )
    lines.append("")

    # ---- Judging ----
    lines.append("## Judging")
    lines.append("")
    if not proposal_judgments:
        lines.append("*No judgments recorded for this proposal.*")
        lines.append("")
    else:
        lines.append(
            "Five judges (3 Anthropic + 2 OpenAI by default) reviewed this in fresh "
            "contexts. Each ran two structured checks: (1) a plausibility "
            "calibration matrix on operational adjacency × leverage rigor, and (2) "
            "a 'central gambit in my default set' check that anchors the would-have-"
            "generated answer at the gambit level rather than action-level overlap."
        )
        lines.append("")
        lines.append("### Plausibility check (matrix: adjacency × leverage)")
        lines.append("")
        for j in proposal_judgments:
            jid = j.get("judge_id", "?")
            plaus = j.get("plausibility", "?")
            adj = "YES" if j.get("adjacency_found") else (
                "NO" if "adjacency_found" in j else "?"
            )
            lev = "NAMED" if j.get("leverage_named") else (
                "HAND-WAVED" if "leverage_named" in j else "?"
            )
            rationale = j.get("rationale", "")
            lines.append(f"**{jid}** — plausibility = {plaus}/5")
            lines.append(f"- Adjacency: {adj}")
            lines.append(f"- Leverage: {lev}")
            if rationale:
                lines.append(f"- Rationale:")
                lines.append(f"  > {_blockquote(rationale)}")
            lines.append("")

        lines.append("### Off-distribution check (central-gambit anchored)")
        lines.append("")
        for j in proposal_judgments:
            jid = j.get("judge_id", "?")
            wgen = j.get("would_have_generated", False)
            gambit = j.get("central_gambit", "")
            off_rationale = j.get("off_dist_rationale", "")
            lines.append(f"**{jid}** — would_have_generated = {wgen}")
            if gambit:
                lines.append(f"- Central gambit identified: *{gambit}*")
            if off_rationale:
                lines.append(f"- Detail:")
                lines.append(f"  > {_blockquote(off_rationale)}")
            lines.append("")

        lines.append("### Survival math")
        lines.append("")
        plaus_values = [int(j["plausibility"]) for j in proposal_judgments]
        plaus_values.sort()
        n = len(plaus_values)
        med = plaus_values[n // 2] if n % 2 == 1 else (plaus_values[n // 2 - 1] + plaus_values[n // 2]) / 2
        wgen_count = sum(1 for j in proposal_judgments if j.get("would_have_generated"))
        survived = _is_surviving(proposal, proposal_judgments)
        lines.append(f"- Median plausibility: **{med}**")
        lines.append(f"- Would-have-generated count: **{wgen_count}/{n}**")
        lines.append(f"- Surviving: **{'YES' if survived else 'NO'}**")
        if proposal.get("tier_surviving") is not None:
            tier_med = proposal.get("tier_median_plaus")
            tier_wgen = proposal.get("tier_wgen_count")
            lines.append(
                f"- (Round-based filter: median≥4 AND wgen≤1 — this proposal scored "
                f"med={tier_med}, wgen={tier_wgen}.)"
            )
        lines.append("")

    # ---- Footer for downstream extension ----
    lines.append("## How to extend this in the wargame")
    lines.append("")
    lines.append(
        "Feed this entire document to a new model instance as the system "
        "prompt. The model will have:"
    )
    lines.append("")
    lines.append("1. The persona's full formation (identity + ethnographic + doctrinal priors).")
    lines.append("2. The scenario as it stood at the time the move was briefed.")
    lines.append("3. The move itself + its tree-search lineage.")
    lines.append("4. Every judge's structured rationale (adjacency / leverage / gambit-level analysis).")
    lines.append("")
    lines.append(
        "Then prompt the model with the Blue counter-move (or the player team's "
        "response, or whatever the wargame's next event is) and ask: *Given the "
        "judges' critiques and the move you proposed, what does Red do next?* "
        "The persona will continue its chain of thought from the same formation "
        "and the same operational priors that produced this option."
    )
    lines.append("")
    lines.append(
        "If you want the model to react to a *different* persona's view of the "
        "same situation, swap in that persona's pack instead. The Red imagination "
        "is intentionally distributed across the persona pool; no single document "
        "captures the whole."
    )
    lines.append("")

    # ---- Audit metadata ----
    lines.append("## Audit metadata")
    lines.append("")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append(f"- Scenario ID: `{scenario.get('scenario_id', 'unknown')}`")
    lines.append(f"- Proposal ID: `{proposal['proposal_id']}`")
    if persona is not None:
        lines.append(f"- Persona ID: `{persona.id}`")
    lines.append(f"- Tree depth: {proposal.get('tree_depth', 0)}")
    if axis := proposal.get("expansion_axis"):
        lines.append(f"- Expansion axis: `{axis}`")
    if parent_id := proposal.get("parent_proposal_id"):
        lines.append(f"- Parent proposal: `{parent_id}`")
    lines.append(f"- Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    return "\n".join(lines)


def _render_scenario(scenario: dict[str, Any]) -> str:
    """Compact human-readable scenario block (not the full YAML — just the load-bearing fields)."""
    lines: list[str] = []
    if title := scenario.get("title"):
        lines.append(f"**{title}**")
        lines.append("")
    if rf := scenario.get("red_force"):
        lines.append(f"- **Red force:** {rf}")
    if bf := scenario.get("blue_force"):
        lines.append(f"- **Blue force:** {bf}")
    tf = scenario.get("timeframe", {}) or {}
    if horizon := tf.get("decision_horizon_days"):
        lines.append(f"- **Decision horizon:** {horizon} days")
    if start := tf.get("start"):
        lines.append(f"- **Start:** {start}")
    lines.append("")
    if situation := scenario.get("situation"):
        lines.append("**Situation:**")
        lines.append("")
        lines.append(situation.strip())
        lines.append("")
    goals = scenario.get("red_strategic_goals") or []
    if goals:
        lines.append("**Red strategic goals:**")
        lines.append("")
        for g in goals:
            lines.append(f"- {g}")
        lines.append("")
    if rtq := scenario.get("red_team_question"):
        lines.append("**Red-team question:**")
        lines.append("")
        lines.append(f"> {rtq.strip()}")
    return "\n".join(lines)


def _slugify(text: str, max_len: int = 60) -> str:
    """Turn a move title into a safe filename slug."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if not s:
        s = "untitled"
    return s[:max_len].rstrip("-")


def _blockquote(text: str) -> str:
    """Wrap multi-line text so each line gets the markdown blockquote prefix."""
    return text.replace("\n", "\n  > ")
