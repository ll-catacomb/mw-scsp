"""Stage 3 — clustering placeholder; Cartographer narration ships in Tier 2.

Architecture decision (Tier 1, Option A in worktree-prompts/pipeline.md):

Move clustering moved off KMeans-on-embeddings to LLM-driven grouping by the
Cartographer agent (Tier 2, owned by `feature/memory`). Tier 1 ships a stable
contract — a no-op cluster_moves() that the orchestrator can call without
introducing a sentence-transformers dependency on the pipeline side. Real
cluster assignments are filled in when the Cartographer narration call is
wired up in Tier 2.

Why no-op rather than KMeans-on-summary-embeddings (Option B):

- The doctrine corpus dropped sentence-transformers when we pivoted from Chroma
  to the markdown corpus; pulling the model just for clustering is regression
  in coupling.
- The Cartographer in Tier 2 will produce both cluster assignments AND the
  notable-absences narration in a single call; computing assignments here
  twice would mean throwing one set away.
- The orchestrator's `clusters.json` artifact stays present with a stable
  shape so Tier 2's wire-up is additive only.
"""

from __future__ import annotations

from typing import Any


def cluster_moves(moves: list[dict]) -> dict[str, Any]:
    """Tier 1 placeholder. Returns a stable contract that Tier 2 fills in."""
    return {
        "cluster_assignments": [None] * len(moves),
        "cluster_themes": None,
    }
