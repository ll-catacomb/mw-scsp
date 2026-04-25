"""Judge Pool — logical agent with 5 instances each tagged.

Per-judge calibration history (rating distribution, would-have-generated rate) is the memory.
Used to detect outlier judges and surface drift in the audit trail.
See PROJECT_SPEC.md §3, §4.5. Implemented in Tier 2 on `feature/memory`.
"""

from __future__ import annotations

from .base import GenerativeAgent


class JudgePool(GenerativeAgent):
    pass
