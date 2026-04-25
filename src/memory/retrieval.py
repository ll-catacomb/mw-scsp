"""Park et al. (2023) §4.2 retrieval scoring.

For a candidate set of memories and a query embedding:

  recency    = decay_per_day ** days_since_last_access
  importance = stored 1–10 score
  relevance  = cosine similarity(query, memory.embedding)

Each component is min-max normalized to [0, 1] across the candidate set, then
combined as `score = a_r·recency + a_i·importance + a_v·relevance` (alpha=1 by default).

The Park paper used a per-sandbox-hour decay; our agents run intermittently across
discrete pipeline runs, so we decay per day instead (PROJECT_SPEC.md §4.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import numpy as np

DEFAULT_DECAY_PER_DAY = 0.99


@dataclass
class Memory:
    """One row from agent_memory, hydrated."""

    memory_id: str
    agent_id: str
    memory_type: str  # 'observation' | 'reflection'
    description: str
    embedding: np.ndarray
    importance: int
    created_at: datetime
    last_accessed_at: datetime
    source_run_id: str | None
    cited_memory_ids: list[str] | None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _minmax(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values.astype(np.float64)
    lo = float(values.min())
    hi = float(values.max())
    if hi - lo < 1e-12:
        return np.zeros_like(values, dtype=np.float64)
    return (values.astype(np.float64) - lo) / (hi - lo)


def score_memories(
    memories: Sequence[Memory],
    query_embedding: np.ndarray,
    *,
    now: datetime | None = None,
    decay_per_day: float = DEFAULT_DECAY_PER_DAY,
    alpha_recency: float = 1.0,
    alpha_importance: float = 1.0,
    alpha_relevance: float = 1.0,
) -> list[tuple[Memory, float]]:
    """Score `memories` against `query_embedding`. Sorted descending by score."""
    if not memories:
        return []
    now_aware = _aware(now or datetime.now(timezone.utc))
    q = np.asarray(query_embedding, dtype=np.float32)

    n = len(memories)
    recency_raw = np.empty(n, dtype=np.float64)
    importance_raw = np.empty(n, dtype=np.float64)
    relevance_raw = np.empty(n, dtype=np.float64)
    for i, mem in enumerate(memories):
        delta_days = (now_aware - _aware(mem.last_accessed_at)).total_seconds() / 86400.0
        days = max(delta_days, 0.0)
        recency_raw[i] = decay_per_day**days
        importance_raw[i] = float(mem.importance)
        relevance_raw[i] = _cosine(np.asarray(mem.embedding, dtype=np.float32), q)

    rec = _minmax(recency_raw)
    imp = _minmax(importance_raw)
    rel = _minmax(relevance_raw)
    scores = alpha_recency * rec + alpha_importance * imp + alpha_relevance * rel
    pairs = list(zip(memories, scores.tolist(), strict=True))
    pairs.sort(key=lambda p: p[1], reverse=True)
    return pairs
