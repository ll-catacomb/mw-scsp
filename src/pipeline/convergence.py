"""Stage 3 — embedding-cluster the modal moves; the Cartographer agent narrates them.

See PROJECT_SPEC.md §3, §4.5. Clustering scaffolded in Tier 1; Cartographer narration in Tier 2.
"""

from __future__ import annotations


async def cluster_and_summarize(modal_moves: list[dict], run_id: str) -> dict:
    raise NotImplementedError("Implemented in Tier 1 (clustering) / Tier 2 (narration).")
