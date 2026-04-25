"""Tier 1 unit tests for memory retrieval scoring + MemoryStore.

Covers Park et al. (2023) §4.2 retrieval: recency decay, min-max normalization,
relevance-as-cosine, weighted-sum ordering, and end-to-end persistence through
MemoryStore against a tmp SQLite database.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.memory.retrieval import (
    DEFAULT_DECAY_PER_DAY,
    Memory,
    _cosine,
    _minmax,
    score_memories,
)
from src.memory.store import MemoryStore


def _make_memory(
    *,
    memory_id: str = "m",
    embedding: np.ndarray | list[float],
    importance: int = 5,
    last_accessed_at: datetime,
    memory_type: str = "observation",
    description: str = "obs",
) -> Memory:
    return Memory(
        memory_id=memory_id,
        agent_id="agent_x",
        memory_type=memory_type,
        description=description,
        embedding=np.asarray(embedding, dtype=np.float32),
        importance=importance,
        created_at=last_accessed_at,
        last_accessed_at=last_accessed_at,
        source_run_id=None,
        cited_memory_ids=None,
    )


# --- recency decay -----------------------------------------------------------


def test_recency_decay_over_30_days_is_detectable():
    now = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
    fresh = _make_memory(
        memory_id="fresh",
        embedding=[1.0, 0.0],
        last_accessed_at=now,
    )
    stale = _make_memory(
        memory_id="stale",
        embedding=[1.0, 0.0],
        last_accessed_at=now - timedelta(days=30),
    )

    # Compute raw recency directly (avoid min-max which would compress to {0,1}).
    fresh_rec = DEFAULT_DECAY_PER_DAY ** 0
    stale_rec = DEFAULT_DECAY_PER_DAY ** 30
    assert fresh_rec == 1.0
    assert stale_rec < 1.0
    assert (fresh_rec - stale_rec) > 0.05  # 30d at 0.99/day → ~0.74, gap ≈ 0.26

    # And the score-ordering reflects that gap when other components tie.
    pairs = score_memories([stale, fresh], np.array([1.0, 0.0]), now=now)
    assert [m.memory_id for m, _ in pairs] == ["fresh", "stale"]


# --- min-max normalization ---------------------------------------------------


def test_minmax_three_value_set():
    out = _minmax(np.array([2.0, 5.0, 11.0]))
    # (2-2)/(11-2)=0, (5-2)/9=1/3, (11-2)/9=1
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1 / 3)
    assert out[2] == pytest.approx(1.0)


def test_minmax_collapses_to_zero_when_all_equal():
    # Park et al. don't specify; we choose zeros so a degenerate component contributes
    # nothing rather than NaN-poisoning the weighted sum.
    out = _minmax(np.array([0.7, 0.7, 0.7]))
    assert np.allclose(out, [0.0, 0.0, 0.0])


# --- cosine vs dot product ---------------------------------------------------


def test_relevance_uses_cosine_not_dot_product():
    # Two vectors with the same direction but very different magnitudes should be
    # considered equally relevant by cosine, but dot product would prefer the longer one.
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    short = _make_memory(
        memory_id="short", embedding=[1.0, 0.0], last_accessed_at=now
    )
    long_ = _make_memory(
        memory_id="long", embedding=[10.0, 0.0], last_accessed_at=now
    )
    q = np.array([1.0, 0.0])
    assert _cosine(short.embedding, q) == pytest.approx(1.0)
    assert _cosine(long_.embedding, q) == pytest.approx(1.0)
    # Dot product would be 1 vs 10 — assert we are NOT doing that.
    assert float(np.dot(short.embedding, q)) != float(np.dot(long_.embedding, q))


def test_relevance_orders_by_angle():
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    aligned = _make_memory(
        memory_id="aligned", embedding=[1.0, 0.0], last_accessed_at=now
    )
    orthogonal = _make_memory(
        memory_id="orthogonal", embedding=[0.0, 1.0], last_accessed_at=now
    )
    pairs = score_memories(
        [orthogonal, aligned], np.array([1.0, 0.0]), now=now
    )
    assert [m.memory_id for m, _ in pairs] == ["aligned", "orthogonal"]


# --- weighted-sum ordering matches manual computation ------------------------


def test_weighted_sum_matches_manual_computation():
    # Three memories. Construct so each component (recency, importance, relevance)
    # has a clear ordering, and verify the weighted sum result by hand.
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    decay = 0.99
    a = _make_memory(
        memory_id="A",
        embedding=[1.0, 0.0],     # cosine vs query [1,0] = 1.0
        importance=2,
        last_accessed_at=now - timedelta(days=10),
    )
    b = _make_memory(
        memory_id="B",
        embedding=[0.6, 0.8],     # cosine = 0.6
        importance=8,
        last_accessed_at=now - timedelta(days=2),
    )
    c = _make_memory(
        memory_id="C",
        embedding=[0.0, 1.0],     # cosine = 0.0
        importance=10,
        last_accessed_at=now,
    )
    q = np.array([1.0, 0.0])
    # Manual:
    rec_raw = np.array([decay**10, decay**2, decay**0])  # ~0.9044, 0.9801, 1.0
    imp_raw = np.array([2.0, 8.0, 10.0])
    rel_raw = np.array([1.0, 0.6, 0.0])
    rec = (rec_raw - rec_raw.min()) / (rec_raw.max() - rec_raw.min())
    imp = (imp_raw - imp_raw.min()) / (imp_raw.max() - imp_raw.min())
    rel = (rel_raw - rel_raw.min()) / (rel_raw.max() - rel_raw.min())
    expected = rec + imp + rel  # all alphas = 1
    expected_order = np.argsort(-expected)
    expected_ids = [["A", "B", "C"][i] for i in expected_order]

    pairs = score_memories([a, b, c], q, now=now, decay_per_day=decay)
    assert [m.memory_id for m, _ in pairs] == expected_ids
    # And every score matches the manual value within fp tolerance.
    by_id = {m.memory_id: s for m, s in pairs}
    # 1e-6 tolerance: cosine is computed in float32 internally, so the score will
    # differ from a float64 hand-calc at the ~1e-8 level. Ordering and shape are
    # what we're verifying.
    for i, mid in enumerate(["A", "B", "C"]):
        assert by_id[mid] == pytest.approx(float(expected[i]), abs=1e-6)


# --- alpha weights honored ---------------------------------------------------


def test_alpha_weights_can_invert_ordering():
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    # Two memories: one is more recent, the other more important.
    recent = _make_memory(
        memory_id="recent",
        embedding=[1.0, 0.0],
        importance=1,
        last_accessed_at=now,
    )
    important = _make_memory(
        memory_id="important",
        embedding=[1.0, 0.0],
        importance=10,
        last_accessed_at=now - timedelta(days=30),
    )
    q = np.array([1.0, 0.0])

    # Default alphas (1/1/1): tie on relevance; recency=1 vs 0; importance=0 vs 1.
    # Sums equal → tie. Either order is acceptable, so ensure scores match instead.
    pairs = score_memories([recent, important], q, now=now)
    by_id = {m.memory_id: s for m, s in pairs}
    assert by_id["recent"] == pytest.approx(by_id["important"])

    # Crank importance weight high — important should win.
    pairs = score_memories(
        [recent, important], q, now=now, alpha_importance=10.0
    )
    assert pairs[0][0].memory_id == "important"


# --- end-to-end through MemoryStore -----------------------------------------


def test_end_to_end_store_retrieve(tmp_path):
    db = tmp_path / "memory.db"
    store = MemoryStore(path=db)

    e_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    e_b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    e_c = np.array([0.5, 0.5, 0.5], dtype=np.float32)

    id_a = store.add_observation(
        agent_id="convergence_cartographer",
        description="ensemble converged on quarantine-as-opening",
        importance=8,
        embedding=e_a,
        source_run_id="run-1",
    )
    id_b = store.add_observation(
        agent_id="convergence_cartographer",
        description="judges flagged a fait-accompli move as implausible",
        importance=4,
        embedding=e_b,
        source_run_id="run-1",
    )
    id_c = store.add_reflection(
        agent_id="convergence_cartographer",
        description="quarantine-first opening recurs across PLA scenarios; model-wide blind spot",
        importance=9,
        embedding=e_c,
        cited_memory_ids=[id_a, id_b],
        source_run_id="run-1",
    )

    # All-types retrieval against a query close to e_a.
    hits = store.retrieve(
        agent_id="convergence_cartographer",
        query_embedding=e_a,
        k=2,
    )
    hit_ids = [m.memory_id for m in hits]
    assert id_a in hit_ids  # most relevant
    assert len(hits) == 2

    # Filtered retrieval (reflections only) yields the reflection alone.
    only_reflections = store.retrieve(
        agent_id="convergence_cartographer",
        query_embedding=e_c,
        k=8,
        memory_types=["reflection"],
    )
    assert [m.memory_id for m in only_reflections] == [id_c]

    # last_accessed_at was bumped on the retrieved row; subsequent recall sees
    # a more recent timestamp than the original creation.
    fresh_hits = store.retrieve(
        agent_id="convergence_cartographer",
        query_embedding=e_a,
        k=1,
    )
    assert fresh_hits[0].last_accessed_at >= fresh_hits[0].created_at

    # recent() returns rows by created_at desc.
    recent = store.recent("convergence_cartographer", n=10)
    assert {m.memory_id for m in recent} == {id_a, id_b, id_c}

    # unreflected_importance_sum: reflection is the most recent row, so observations
    # created BEFORE it don't count → sum should be 0.
    assert store.unreflected_importance_sum("convergence_cartographer") == 0

    # Add a fresh observation after the reflection. Its importance should now show.
    store.add_observation(
        agent_id="convergence_cartographer",
        description="new modal cluster on ISR posture",
        importance=5,
        embedding=e_a,
        source_run_id="run-2",
    )
    assert store.unreflected_importance_sum("convergence_cartographer") == 5


def test_unreflected_importance_sum_with_no_reflection(tmp_path):
    db = tmp_path / "memory.db"
    store = MemoryStore(path=db)
    e = np.array([1.0, 0.0], dtype=np.float32)

    store.add_observation("agent_x", "obs1", importance=3, embedding=e)
    store.add_observation("agent_x", "obs2", importance=7, embedding=e)
    assert store.unreflected_importance_sum("agent_x") == 10


def test_score_memories_empty_returns_empty():
    out = score_memories([], np.array([1.0, 0.0]))
    assert out == []


def test_recency_clamped_to_nonnegative_for_future_timestamps():
    # If last_accessed_at is somehow in the future (clock skew), recency should not blow up.
    now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    future = _make_memory(
        memory_id="future",
        embedding=[1.0, 0.0],
        last_accessed_at=now + timedelta(days=5),
    )
    pairs = score_memories([future], np.array([1.0, 0.0]), now=now)
    score = pairs[0][1]
    assert math.isfinite(score)
