"""GenerativeAgent base class — Park et al. (2023) memory stream + retrieval + reflection.

See PROJECT_SPEC.md §4. Implemented in Tier 1 on `feature/memory`.
"""

from __future__ import annotations


class GenerativeAgent:
    """Base for persistent agents that accumulate analytical state across pipeline runs."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        raise NotImplementedError("Implemented in Tier 1 on feature/memory.")
