"""Stage 5 — Judge Pool. 5 fresh-context judges, mixed providers, two questions per move.

Survival per PROJECT_SPEC.md §3:
  median_plausibility >= 3 AND would_have_gen_count < ceil(N_judges / 2)

Both halves of the filter must hold. The first eliminates implausible moves; the second
eliminates moves the judges themselves would have generated (i.e. on-distribution).
"""

from __future__ import annotations

import asyncio
import math
from statistics import median
from typing import Any, Callable

import numpy as np

from src.agents.judge_pool import JudgePool
from src.memory.store import MemoryStore, connect, init_db


async def judge_proposals(
    proposals: list[dict[str, Any]],
    scenario: dict[str, Any],
    run_id: str,
    *,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
) -> list[dict[str, Any]]:
    """For each proposal: 5 judges × 2 questions. Return the flat list of judgment dicts.

    Side effects:
      - Inserts one row per judgment into `judgments`.
      - Updates each `off_dist_proposals` row with `surviving`, `median_plaus`,
        `would_gen_count`.
    """
    from src.pipeline.orchestrator import default_embedder  # local import to avoid cycles

    if not proposals:
        return []

    embed = embedder or default_embedder()
    mem = store or MemoryStore()
    pool = JudgePool(embed=embed, store=mem)

    # All proposals' fan-outs concurrently. Per-provider semaphores in the wrapper bound
    # the actual fan-out so the rate limits are respected without a global gate here.
    grouped = await asyncio.gather(
        *(
            pool.judge(p, scenario, run_id, proposal_index=i)
            for i, p in enumerate(proposals)
        )
    )

    all_judgments: list[dict[str, Any]] = []
    for j_list in grouped:
        all_judgments.extend(j_list)

    _persist_and_compute(proposals, grouped, run_id)
    return all_judgments


def compute_survival(
    proposal_judgments: list[dict[str, Any]],
) -> tuple[float, int, bool]:
    """(median_plausibility, would_gen_count, surviving). Used by tests + persist."""
    plausibilities = [j["plausibility"] for j in proposal_judgments]
    n_judges = len(plausibilities)
    med = float(median(plausibilities)) if plausibilities else 0.0
    wgc = sum(1 for j in proposal_judgments if j["would_have_generated"])
    surviving = (med >= 3) and (wgc < math.ceil(n_judges / 2))
    return med, wgc, surviving


def _persist_and_compute(
    proposals: list[dict[str, Any]],
    grouped_judgments: list[list[dict[str, Any]]],
    run_id: str,
) -> None:
    init_db()
    with connect() as conn:
        for proposal, judgments in zip(proposals, grouped_judgments, strict=True):
            for j in judgments:
                conn.execute(
                    """
                    INSERT INTO judgments (
                      judgment_id, run_id, proposal_id, judge_id,
                      plausibility, rationale, would_have_gen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        j["judgment_id"],
                        run_id,
                        j["proposal_id"],
                        j["judge_id"],
                        int(j["plausibility"]),
                        j["rationale"],
                        1 if j["would_have_generated"] else 0,
                    ),
                )

            med, wgc, surviving = compute_survival(judgments)
            conn.execute(
                """
                UPDATE off_dist_proposals
                   SET surviving = ?, median_plaus = ?, would_gen_count = ?
                 WHERE proposal_id = ?
                """,
                (1 if surviving else 0, med, wgc, proposal["proposal_id"]),
            )
