"""Off-Distribution Generator — generative agent for Stage 4.

Memory: previously proposed off-distribution moves with their plausibility / survival outcomes.
Instructed not to repeat near-duplicates. See PROJECT_SPEC.md §3, §4.5. Implemented in Tier 2.
"""

from __future__ import annotations

from .base import GenerativeAgent


class OffDistributionGenerator(GenerativeAgent):
    pass
