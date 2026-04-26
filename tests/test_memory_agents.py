"""Tier 2 unit tests for OffDistributionGenerator, JudgePool, reflection, and summary.

`logged_completion` is mocked module-by-module so the tests stay offline. We dispatch
on the `stage` kwarg the wrapper receives, which is enough to route every call.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pytest

from src.agents.base import (
    REFLECTION_IMPORTANCE_THRESHOLD,
    GenerativeAgent,
    ImportanceRating,
    _AgentSummaryParagraph,
    _ReflectionInsight,
    _ReflectionInsights,
    _ReflectionQuestions,
)
from src.agents.judge_pool import (
    JUDGE_INSTANCES,
    JudgePool,
    _OffDistCheck,
    _PlausibilityRating,
)
from src.agents.off_distribution_generator import (
    OffDistributionGenerator,
    OffDistributionProposals,
    _Action,
    _Proposal,
)
from src.memory.store import MemoryStore, connect


# --- shared fixtures + helpers ----------------------------------------------


@pytest.fixture
def store(tmp_path):
    return MemoryStore(path=tmp_path / "memory.db")


@pytest.fixture
def embed():
    """Deterministic 8-dim embedder. Distinct strings get distinct vectors."""

    def _embed(text: str, *, is_query: bool = False) -> np.ndarray:
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        return rng.standard_normal(8).astype(np.float32)

    return _embed


def _result(parsed: Any) -> dict[str, Any]:
    return {
        "call_id": str(uuid.uuid4()),
        "raw_text": parsed.model_dump_json(),
        "parsed": parsed,
        "input_tokens": 10,
        "output_tokens": 10,
        "cost_usd": 0.0,
        "latency_ms": 1,
    }


def _make_router(handlers: dict[str, Any]):
    """Build a fake `logged_completion`. Records every call's kwargs."""
    calls: list[dict[str, Any]] = []

    async def fake_logged_completion(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        stage = kwargs["stage"]
        handler = handlers.get(stage)
        if handler is None:
            raise AssertionError(f"unmocked stage: {stage}")
        payload = handler(kwargs) if callable(handler) else handler
        return _result(payload)

    fake_logged_completion.calls = calls  # type: ignore[attr-defined]
    return fake_logged_completion


def _patch_logged_completion(monkeypatch, fake) -> None:
    """Patch every module that does `from src.llm.wrapper import logged_completion`."""
    monkeypatch.setattr("src.agents.base.logged_completion", fake)
    monkeypatch.setattr(
        "src.agents.off_distribution_generator.logged_completion", fake
    )
    monkeypatch.setattr("src.agents.judge_pool.logged_completion", fake)


# --- OffDistributionGenerator -----------------------------------------------


def _canned_proposals(k: int) -> OffDistributionProposals:
    return OffDistributionProposals(
        proposals=[
            _Proposal(
                move_title=f"Move {i}",
                summary=f"Summary {i}",
                actions=[
                    _Action(
                        actor="PLA",
                        action=f"action_{i}",
                        target=f"target_{i}",
                        timeline_days=i + 1,
                        purpose=f"purpose_{i}",
                    )
                ],
                intended_effect=f"effect {i}",
                which_convergence_pattern_it_breaks=f"pattern {i}",
                why_a_red_planner_could_justify_this=f"justification {i}",
                risks_red_accepts=[f"risk {i}"],
            )
            for i in range(k)
        ]
    )


async def test_off_distribution_generator_persists_k_observations(
    store, embed, monkeypatch
):
    k = 3
    fake = _make_router(
        {
            "4_off_distribution": _canned_proposals(k),
            "memory_creation": ImportanceRating(rating=7),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    agent = OffDistributionGenerator(embed=embed, store=store)
    convergence = {
        "convergence_summary": "Ensemble converged on quarantine-first.",
        "clusters": [
            {"cluster_id": 0, "theme": "quarantine", "member_move_ids": ["m0", "m1"]}
        ],
        "notable_absences": [
            {
                "absence": "decapitation",
                "why_it_might_be_proposed": "...",
                "why_the_ensemble_missed_it": "...",
            }
        ],
    }
    scenario = {"title": "Taiwan Strait Spring 2028", "summary": "PLA pressure."}
    proposals = await agent.propose(convergence, scenario, run_id="run-1", k=k)

    assert len(proposals) == k
    assert all("proposal_id" in p for p in proposals)
    # Every proposal got a UUID.
    ids = {p["proposal_id"] for p in proposals}
    assert len(ids) == k

    # The right prompt fired exactly once.
    off_dist_calls = [c for c in fake.calls if c["stage"] == "4_off_distribution"]
    assert len(off_dist_calls) == 1
    assert off_dist_calls[0]["model"] == "claude-opus-4-7"
    assert off_dist_calls[0]["temperature"] >= 0.9
    assert "off_distribution.md" in str(off_dist_calls[0]["prompt_path"])

    # K observations landed in memory under the right agent_id.
    assert len(store.all_for_agent("off_distribution_generator")) == k

    # And the importance prompt fired K times (one per observation).
    importance_calls = [c for c in fake.calls if c["stage"] == "memory_creation"]
    assert len(importance_calls) == k


async def test_off_distribution_generator_does_not_import_doctrine_retrieve(
    store, embed
):
    """Architectural commitment: PROJECT_SPEC.md §5 — Stage 4 does not retrieve doctrine."""
    import src.agents.off_distribution_generator as odg

    # If anyone ever wires doctrine retrieval into this module, this test fails loudly.
    assert "src.doctrine.retrieve" not in dir(odg)
    src = open(odg.__file__, encoding="utf-8").read()
    assert "from src.doctrine" not in src
    assert "import src.doctrine" not in src


# --- JudgePool ---------------------------------------------------------------


async def test_judge_pool_runs_five_judges_with_independent_calls(
    store, embed, monkeypatch
):
    fake = _make_router(
        {
            "5_judge_plausibility": _PlausibilityRating(
                adjacency_found=True,
                adjacency_evidence="2024 PLA cross-strait exercise pattern",
                leverage_named=True,
                leverage_instrument="DF-26 brigade and named target list",
                plausibility=4,
                rationale="defensible move",
            ),
            "5_judge_off_dist_check": _OffDistCheck(
                central_gambit="decapitation feint via SOF on the southern coast",
                central_gambit_in_my_default_set=False,
                would_have_generated=False,
                rationale="outside default set",
            ),
            "memory_creation": ImportanceRating(rating=4),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    pool = JudgePool(embed=embed, store=store)
    proposal = {
        "proposal_id": "prop-abc",
        "move_title": "Decapitation feint",
        "summary": "An off-distribution move.",
    }
    scenario = {"title": "Taiwan Strait Spring 2028"}
    judgments = await pool.judge(proposal, scenario, run_id="run-1", proposal_index=0)

    assert len(judgments) == 5
    judge_ids = {j["judge_id"] for j in judgments}
    assert judge_ids == {jid for jid, _ in JUDGE_INSTANCES}

    # Each judgment carries the proposal_id and a fresh judgment_id.
    assert all(j["proposal_id"] == "prop-abc" for j in judgments)
    assert len({j["judgment_id"] for j in judgments}) == 5

    # Plausibility + off-dist prompts fired once per judge → 5 + 5 calls.
    plaus = [c for c in fake.calls if c["stage"] == "5_judge_plausibility"]
    off = [c for c in fake.calls if c["stage"] == "5_judge_off_dist_check"]
    assert len(plaus) == 5
    assert len(off) == 5
    # Family routing: anthropic for judge_0..2, openai for judge_3..4.
    by_judge_plaus = {c["agent_id"]: c["model"] for c in plaus}
    assert by_judge_plaus["judge_0"].startswith("claude")
    assert by_judge_plaus["judge_3"].startswith("gpt")
    assert by_judge_plaus["judge_4"].startswith("gpt")

    # Each judge wrote one calibration observation.
    for jid, _family in JUDGE_INSTANCES:
        memories = store.all_for_agent(jid)
        assert len(memories) == 1, f"judge {jid} should have 1 calibration row"
        assert "rated proposal prop-abc" in memories[0].description


async def test_judge_pool_family_rotation_on_odd_proposal_index(
    store, embed, monkeypatch
):
    """proposal_index % 2 == 1 should put openai judges first in the gather order.

    At temp=0.2 this is structural only, but the rotation must still produce all 5
    judgments and preserve canonical judge_id ordering in the output.
    """
    fake = _make_router(
        {
            "5_judge_plausibility": _PlausibilityRating(
                adjacency_found=True,
                adjacency_evidence="generic PLA pattern",
                leverage_named=True,
                leverage_instrument="generic named instrument",
                plausibility=3,
                rationale="ok",
            ),
            "5_judge_off_dist_check": _OffDistCheck(
                central_gambit="modal move",
                central_gambit_in_my_default_set=True,
                would_have_generated=True,
                rationale="modal",
            ),
            "memory_creation": ImportanceRating(rating=3),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    pool = JudgePool(embed=embed, store=store)
    judgments = await pool.judge(
        {"proposal_id": "p1"}, {"title": "S"}, run_id="r", proposal_index=1
    )
    assert [j["judge_id"] for j in judgments] == [jid for jid, _ in JUDGE_INSTANCES]


# --- Reflection (Park et al. §4.2) ------------------------------------------


def _seed_high_importance_observations(store, embed, agent_id: str, n: int = 8) -> None:
    """Push the agent over the reflection threshold with n importance-7 observations."""
    for i in range(n):
        desc = f"observation {i}: ensemble proposed quarantine-as-opening for scenario {i}"
        store.add_observation(
            agent_id=agent_id,
            description=desc,
            importance=7,
            embedding=embed(desc, is_query=False),
            source_run_id=f"run-{i}",
        )


async def test_reflect_persists_reflections_with_citations(store, embed, monkeypatch):
    agent_id = "test_agent"
    _seed_high_importance_observations(store, embed, agent_id, n=6)

    questions = _ReflectionQuestions(
        questions=[
            "What recurring move does the ensemble converge on?",
            "Where does the convergence break?",
            "Which absences keep returning?",
        ]
    )
    insights = _ReflectionInsights(
        insights=[
            _ReflectionInsight(
                insight=f"Insight {i}: ensemble shows a consistent quarantine-first opening",
                cited_memory_indices=[1, 2, 3],
            )
            for i in range(5)
        ]
    )
    fake = _make_router(
        {
            "reflection_questions": questions,
            "reflection_insights": insights,
            "memory_creation": ImportanceRating(rating=8),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    agent = GenerativeAgent(
        agent_id=agent_id,
        agent_role="test role",
        embed=embed,
        store=store,
    )
    new_ids = await agent.reflect(source_run_id="reflect-run")

    # 3 questions × 5 insights = 15 reflection rows.
    assert len(new_ids) == 15
    rows = [m for m in store.all_for_agent(agent_id) if m.memory_type == "reflection"]
    assert len(rows) == 15
    # Each reflection row has cited_memory_ids populated. Citations may resolve to
    # observations OR earlier reflections from the same call (Park et al. Fig. 7 —
    # reflections form a tree).
    all_ids = {m.memory_id for m in store.all_for_agent(agent_id)}
    for r in rows:
        assert r.cited_memory_ids, f"reflection {r.memory_id} has no citations"
        assert all(c in all_ids for c in r.cited_memory_ids)


async def test_reflect_resets_unreflected_importance_sum(store, embed, monkeypatch):
    agent_id = "reset_agent"
    _seed_high_importance_observations(store, embed, agent_id, n=8)
    pre = store.unreflected_importance_sum(agent_id)
    assert pre >= REFLECTION_IMPORTANCE_THRESHOLD

    fake = _make_router(
        {
            "reflection_questions": _ReflectionQuestions(
                questions=["q1", "q2", "q3"]
            ),
            "reflection_insights": _ReflectionInsights(
                insights=[
                    _ReflectionInsight(
                        insight=f"i{i}", cited_memory_indices=[1]
                    )
                    for i in range(5)
                ]
            ),
            "memory_creation": ImportanceRating(rating=6),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    agent = GenerativeAgent(
        agent_id=agent_id, agent_role="role", embed=embed, store=store
    )
    new_ids = await agent.reflect(source_run_id="r")
    assert new_ids
    # All seeded observations are older than the most recent reflection — so the
    # unreflected window resets to 0.
    assert store.unreflected_importance_sum(agent_id) == 0


async def test_reflect_if_due_only_runs_when_threshold_crossed(
    store, embed, monkeypatch
):
    """Below threshold: no LLM calls, no new reflections."""
    agent_id = "below_threshold_agent"
    # 1 observation × importance 5 = 5 (well below 50).
    store.add_observation(
        agent_id=agent_id,
        description="single low-importance obs",
        importance=5,
        embedding=embed("single low-importance obs", is_query=False),
    )

    fake = _make_router({})  # empty handlers → any call would fail loudly.
    _patch_logged_completion(monkeypatch, fake)

    agent = GenerativeAgent(
        agent_id=agent_id, agent_role="role", embed=embed, store=store
    )
    new_ids = await agent.reflect_if_due(source_run_id="r")
    assert new_ids == []
    assert fake.calls == []


# --- agent_summary regenerator ----------------------------------------------


async def test_regenerate_summary_if_stale_writes_versioned_row_every_three_runs(
    store, embed, monkeypatch
):
    agent_id = "summary_agent"
    # Seed at least one memory so recall returns something for each query.
    for i in range(4):
        d = f"obs {i}"
        store.add_observation(
            agent_id=agent_id,
            description=d,
            importance=5,
            embedding=embed(d, is_query=False),
        )

    fake = _make_router(
        {
            "agent_summary": _AgentSummaryParagraph(
                paragraph="The agent's analytical disposition is measured."
            ),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    agent = GenerativeAgent(
        agent_id=agent_id, agent_role="role", embed=embed, store=store
    )

    # Calls 1, 2 → False; call 3 → True; calls 4, 5 → False; call 6 → True.
    results = []
    for n in range(1, 7):
        r = await agent.regenerate_summary_if_stale(run_count=n, source_run_id="r")
        results.append(r)
    assert results == [False, False, True, False, False, True]

    # Two summary rows — one per regen — with monotonically increasing version.
    with connect(store.path) as conn:
        rows = conn.execute(
            "SELECT version FROM agent_summary WHERE agent_id = ? ORDER BY version",
            (agent_id,),
        ).fetchall()
    assert [r["version"] for r in rows] == [1, 2]


async def test_regenerate_summary_if_stale_fires_after_new_reflection(
    store, embed, monkeypatch
):
    """A reflection landing between summary regenerations is itself a staleness trigger."""
    agent_id = "reflection_trigger_agent"
    for i in range(3):
        d = f"obs {i}"
        store.add_observation(
            agent_id=agent_id,
            description=d,
            importance=5,
            embedding=embed(d, is_query=False),
        )

    fake = _make_router(
        {
            "agent_summary": _AgentSummaryParagraph(paragraph="cached paragraph."),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    agent = GenerativeAgent(
        agent_id=agent_id, agent_role="role", embed=embed, store=store
    )

    # Run 3 hits the every-N-runs trigger; a reflection lands afterwards; run 4 must
    # still regenerate (the reflection is the staleness trigger).
    assert await agent.regenerate_summary_if_stale(3, source_run_id="r")
    # First regen wrote v1.
    store.add_reflection(
        agent_id=agent_id,
        description="cross-run pattern observed",
        importance=8,
        embedding=embed("cross-run pattern", is_query=False),
        cited_memory_ids=[],
        source_run_id="r",
    )
    assert await agent.regenerate_summary_if_stale(4, source_run_id="r")


async def test_summary_paragraph_falls_back_to_fresh_generation(
    store, embed, monkeypatch
):
    agent_id = "cold_agent"
    # Seed a single observation so the recall returns something.
    store.add_observation(
        agent_id=agent_id,
        description="agent observed quarantine convergence",
        importance=6,
        embedding=embed("agent observed quarantine convergence", is_query=False),
    )

    fake = _make_router(
        {
            "agent_summary": _AgentSummaryParagraph(
                paragraph="A measured cartographer of LLM convergence."
            ),
        }
    )
    _patch_logged_completion(monkeypatch, fake)

    agent = GenerativeAgent(
        agent_id=agent_id, agent_role="cold role", embed=embed, store=store
    )
    paragraph = await agent.summary_paragraph(query="core analytical disposition")
    assert paragraph == "A measured cartographer of LLM convergence."


async def test_summary_paragraph_returns_cached_when_present(store, embed, monkeypatch):
    agent_id = "warm_agent"
    store.write_summary(agent_id, "cached paragraph from a prior run")

    # No router needed: cached path must not call logged_completion at all.
    fake = _make_router({})
    _patch_logged_completion(monkeypatch, fake)

    agent = GenerativeAgent(
        agent_id=agent_id, agent_role="role", embed=embed, store=store
    )
    paragraph = await agent.summary_paragraph(query="anything")
    assert paragraph == "cached paragraph from a prior run"
    assert fake.calls == []
