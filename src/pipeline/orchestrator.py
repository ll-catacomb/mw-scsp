"""Pipeline orchestrator. Tier 1+ — see TASK_LEDGER.md."""

from __future__ import annotations


async def run_pipeline(scenario_path: str, run_id: str | None = None) -> str:
    """End-to-end run. Implemented in Tier 1 (`feature/pipeline`)."""
    raise NotImplementedError("Implemented in Tier 1 on feature/pipeline.")
