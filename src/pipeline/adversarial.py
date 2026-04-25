"""Stage 4 — Off-distribution generation via persona-rooted bounded tree search.

Architecture (PROJECT_SPEC.md §3, §5; informed by Park et al. 2023 §A.1
identity-seed pattern and Brenner-Cohen-Addad-Woodruff 2026 §2.2 tree search
with negative-prompting expansion):

  1. Select up to PERSONA_K personas from `data/personas/` via tag-match against
     the scenario_id and greedy diversity over (formation, generation, temperament).
  2. Each selected persona generates PERSONA_INIT_K initial proposals from its
     own POV — identity seed + ethnographic exterior + doctrinal priors as the
     system prompt. The persona is NOT instructed to "be off-distribution"; the
     divergence emerges from the formation.
  3. For each root proposal, generate PERSONA_EXPAND_K siblings via negative-
     prompting expansion along an axis (actor, timing, domain, or target). Tree
     depth bounded by PERSONA_TREE_DEPTH (default 2).
  4. Return all leaves to the caller (orchestrator), which hands them to the
     judge pool.

The off-distribution generator does NOT do doctrine retrieval. The architectural
test in `tests/test_pipeline_dry_run.py` enforces no `src.doctrine.retrieve`
import in this module path.

Backward compatibility: `OFF_DIST_K`, the old single-call knob, is honored in
fallback mode (when `PERSONA_K=0` is set explicitly OR no personas apply to the
scenario). Fallback path constructs `OffDistributionGenerator` (Tier-2 single-
call agent) directly.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

import numpy as np

from src.memory.store import MemoryStore, connect, init_db
from src.personas.index import load_index as load_persona_index
from src.personas.select import select_for_scenario
from src.pipeline.tree_search import TreeSearchConfig, grow_persona_tree


async def generate_off_distribution(
    convergence_summary: dict[str, Any],
    scenario: dict[str, Any],
    run_id: str,
    *,
    k: int | None = None,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
) -> list[dict[str, Any]]:
    """Generate persona-rooted off-distribution proposals via bounded tree search.

    `k` is preserved as a parameter for backward compatibility — when set, it
    overrides the persona pool path and uses the legacy single-call generator.
    Pipeline callers that want the new architecture pass k=None (default) and
    the env vars PERSONA_K / PERSONA_INIT_K / PERSONA_EXPAND_K / PERSONA_TREE_DEPTH
    drive the tree shape.

    Returns a flat list of proposal dicts including initial roots and tree-search
    siblings. Each dict carries:
      - `proposal_id` (uuid)
      - `persona_id` (None for fallback / single-call mode)
      - `parent_proposal_id` (None for roots)
      - `expansion_axis` (None for roots)
      - `tree_depth` (0 for roots, 1+ for expansions)
    Plus the off-distribution proposal schema fields (move_title, summary, etc.).
    """
    from src.pipeline.orchestrator import default_embedder  # local import to avoid cycles

    embed = embedder or default_embedder()
    mem = store or MemoryStore()

    scenario_id = scenario.get("scenario_id") or scenario.get("title", "unknown")

    # Decide path: persona tree vs single-call fallback.
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
            return proposals

    # Fallback: legacy single-call OffDistributionGenerator (Tier 2 default before personas).
    from src.agents.off_distribution_generator import OffDistributionGenerator

    fallback_k = k if k is not None else int(os.environ.get("OFF_DIST_K", "10"))
    generator = OffDistributionGenerator(embed=embed, store=mem)
    proposals = await generator.propose(
        convergence_summary=convergence_summary,
        scenario=scenario,
        run_id=run_id,
        k=fallback_k,
    )
    # Tag fallback proposals so downstream code can distinguish persona-rooted from single-call.
    for p in proposals:
        p.setdefault("persona_id", None)
        p.setdefault("parent_proposal_id", None)
        p.setdefault("expansion_axis", None)
        p.setdefault("tree_depth", 0)
    _persist_proposals(proposals, run_id)
    return proposals


def _persist_proposals(proposals: list[dict[str, Any]], run_id: str) -> None:
    init_db()
    with connect() as conn:
        for p in proposals:
            # The proposal dict carries persona_id, parent_proposal_id, expansion_axis,
            # tree_depth inline — they ride in move_json so the off_dist_proposals schema
            # doesn't change. UI / audit reads parse them out of move_json.
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
