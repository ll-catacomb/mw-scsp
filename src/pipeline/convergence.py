"""Stage 3 — Cartographer narration over the modal moves.

Tier 1 shipped a no-op placeholder; Tier 2 calls the real `ConvergenceCartographer`.
The Cartographer LLM does the cluster grouping itself in the same call that produces
the convergence summary and notable absences (no separate KMeans pass — see the
Tier-1 architecture note that lived in this file). Pre-narration `cluster_assignments`
is passed as None; the LLM groups the moves it sees.

See PROJECT_SPEC.md §3, §4.5.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from src.agents.convergence_cartographer import ConvergenceCartographer
from src.memory.store import MemoryStore


async def cartographer_narrate(
    modal_moves: list[dict[str, Any]],
    scenario: dict[str, Any],
    run_id: str,
    *,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
) -> dict[str, Any]:
    """Run the Cartographer over `modal_moves`. Returns the narration dict.

    Shape:
      {
        "convergence_summary": str,
        "clusters": [{cluster_id, theme, member_move_ids, representative_actions}, ...],
        "notable_absences": [{absence, why_it_might_be_proposed, why_the_ensemble_missed_it}, ...],
        "cross_run_observations": [str, ...],
      }
    """
    from src.pipeline.orchestrator import default_embedder  # local import to avoid cycles

    embed = embedder or default_embedder()
    mem = store or MemoryStore()
    cartographer = ConvergenceCartographer(embed=embed, store=mem)

    narration = await cartographer.narrate_convergence(
        modal_moves=modal_moves,
        cluster_assignments=None,
        scenario=scenario,
        run_id=run_id,
    )

    # Persist observation memory: this run's convergence summary, so future Cartographer
    # calls can recall it via `recall("convergence patterns relevant to {scenario}")`.
    summary_text = narration.get("convergence_summary", "")
    if summary_text:
        title = scenario.get("title") or scenario.get("scenario_id") or "scenario"
        await cartographer.observe(
            description=f"Convergence summary for {title}: {summary_text}",
            source_run_id=run_id,
        )

    return narration


# Kept for backwards compatibility with any caller still using the Tier 1 name.
def cluster_moves(moves: list[dict]) -> dict[str, Any]:
    return {
        "cluster_assignments": [None] * len(moves),
        "cluster_themes": None,
    }
