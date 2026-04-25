"""Memory-stream retrieval: recency + importance + relevance, min-max normalized, weighted sum.

See PROJECT_SPEC.md §4.2. Implemented in Tier 1 on `feature/memory`.
"""

from __future__ import annotations


def score_memories(
    query_embedding,
    memories: list[dict],
    now,
    *,
    alpha_recency: float = 1.0,
    alpha_importance: float = 1.0,
    alpha_relevance: float = 1.0,
    decay_per_day: float = 0.995,
) -> list[tuple[dict, float]]:
    """Return memories ranked by Park et al. (2023) §4.2 retrieval score."""
    raise NotImplementedError("Implemented in Tier 1 on feature/memory.")
