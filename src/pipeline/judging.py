"""Stage 5 — Judge Pool. 5 fresh-context judges, mixed providers, two questions per move.

Survival: median plausibility >= 3 AND would_have_generated_count < ceil(N_judges / 2).
See PROJECT_SPEC.md §3. Implemented in Tier 2 on `feature/pipeline`.
"""

from __future__ import annotations


async def judge_proposals(proposals: list[dict], scenario: dict, run_id: str) -> list[dict]:
    raise NotImplementedError("Implemented in Tier 2 on feature/pipeline.")
