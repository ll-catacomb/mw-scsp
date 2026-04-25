"""Stage 3 — Cartographer narration.

The Cartographer ingests the modal moves, recalls any prior reflections from its memory,
and produces:
  - `convergence_summary` (prose, ≤200 words)
  - `clusters` (structured: cluster_id, theme, member_move_ids, representative_actions)
  - `notable_absences` (Stage-4 input: 4-8 specific moves the ensemble didn't propose)
  - `cross_run_observations` (cross-scenario patterns; empty on first run for a scenario family)

LLM-driven grouping rather than KMeans-on-embeddings. The Cartographer has the whole
move corpus in context; it's a better grouper than cosine similarity at hackathon scale.

Tier-1 placeholder `cluster_moves()` is preserved as a no-op fallback used by tests
that don't want to spin up sentence-transformers + LLM calls.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import numpy as np

from src.agents.convergence_cartographer import ConvergenceCartographer
from src.memory.store import MemoryStore

EmbedFn = Callable[..., np.ndarray]

# Module-level singleton so we don't pay sentence-transformers' model-load cost per call.
_default_embedder_singleton: EmbedFn | None = None


def make_default_embedder() -> EmbedFn:
    """Construct a sentence-transformers BGE wrapper with the asymmetric query prefix.

    Uses MEMORY_EMBEDDING_MODEL (default `BAAI/bge-base-en-v1.5`) and MEMORY_QUERY_PREFIX
    (default per RA-7). Returns a callable matching `EmbedFn`: `embed(text, *, is_query)`.
    First call loads the model (~5s on cold cache, free on subsequent calls).
    """
    global _default_embedder_singleton
    if _default_embedder_singleton is not None:
        return _default_embedder_singleton

    from sentence_transformers import SentenceTransformer

    model_name = os.environ.get("MEMORY_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
    query_prefix = os.environ.get(
        "MEMORY_QUERY_PREFIX",
        "Represent this sentence for searching relevant passages: ",
    )
    model = SentenceTransformer(model_name)

    def embed(text: str, *, is_query: bool) -> np.ndarray:
        prepared = (query_prefix + text) if is_query else text
        vec = model.encode(prepared, convert_to_numpy=True, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32)

    _default_embedder_singleton = embed
    return embed


async def cartographer_narrate(
    modal_moves: list[dict],
    scenario: dict,
    run_id: str,
    *,
    embedder: EmbedFn | None = None,
    store: MemoryStore | None = None,
) -> dict[str, Any]:
    """Run the Cartographer's `narrate_convergence` and return the parsed dict.

    Returns the ConvergenceNarration shape:
      {
        convergence_summary: str,
        clusters: [{cluster_id, theme, member_move_ids, representative_actions}],
        notable_absences: [{absence, why_it_might_be_proposed, why_the_ensemble_missed_it}],
        cross_run_observations: [str],
      }
    """
    embed_fn = embedder or make_default_embedder()
    memory_store = store or MemoryStore()
    cart = ConvergenceCartographer(embed=embed_fn, store=memory_store)
    return await cart.narrate_convergence(
        modal_moves=modal_moves,
        cluster_assignments={},  # LLM groups directly from move corpus; no precomputed clusters
        scenario=scenario,
        run_id=run_id,
    )


def cluster_moves(moves: list[dict]) -> dict[str, Any]:
    """Tier-1 no-op placeholder. Kept for tests that don't want to load sentence-transformers."""
    return {
        "cluster_assignments": [None] * len(moves),
        "cluster_themes": None,
    }
