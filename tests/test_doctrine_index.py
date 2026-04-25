"""Tier 1 smoke tests for the doctrine corpus loader and pass-1 retriever.

Per the feature/doctrine brief:
- load_index() succeeds without warnings.
- retrieve_sync('amphibious operations', 'modal-grounding', 3) returns at least one PLA passage.
- retrieve_sync('the staff should reject this course of action', 'judge-rubric', 3)
  returns jp5-0-coa-screening first.
- Every authored passage's id is referenced from at least one other passage's `related` list
  (catches orphan passages).

No LLM calls; pass-1 keyword/topic retrieval only.
"""

from __future__ import annotations

from src.doctrine.index import DoctrineSchemaError, load_index
from src.doctrine.retrieve import retrieve_sync


def test_load_index_succeeds_without_warnings():
    """The corpus must validate cleanly with no unknown-topic warnings."""
    try:
        idx = load_index()
    except DoctrineSchemaError as e:
        raise AssertionError(f"corpus failed validation:\n{e}") from e
    assert idx.warnings == [], (
        "corpus loaded but produced topic-vocabulary warnings:\n"
        + "\n".join(idx.warnings)
    )
    # Sanity: corpus is non-trivial.
    assert len(idx.by_id) >= 25, f"expected ≥25 passages, got {len(idx.by_id)}"


def test_retrieve_amphibious_returns_pla_passage():
    """Modal-grounding query 'amphibious operations' must return at least one PLA passage."""
    hits = retrieve_sync("amphibious operations", "modal-grounding", 3)
    assert hits, "expected at least one hit for 'amphibious operations'"
    pla_hits = [h for h in hits if h["id"].startswith("pla-")]
    assert pla_hits, (
        f"expected at least one PLA passage in modal-grounding hits for "
        f"'amphibious operations'; got: {[h['id'] for h in hits]}"
    )


def test_retrieve_staff_should_reject_returns_coa_screening_first():
    """Judge-rubric query about COA rejection must return jp5-0-coa-screening first."""
    hits = retrieve_sync(
        "the staff should reject this course of action", "judge-rubric", 3,
    )
    assert hits, "expected hits for the staff-rejection query"
    assert hits[0]["id"] == "jp5-0-coa-screening", (
        f"expected jp5-0-coa-screening first; got order: {[h['id'] for h in hits]}"
    )


def test_no_orphan_passages():
    """Every passage must be referenced by at least one other passage's `related` list."""
    idx = load_index()
    referenced: set[str] = set()
    for p in idx.by_id.values():
        for ref in p.related:
            if ref != p.id:
                referenced.add(ref)
    orphans = sorted(p.id for p in idx.by_id.values() if p.id not in referenced)
    assert not orphans, (
        f"orphan passages (no other passage's `related` mentions them): {orphans}"
    )
