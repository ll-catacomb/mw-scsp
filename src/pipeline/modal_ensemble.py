"""Stage 2 — N=8 modal-ensemble calls, mixed Claude + GPT, doctrine RAG-grounded.

See PROJECT_SPEC.md §3, §6. Implemented in Tier 1 on `feature/pipeline`.
"""

from __future__ import annotations


async def generate_modal_moves(scenario: dict, run_id: str) -> list[dict]:
    raise NotImplementedError("Implemented in Tier 1 on feature/pipeline.")
