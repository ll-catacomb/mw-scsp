"""Tier 2 dry-run tests for the pipeline wiring.

Three things this exercises without making real LLM calls:

1. `cartographer_narrate` produces the expected dict shape from a stub `logged_completion`
   and a stub embedder over an in-memory MemoryStore.
2. `judge_proposals`' survival math is correct on a hand-crafted set of judgment dicts
   (via `compute_survival`).
3. Architectural: `src.pipeline.adversarial` does NOT import `src.doctrine.retrieve`.
   PROJECT_SPEC.md §5: the off-distribution generator is doctrine-free by design.

`logged_completion` is patched at the call site (per-module imports) so the wrapper's
audit-log persistence path is bypassed entirely — the test stays offline + DB-free
for those calls. The MemoryStore points at a temp SQLite file so observation writes
still go through real CRUD.
"""

from __future__ import annotations

import ast
import asyncio
import importlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from src.pipeline.judging import compute_survival


# --- 1. cartographer_narrate shape -------------------------------------------


@pytest.mark.asyncio
async def test_cartographer_narrate_returns_expected_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_DB_PATH", str(tmp_path / "memory.db"))

    from src.memory.store import MemoryStore
    store = MemoryStore(tmp_path / "memory.db")

    # Stub embedder: deterministic + cheap, mirrors the (text, *, is_query: bool) signature.
    def stub_embed(text: str, *, is_query: bool) -> np.ndarray:
        h = abs(hash(text)) % (10**6)
        rng = np.random.default_rng(h)
        return rng.standard_normal(8).astype(np.float32)

    # Stub `logged_completion`: returns a parsed-as-pydantic narration + a dummy importance.
    from src.pipeline.schemas import OffDistributionBatch  # noqa: F401  (sanity import)
    from src.agents.convergence_cartographer import ConvergenceNarration
    from src.agents.base import ImportanceRating

    async def fake_completion(*, response_format=None, **kwargs):
        if response_format is ConvergenceNarration:
            parsed = ConvergenceNarration(
                convergence_summary="Modal ensemble converged on quarantine.",
                clusters=[
                    {
                        "cluster_id": 1,
                        "theme": "quarantine + outlying-island seizure",
                        "member_move_ids": ["a", "b"],
                        "representative_actions": ["surge CCG", "seize Dongsha"],
                    }
                ],
                notable_absences=[
                    {
                        "absence": "Pure non-kinetic infosphere campaign",
                        "why_it_might_be_proposed": "Doctrine permits.",
                        "why_the_ensemble_missed_it": "Default to kinetic anchoring.",
                    }
                ],
                cross_run_observations=[],
            )
            return {
                "call_id": "stub",
                "raw_text": parsed.model_dump_json(),
                "parsed": parsed,
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_usd": 0.0,
                "latency_ms": 1,
            }
        if response_format is ImportanceRating:
            parsed = ImportanceRating(rating=5)
            return {
                "call_id": "stub",
                "raw_text": parsed.model_dump_json(),
                "parsed": parsed,
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_usd": 0.0,
                "latency_ms": 1,
            }
        raise RuntimeError(f"unexpected response_format in test: {response_format}")

    # Patch at the call sites. `logged_completion` is imported into both the agent base
    # (for importance scoring) and the cartographer module (for narration), so we need
    # to patch both.
    monkeypatch.setattr("src.agents.convergence_cartographer.logged_completion", fake_completion)
    monkeypatch.setattr("src.agents.base.logged_completion", fake_completion)

    from src.pipeline.convergence import cartographer_narrate

    modal_moves = [
        {"move_id": "a", "move_title": "Quarantine", "summary": "blockade", "actions": []},
        {"move_id": "b", "move_title": "Dongsha seizure", "summary": "atoll", "actions": []},
    ]
    scenario = {"scenario_id": "test", "title": "Test scenario", "summary": "test"}

    narration = await cartographer_narrate(
        modal_moves,
        scenario,
        run_id="test_run",
        embedder=stub_embed,
        store=store,
    )

    assert "convergence_summary" in narration
    assert "clusters" in narration
    assert "notable_absences" in narration
    assert "cross_run_observations" in narration
    assert isinstance(narration["clusters"], list) and narration["clusters"]
    assert narration["clusters"][0]["theme"].startswith("quarantine")


# --- 2. judge_proposals survival math ----------------------------------------


def test_compute_survival_passes_when_median_3_and_minority_would_have_gen():
    # 5 judges, plausibility median = 4, would_have_gen count = 1 (< ceil(5/2)=3).
    judgments = [
        {"plausibility": 5, "would_have_generated": False},
        {"plausibility": 4, "would_have_generated": False},
        {"plausibility": 4, "would_have_generated": True},
        {"plausibility": 3, "would_have_generated": False},
        {"plausibility": 3, "would_have_generated": False},
    ]
    med, wgc, surviving = compute_survival(judgments)
    assert med == 4.0
    assert wgc == 1
    assert surviving is True


def test_compute_survival_fails_when_median_below_3():
    judgments = [
        {"plausibility": 2, "would_have_generated": False},
        {"plausibility": 2, "would_have_generated": False},
        {"plausibility": 2, "would_have_generated": False},
        {"plausibility": 5, "would_have_generated": False},
        {"plausibility": 5, "would_have_generated": False},
    ]
    med, wgc, surviving = compute_survival(judgments)
    assert med == 2.0
    assert wgc == 0
    assert surviving is False  # plausibility filter


def test_compute_survival_fails_when_majority_would_have_generated():
    judgments = [
        {"plausibility": 4, "would_have_generated": True},
        {"plausibility": 4, "would_have_generated": True},
        {"plausibility": 4, "would_have_generated": True},
        {"plausibility": 3, "would_have_generated": False},
        {"plausibility": 3, "would_have_generated": False},
    ]
    med, wgc, surviving = compute_survival(judgments)
    assert med == 4.0
    assert wgc == 3
    # ceil(5/2) = 3, so 3 is not < 3 — fails the off-distribution filter.
    assert surviving is False


def test_compute_survival_boundary_exactly_3_median_passes():
    judgments = [
        {"plausibility": 3, "would_have_generated": False},
        {"plausibility": 3, "would_have_generated": False},
        {"plausibility": 3, "would_have_generated": False},
        {"plausibility": 3, "would_have_generated": False},
        {"plausibility": 3, "would_have_generated": False},
    ]
    med, wgc, surviving = compute_survival(judgments)
    assert med == 3.0
    assert surviving is True


def test_build_menu_prefers_tier_surviving_over_legacy():
    """build_menu must use the strict round-based tree filter (`tier_surviving`)
    when annotated, not the legacy med≥3+wgen<ceil(N/2) compute_survival call.

    Regression: a Taiwan run produced 13 by legacy and 11 by tier_surviving,
    so menu.json said 13, branch_curation.json rated 13, but context_packs/
    only wrote 11. The three artifacts have to agree.
    """
    from src.pipeline.orchestrator import build_menu

    def _j(pid: str, plaus: int, wgen: bool, idx: int) -> dict:
        return {
            "proposal_id": pid,
            "judge_id": f"judge_{idx}",
            "judge_family": "test",
            "plausibility": plaus,
            "would_have_generated": wgen,
            "rationale": "",
        }

    # P1: tier says yes, legacy would say yes too — not the test case but here for sanity.
    p1 = {"proposal_id": "p1", "move_title": "P1", "tier_surviving": True}
    j1 = [_j("p1", 5, False, i) for i in range(5)]
    # P2: tier says NO (med=3 < TIER_PLAUS_FLOOR=4 default), legacy says yes.
    p2 = {"proposal_id": "p2", "move_title": "P2", "tier_surviving": False}
    j2 = [_j("p2", 3, False, i) for i in range(5)]
    # P3: tier says NO (wgen=1 > TIER_WGEN_CEIL=0 default), legacy says yes.
    p3 = {"proposal_id": "p3", "move_title": "P3", "tier_surviving": False}
    j3 = [_j("p3", 4, True, 0)] + [_j("p3", 4, False, i) for i in range(1, 5)]
    # P4: no tier_surviving annotation — legacy fallback applies; med=4 wgen=0 → True.
    p4 = {"proposal_id": "p4", "move_title": "P4"}
    j4 = [_j("p4", 4, False, i) for i in range(5)]

    _md, menu = build_menu([p1, p2, p3, p4], j1 + j2 + j3 + j4)
    surviving_ids = {e["proposal"]["proposal_id"] for e in menu["surviving"]}
    rejected_ids = {e["proposal"]["proposal_id"] for e in menu["rejected"]}
    assert surviving_ids == {"p1", "p4"}, (
        f"expected {{p1, p4}} surviving; got {surviving_ids}. "
        "tier_surviving=False must override the legacy filter; "
        "tier_surviving=missing falls back to legacy."
    )
    assert rejected_ids == {"p2", "p3"}


# --- 3. architectural: adversarial.py is doctrine-free -----------------------


def test_adversarial_does_not_import_doctrine_retrieve():
    """PROJECT_SPEC.md §5 — the off-distribution stage is doctrine-free by design.

    Walks the AST of `src/pipeline/adversarial.py` to assert no `import src.doctrine`
    or `from src.doctrine` statement appears, regardless of whether it's executed.
    """
    src_path = Path(__file__).resolve().parents[1] / "src" / "pipeline" / "adversarial.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("src.doctrine"), (
                    f"adversarial.py imports {alias.name} — but Stage 4 must be doctrine-free."
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("src.doctrine"), (
                f"adversarial.py from-imports {mod} — but Stage 4 must be doctrine-free."
            )
