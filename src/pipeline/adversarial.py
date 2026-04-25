"""Stage 4 — Off-Distribution Generator. K=10 candidates that escape the convergence summary.

See PROJECT_SPEC.md §3, §4.5. Implemented in Tier 2 on `feature/pipeline`.
The off-distribution generator does NOT do doctrine RAG retrieval (§5).
"""

from __future__ import annotations


async def generate_off_distribution(
    convergence_summary: dict, scenario: dict, run_id: str
) -> list[dict]:
    raise NotImplementedError("Implemented in Tier 2 on feature/pipeline.")
