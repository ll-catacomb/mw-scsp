"""Stage 4 — Off-Distribution Generator. K candidates that escape the convergence summary.

The off-distribution generator does NOT do doctrine retrieval (PROJECT_SPEC.md §5).
This module deliberately does not import `src.doctrine.retrieve`; the architectural
test in `tests/test_pipeline_dry_run.py` enforces that.

K is configurable via the `OFF_DIST_K` env var (default 10). Madeleine flagged that
K=10 may not surface enough true outliers — kept knob external so a future scaling
pass can crank without code change.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

import numpy as np

from src.agents.off_distribution_generator import OffDistributionGenerator
from src.memory.store import MemoryStore, connect, init_db


async def generate_off_distribution(
    convergence_summary: dict[str, Any],
    scenario: dict[str, Any],
    run_id: str,
    *,
    k: int | None = None,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
) -> list[dict[str, Any]]:
    """Generate K off-distribution proposals; persist to off_dist_proposals; return dicts."""
    from src.pipeline.orchestrator import default_embedder  # local import to avoid cycles

    if k is None:
        k = int(os.environ.get("OFF_DIST_K", "10"))

    embed = embedder or default_embedder()
    mem = store or MemoryStore()
    generator = OffDistributionGenerator(embed=embed, store=mem)

    proposals = await generator.propose(
        convergence_summary=convergence_summary,
        scenario=scenario,
        run_id=run_id,
        k=k,
    )

    _persist_proposals(proposals, run_id)
    return proposals


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
