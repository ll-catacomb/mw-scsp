"""Bounded tree search for off-distribution proposals.

Adapted from Brenner, Cohen-Addad & Woodruff 2026 "Solving an Open Problem
in Theoretical Physics using AI-Assisted Discovery" §2.2 — their Tree Search
framework with negative-prompting expansion. We adapt their three pieces to
our hackathon scale:

  • State space: each node is a candidate Red move (proposal dict).
  • Negative prompting: when expanding a parent proposal, we name a specific
    axis along which siblings must diverge, and feed already-generated
    siblings as "do-not-duplicate" history.
  • Pruning: we don't run a verifier mid-tree (judges are expensive); the
    full judge pool runs once at the leaves. Personas provide structural
    diversity at the root layer; negative prompting provides axis-bounded
    divergence at the expansion layer.

Bounded depth (default 2) and bounded branching (default 2 siblings per
parent) keep the tree small. Configurable via env vars:

  PERSONA_K           — personas to select per scenario (default 6)
  PERSONA_INIT_K      — initial proposals per persona (default 2)
  PERSONA_EXPAND_K    — siblings generated per parent (default 2)
  PERSONA_TREE_DEPTH  — max tree depth (default 2 — root + 1 expansion layer)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from src.agents.red_planner import RedPlanner
from src.memory.store import MemoryStore
from src.personas.index import Persona


# Negative-prompting axes. Each expansion round picks one axis; the persona
# generates siblings of the parent that differ specifically along it. Descriptions
# are tightened with bright-line tests after the Tier-2.5 smoke test surfaced
# loose interpretations (e.g. a `domain`-axis sibling that stayed kinetic but
# shifted target — that's the `target` axis, not `domain`).
EXPANSION_AXES: list[tuple[str, str]] = [
    (
        "actor",
        "Substitute the *category* of actor or instrument — not just the unit. "
        "If the original used a primary military force (PLAN surface, PLARF, "
        "IRGC missiles), use a different category entirely: CCG, maritime "
        "militia, civilian fleet (RoRo, COSCO), third-state proxy, non-state "
        "ally, commercial entity, intelligence service (MSS / MOIS / UFWD), "
        "diplomatic apparatus. Bright-line: swapping one PLA brigade for "
        "another PLA brigade is NOT an actor-axis shift; swapping PLAN for "
        "CCG IS.",
    ),
    (
        "timing",
        "Invert the *temporal shape* of the operation. Bright-line: a faster "
        "or slower version of the same shape is NOT a timing shift; the shape "
        "itself must change. Examples of real shape changes: fast single-pulse "
        "→ sustained slow burn; telegraphed-before-action → no-warning "
        "execute; single-decision-point → cascade-of-windows; opening-move → "
        "deferred-trigger waiting for a Blue commitment; immediate-kinetic → "
        "long political process that re-frames the deadline itself.",
    ),
    (
        "domain",
        "Cross the **kinetic ↔ non-kinetic** boundary. Bright-line: a kinetic "
        "move with a different target is NOT a domain shift. The domain axis "
        "is specifically about whether the operation is fires/maneuver/landing "
        "vs. cyber-on-substrate / lawfare / information operations / financial "
        "or insurance-market manipulation / attribution engineering / supply-"
        "chain coercion. If the original was kinetic, the sibling must produce "
        "its strategic effect through a non-kinetic mechanism. If the original "
        "was non-kinetic, the sibling must reach the same goal through kinetic "
        "means — same goal, different domain of action.",
    ),
    (
        "target",
        "Shift from the adversary's main forces to the *connective tissue* — "
        "or vice versa. Bright-line: same domain, same actor category, but "
        "what is being *acted upon* changes function. Examples: from carrier "
        "battle group → US-Philippines basing access politics; from Taiwan's "
        "armed forces → Taiwan's energy supply contracts; from PLA Rocket "
        "Force inventory → PLA Rocket Force command authorities; from "
        "Hezbollah's PGM stockpile → Lebanon's banking system. The sibling "
        "must hit a *decisive point the adversary's planning has not "
        "articulated*, not a different unit of the same target class.",
    ),
]


@dataclass
class TreeSearchConfig:
    persona_k: int = 6
    persona_init_k: int = 2
    persona_expand_k: int = 2
    tree_depth: int = 2

    @classmethod
    def from_env(cls) -> TreeSearchConfig:
        return cls(
            persona_k=int(os.environ.get("PERSONA_K", "6")),
            persona_init_k=int(os.environ.get("PERSONA_INIT_K", "2")),
            persona_expand_k=int(os.environ.get("PERSONA_EXPAND_K", "2")),
            tree_depth=int(os.environ.get("PERSONA_TREE_DEPTH", "2")),
        )

    def expected_leaf_count(self, n_personas: int) -> int:
        """Conservative upper bound on the leaf count for budgeting."""
        roots = n_personas * self.persona_init_k
        leaves = roots
        for _ in range(self.tree_depth - 1):
            leaves += roots * self.persona_expand_k
            roots = roots * self.persona_expand_k
        return leaves


async def grow_persona_tree(
    personas: list[Persona],
    scenario: dict[str, Any],
    convergence_summary: dict[str, Any],
    run_id: str,
    *,
    embed: Callable[..., np.ndarray],
    store: MemoryStore,
    config: TreeSearchConfig | None = None,
) -> list[dict[str, Any]]:
    """Grow the persona-rooted tree. Returns all leaves (initial + expansion).

    Caller (`adversarial.py`) hands the result to the judge pool, which scores
    every leaf with the existing 5-judge survival filter.
    """
    cfg = config or TreeSearchConfig.from_env()

    if not personas:
        return []

    planners = {p.id: RedPlanner(persona=p, embed=embed, store=store) for p in personas}

    # Phase 1: initial generation, parallel across personas.
    initial_tasks = [
        planners[p.id].propose_initial(
            scenario=scenario,
            convergence_summary=convergence_summary,
            run_id=run_id,
            k=cfg.persona_init_k,
        )
        for p in personas
    ]
    initial_results = await asyncio.gather(*initial_tasks)
    all_proposals: list[dict[str, Any]] = []
    for batch in initial_results:
        all_proposals.extend(batch)

    if cfg.tree_depth <= 1:
        return all_proposals

    # Phase 2: expansion. For each root, pick an axis (cycle through EXPANSION_AXES)
    # and generate siblings along it. Tracks sibling history per parent so the
    # negative-prompting "do not duplicate" works.
    current_layer = list(all_proposals)
    for depth in range(1, cfg.tree_depth):
        next_layer_tasks = []
        sibling_histories: dict[str, list[dict[str, Any]]] = {}
        axis_pick: dict[str, tuple[str, str]] = {}

        for i, parent in enumerate(current_layer):
            persona_id = parent["persona_id"]
            planner = planners.get(persona_id)
            if planner is None:
                # Defensive: persona may have been removed between runs; skip.
                continue
            axis_name, axis_description = EXPANSION_AXES[
                (i + depth) % len(EXPANSION_AXES)
            ]
            axis_pick[parent["proposal_id"]] = (axis_name, axis_description)
            sibling_histories[parent["proposal_id"]] = []

            next_layer_tasks.append(
                _expand_with_history(
                    planner,
                    parent=parent,
                    axis_name=axis_name,
                    axis_description=axis_description,
                    scenario=scenario,
                    run_id=run_id,
                    k=cfg.persona_expand_k,
                    sibling_history=sibling_histories[parent["proposal_id"]],
                )
            )

        # Run all expansions for this depth concurrently.
        layer_results = await asyncio.gather(*next_layer_tasks)
        next_layer: list[dict[str, Any]] = []
        for batch in layer_results:
            next_layer.extend(batch)
        all_proposals.extend(next_layer)
        current_layer = next_layer

    return all_proposals


async def _expand_with_history(
    planner: RedPlanner,
    *,
    parent: dict[str, Any],
    axis_name: str,
    axis_description: str,
    scenario: dict[str, Any],
    run_id: str,
    k: int,
    sibling_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expand one parent with awareness of already-generated siblings.

    Note: in the current implementation, sibling_history is passed empty because
    siblings are generated in a single batch (not iteratively within a parent).
    The hook is preserved for an iterative-batch variant later.
    """
    return await planner.propose_siblings(
        parent_proposal=parent,
        axis_name=axis_name,
        axis_description=axis_description,
        scenario=scenario,
        run_id=run_id,
        k=k,
        sibling_history=sibling_history,
    )
