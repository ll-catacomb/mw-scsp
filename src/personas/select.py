"""Persona selection — pick a structurally-diverse subset for a scenario.

Given a scenario_id and a target count k, return up to k personas whose
`applies-to` includes that scenario, biased to span the formation × generation
× temperament axes so the pool isn't 6 cautious doctrinal personas.

Greedy diversity selection: anchor on `priority: high` first, then fill
remaining slots by maximising the new persona's distance from already-selected
ones in the (formation, generation, temperament) tuple space.
"""

from __future__ import annotations

import os
from typing import Iterable

from src.personas.index import Persona, PersonaIndex, load_index


def _axis_overlap(p: Persona, picked: Iterable[Persona]) -> int:
    """How many already-picked personas share at least one axis with this one.

    Lower is better — we want pickees that are *unlike* what we already have.
    """
    overlap = 0
    for q in picked:
        same = 0
        if p.formation == q.formation:
            same += 1
        if p.generation == q.generation:
            same += 1
        if p.temperament == q.temperament:
            same += 1
        # 1 axis match = mild overlap (3); 2 axes = stronger (2); 3 axes = identical type (1).
        if same >= 2:
            overlap += same
    return overlap


def select_for_scenario(
    scenario_id: str,
    k: int | None = None,
    *,
    index: PersonaIndex | None = None,
) -> list[Persona]:
    """Return up to `k` personas applicable to `scenario_id`, prioritised + diversity-spread."""
    idx = index or load_index()
    if k is None:
        k = int(os.environ.get("PERSONA_K", "6"))

    eligible = list(idx.by_scenario.get(scenario_id, []))
    if not eligible:
        return []

    # Sort eligible by (priority weight desc, id asc). Within priority we'll do greedy
    # diversity selection.
    eligible.sort(key=lambda p: (-p.priority_weight(), p.id))

    selected: list[Persona] = []
    # Always pull every `priority: high` persona first (up to k).
    high_priority = [p for p in eligible if p.priority == "high"]
    for p in high_priority:
        if len(selected) >= k:
            break
        selected.append(p)

    # Fill remaining slots greedy-diversity from the medium / low pool.
    remaining = [p for p in eligible if p not in selected]
    while len(selected) < k and remaining:
        scored = sorted(
            remaining,
            key=lambda p: (_axis_overlap(p, selected), -p.priority_weight(), p.id),
        )
        selected.append(scored[0])
        remaining.remove(scored[0])

    return selected[:k]
