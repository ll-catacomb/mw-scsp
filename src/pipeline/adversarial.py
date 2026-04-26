"""Stage 4 — Off-distribution generation via persona-rooted tree search WITH
inter-tier judging.

Architecture (PROJECT_SPEC.md §3, §5; informed by Park et al. 2023 §A.1
identity-seed pattern and Brenner-Cohen-Addad-Woodruff 2026 §2.2 tree search
with negative-prompting expansion AND verifier pruning):

  Round 1 (root generation):
    Each persona produces PERSONA_INIT_K root proposals.
  Round 1 judging:
    The full 5-judge pool scores every root with the structured plausibility
    + would-have-generated checks. Survivors are filtered by:
        median_plausibility >= TIER_PLAUS_FLOOR   (default 4)
        would_have_gen_count <= TIER_WGEN_CEIL    (default 1)
    Those defaults are stricter than the final-survival filter; the intent is
    to push the tree into "truly avant-garde but defensible" territory.
  Round 2..PERSONA_TREE_DEPTH (expansion):
    For each survivor of the previous round, generate PERSONA_EXPAND_K
    siblings via negative-prompting expansion along an axis (actor, timing,
    domain, target). Judge them. Filter survivors by the same thresholds.
    Stop when a tier produces no survivors or depth is reached.

This is the actual tree-search behavior the 2603 paper describes: the verifier
prunes ~80% at each level and only survivors are expanded. Without this loop,
the system was generating-then-passing-everything (12-19 of 18-21 surviving)
which is not a tree search — it's parallel generation with one final filter.

The off-distribution generator does NOT do doctrine retrieval. The
architectural test in `tests/test_personas.py` enforces no `src.doctrine.*`
imports anywhere in this stage.

Backward compatibility: when no judge_fn is provided, falls back to the old
non-pruned tree (`grow_persona_tree`) and returns judgments=[]. When PERSONA_K=0
or no persona applies to the scenario, falls back further to the legacy single-
call `OffDistributionGenerator`.
"""

from __future__ import annotations

import json
import logging
import math
import os
from statistics import median as _median
from typing import Any, Awaitable, Callable

import numpy as np

from src.memory.store import MemoryStore, connect, init_db
from src.personas.index import load_index as load_persona_index
from src.personas.select import select_for_scenario
from src.pipeline.tree_search import (
    TreeSearchConfig,
    generate_roots,
    generate_siblings_for_survivors,
    grow_persona_tree,
)

logger = logging.getLogger(__name__)


# Type alias for the judge callable. Takes proposals and returns flat judgment dicts.
JudgeFn = Callable[..., Awaitable[list[dict[str, Any]]]]


def _tier_thresholds() -> tuple[int, int]:
    """Return (plaus_floor, wgen_ceil) for inter-tier survival.

    Defaults are STRICTER than the final-survival filter:
      median_plausibility >= 4   (vs final's 3)
      would_have_gen_count <= 1  (vs final's < ceil(N/2)=3)
    The intent is to push the tree-search into "truly avant-garde + named
    leverage + low judge familiarity" territory, not just "anything coherent."
    """
    floor = int(os.environ.get("TIER_PLAUS_FLOOR", "4"))
    ceil = int(os.environ.get("TIER_WGEN_CEIL", "1"))
    return floor, ceil


def _filter_survivors(
    proposals: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    *,
    plaus_floor: int,
    wgen_ceil: int,
) -> list[dict[str, Any]]:
    """Apply the survival filter. Returns the proposals that pass."""
    by_pid: dict[str, list[dict[str, Any]]] = {}
    for j in judgments:
        by_pid.setdefault(j["proposal_id"], []).append(j)

    survivors: list[dict[str, Any]] = []
    for p in proposals:
        pj = by_pid.get(p["proposal_id"], [])
        if not pj:
            continue
        plaus_values = [int(j["plausibility"]) for j in pj]
        med = float(_median(plaus_values))
        wgen = sum(1 for j in pj if j.get("would_have_generated"))
        if med >= plaus_floor and wgen <= wgen_ceil:
            survivors.append(p)
    return survivors


def _annotate_with_survival(
    proposals: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    *,
    plaus_floor: int,
    wgen_ceil: int,
) -> None:
    """Mark each proposal with `tier_surviving`, `tier_median_plaus`, `tier_wgen_count`.
    Mutates `proposals` in place. Run BEFORE persistence so the metadata rides in move_json.
    """
    by_pid: dict[str, list[dict[str, Any]]] = {}
    for j in judgments:
        by_pid.setdefault(j["proposal_id"], []).append(j)

    for p in proposals:
        pj = by_pid.get(p["proposal_id"], [])
        if not pj:
            p["tier_surviving"] = False
            p["tier_median_plaus"] = None
            p["tier_wgen_count"] = None
            continue
        plaus_values = [int(j["plausibility"]) for j in pj]
        med = float(_median(plaus_values))
        wgen = sum(1 for j in pj if j.get("would_have_generated"))
        p["tier_surviving"] = (med >= plaus_floor) and (wgen <= wgen_ceil)
        p["tier_median_plaus"] = med
        p["tier_wgen_count"] = wgen


async def generate_off_distribution(
    convergence_summary: dict[str, Any],
    scenario: dict[str, Any],
    run_id: str,
    *,
    k: int | None = None,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
    judge_fn: JudgeFn | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate persona-rooted off-distribution proposals.

    With `judge_fn` (the new flow): runs interleaved per-tier judging with a
    strict survival filter. Each tier prunes; only survivors get expanded.
    Final return is (all_leaves_attempted, all_judgments) — every leaf the
    pipeline ever generated, with every judgment ever rendered. The orchestrator
    uses the judgments-as-already-persisted to skip a separate Stage-5 call.

    Without `judge_fn` (back-compat): runs the old non-pruned tree and returns
    (proposals, []). The orchestrator runs a separate Stage-5 judging.

    `k` triggers the legacy single-call fallback; persona_path is preferred.
    """
    from src.pipeline.orchestrator import default_embedder  # local import to avoid cycles

    embed = embedder or default_embedder()
    mem = store or MemoryStore()

    scenario_id = scenario.get("scenario_id") or scenario.get("title", "unknown")

    persona_k_env = int(os.environ.get("PERSONA_K", "6"))
    use_personas = persona_k_env > 0 and k is None

    if use_personas:
        try:
            persona_index = load_persona_index()
        except Exception:  # noqa: BLE001 — falls through to fallback if corpus broken
            persona_index = None

        personas = (
            select_for_scenario(scenario_id, k=persona_k_env, index=persona_index)
            if persona_index is not None
            else []
        )

        if personas:
            if judge_fn is not None:
                return await _run_round_based_tree(
                    personas=personas,
                    scenario=scenario,
                    convergence_summary=convergence_summary,
                    run_id=run_id,
                    embed=embed,
                    store=mem,
                    judge_fn=judge_fn,
                )
            # No judge_fn: fall through to the legacy non-pruned tree.
            cfg = TreeSearchConfig.from_env()
            cfg.persona_k = len(personas)
            proposals = await grow_persona_tree(
                personas=personas,
                scenario=scenario,
                convergence_summary=convergence_summary,
                run_id=run_id,
                embed=embed,
                store=mem,
                config=cfg,
            )
            _persist_proposals(proposals, run_id)
            return proposals, []

    # Fallback: legacy single-call OffDistributionGenerator. Reached when:
    #  (a) PERSONA_K=0 was set explicitly (escape hatch), OR
    #  (b) the persona corpus failed to load, OR
    #  (c) no persona is tagged `applies-to: <scenario_id>` for the active scenario.
    from src.agents.off_distribution_generator import OffDistributionGenerator

    fallback_k = k if k is not None else int(os.environ.get("OFF_DIST_K", "3"))
    logger.warning(
        "off-distribution: persona path skipped (PERSONA_K=%s, eligible=0); "
        "falling back to legacy single-call OffDistributionGenerator with k=%d. "
        "Add a persona file with applies-to: %s to use the persona path.",
        os.environ.get("PERSONA_K", "6"),
        fallback_k,
        scenario_id,
    )
    generator = OffDistributionGenerator(embed=embed, store=mem)
    proposals = await generator.propose(
        convergence_summary=convergence_summary,
        scenario=scenario,
        run_id=run_id,
        k=fallback_k,
    )
    for p in proposals:
        p.setdefault("persona_id", None)
        p.setdefault("parent_proposal_id", None)
        p.setdefault("expansion_axis", None)
        p.setdefault("tree_depth", 0)
        p.setdefault("tier", 0)
    _persist_proposals(proposals, run_id)
    return proposals, []


async def _run_round_based_tree(
    *,
    personas,
    scenario,
    convergence_summary,
    run_id,
    embed,
    store,
    judge_fn: JudgeFn,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The Brenner-style round-based tree: alternate generation and judging.
    Survivors at each tier seed the next tier's expansions.
    """
    cfg = TreeSearchConfig.from_env()
    cfg.persona_k = len(personas)
    plaus_floor, wgen_ceil = _tier_thresholds()
    logger.info(
        "stage 4 round-based tree: %d personas, init_k=%d, expand_k=%d, depth=%d, "
        "tier filter median>=%d AND wgen<=%d",
        len(personas), cfg.persona_init_k, cfg.persona_expand_k, cfg.tree_depth,
        plaus_floor, wgen_ceil,
    )

    all_proposals: list[dict[str, Any]] = []
    all_judgments: list[dict[str, Any]] = []

    # Round 0: roots.
    roots, planners = await generate_roots(
        personas=personas, scenario=scenario, convergence_summary=convergence_summary,
        run_id=run_id, embed=embed, store=store, init_k=cfg.persona_init_k,
    )
    if not roots:
        logger.warning("stage 4: no roots generated; returning empty.")
        return [], []

    _persist_proposals(roots, run_id)
    root_judgments = await judge_fn(
        proposals=roots, scenario=scenario, run_id=run_id,
        embedder=embed, store=store,
    )
    _annotate_with_survival(roots, root_judgments, plaus_floor=plaus_floor, wgen_ceil=wgen_ceil)
    all_proposals.extend(roots)
    all_judgments.extend(root_judgments)

    survivors = _filter_survivors(roots, root_judgments, plaus_floor=plaus_floor, wgen_ceil=wgen_ceil)
    logger.info(
        "round 0: %d roots → %d survivors (median>=%d, wgen<=%d)",
        len(roots), len(survivors), plaus_floor, wgen_ceil,
    )

    # Rounds 1..depth-1: expansion of survivors.
    for depth in range(1, cfg.tree_depth):
        if not survivors:
            logger.info("round %d: no survivors from previous round; halting expansion.", depth)
            break

        siblings = await generate_siblings_for_survivors(
            survivors=survivors, planners=planners, scenario=scenario, run_id=run_id,
            expand_k=cfg.persona_expand_k, depth=depth,
        )
        if not siblings:
            logger.info("round %d: expansion produced no proposals; halting.", depth)
            break

        _persist_proposals(siblings, run_id)
        sibling_judgments = await judge_fn(
            proposals=siblings, scenario=scenario, run_id=run_id,
            embedder=embed, store=store,
        )
        _annotate_with_survival(
            siblings, sibling_judgments, plaus_floor=plaus_floor, wgen_ceil=wgen_ceil,
        )
        all_proposals.extend(siblings)
        all_judgments.extend(sibling_judgments)

        survivors = _filter_survivors(
            siblings, sibling_judgments, plaus_floor=plaus_floor, wgen_ceil=wgen_ceil,
        )
        logger.info(
            "round %d: %d siblings → %d survivors",
            depth, len(siblings), len(survivors),
        )

    return all_proposals, all_judgments


def _persist_proposals(proposals: list[dict[str, Any]], run_id: str) -> None:
    init_db()
    with connect() as conn:
        for p in proposals:
            move_json = json.dumps(p, ensure_ascii=False, default=str)
            conn.execute(
                """
                INSERT INTO off_dist_proposals (
                  proposal_id, run_id, move_json, embedding,
                  surviving, median_plaus, would_gen_count
                ) VALUES (?, ?, ?, NULL, NULL, NULL, NULL)
                """,
                (p["proposal_id"], run_id, move_json),
            )
