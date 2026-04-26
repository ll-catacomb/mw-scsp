"""Tests for the persona corpus, selector, and tree-search expansion logic.

Doesn't make real LLM calls. The tree-search test mocks `logged_completion`
so the persona-rooted expansion can be exercised offline.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from src.personas.index import (
    ALLOWED_ACTORS,
    ALLOWED_FORMATIONS,
    ALLOWED_GENERATIONS,
    ALLOWED_TEMPERAMENTS,
    Persona,
    PersonaSchemaError,
    load_index,
)
from src.personas.select import select_for_scenario
from src.pipeline.tree_search import EXPANSION_AXES, TreeSearchConfig, grow_persona_tree


# ---- corpus validity ----------------------------------------------------------


def test_corpus_loads_clean():
    idx = load_index()
    assert len(idx.by_id) >= 6
    # Both scenarios covered.
    assert "taiwan_strait_spring_2028" in idx.by_scenario
    assert "israel_me_cascade_2026" in idx.by_scenario
    # Each scenario has at least 3 personas.
    assert len(idx.by_scenario["taiwan_strait_spring_2028"]) >= 3
    assert len(idx.by_scenario["israel_me_cascade_2026"]) >= 3


def test_every_persona_has_required_body_sections():
    idx = load_index()
    for p in idx.by_id.values():
        assert p.identity_seed.strip(), f"{p.id}: missing identity seed"
        assert p.ethnographic_exterior.strip(), f"{p.id}: missing ethnographic exterior"
        assert p.doctrinal_priors.strip(), f"{p.id}: missing doctrinal priors"
        assert p.blind_spots_and_ergonomics.strip(), f"{p.id}: missing blind spots"


def test_persona_enum_fields_match_controlled_vocab():
    idx = load_index()
    for p in idx.by_id.values():
        assert p.actor in ALLOWED_ACTORS, f"{p.id} actor={p.actor!r}"
        assert p.formation in ALLOWED_FORMATIONS, f"{p.id} formation={p.formation!r}"
        assert p.generation in ALLOWED_GENERATIONS, f"{p.id} generation={p.generation!r}"
        assert p.temperament in ALLOWED_TEMPERAMENTS, f"{p.id} temperament={p.temperament!r}"


# ---- selector -----------------------------------------------------------------


def test_selector_returns_personas_only_for_matching_scenario():
    selected = select_for_scenario("taiwan_strait_spring_2028", k=10)
    for p in selected:
        assert "taiwan_strait_spring_2028" in p.applies_to, (
            f"{p.id} selected for taiwan but applies-to is {p.applies_to}"
        )


def test_selector_caps_at_k():
    selected_2 = select_for_scenario("taiwan_strait_spring_2028", k=2)
    selected_5 = select_for_scenario("taiwan_strait_spring_2028", k=5)
    assert len(selected_2) == 2
    assert len(selected_5) >= 2  # may be < 5 if corpus has fewer; current corpus has 3


def test_selector_spans_formation_axis_when_possible():
    # When k >= number of distinct formations in the eligible pool, we should see
    # them all represented.
    selected = select_for_scenario("taiwan_strait_spring_2028", k=3)
    formations = {p.formation for p in selected}
    # Current Taiwan corpus has 3 different formations.
    assert len(formations) >= 3, (
        f"Taiwan persona selection is collapsing the formation axis: {formations}"
    )


def test_selector_unknown_scenario_returns_empty():
    assert select_for_scenario("nonexistent_scenario_xyz", k=6) == []


# ---- expansion axes -----------------------------------------------------------


def test_expansion_axes_have_descriptions():
    assert len(EXPANSION_AXES) >= 4
    for name, description in EXPANSION_AXES:
        assert name and isinstance(name, str)
        assert len(description) > 50, f"axis {name!r} description is too thin"


# ---- tree search (mocked LLM) -------------------------------------------------


def _stub_embed(text: str, *, is_query: bool) -> np.ndarray:
    # Deterministic per-text vector; small dim to keep tests fast.
    rng = np.random.default_rng(abs(hash(text)) % (2**32))
    return rng.standard_normal(8).astype(np.float32)


def _make_stub_completion(canned_responses: list[Any]) -> Any:
    """Return an async stub for `logged_completion`.

    Each call pops a canned response from the front of the list. If the call
    declares a `response_format=` pydantic schema, the stub parses the canned
    dict into that schema and puts it in result["parsed"] — mirroring what the
    real wrapper does on a successful structured-output call.
    """
    iterator = iter(canned_responses)

    async def stub(*args, **kwargs):  # noqa: D401, ANN001
        nxt = next(iterator)
        raw_text = nxt if isinstance(nxt, str) else json.dumps(nxt)
        response_format = kwargs.get("response_format")
        parsed = None
        if response_format is not None:
            payload = nxt if isinstance(nxt, dict) else json.loads(raw_text)
            parsed = response_format.model_validate(payload)
        return {
            "call_id": "stub",
            "raw_text": raw_text,
            "parsed": parsed,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
        }

    return stub


def _build_proposal_payload(title: str) -> dict[str, Any]:
    return {
        "proposals": [
            {
                "move_title": title,
                "summary": f"summary for {title}",
                "actions": [
                    {
                        "actor": "X",
                        "action": "Y",
                        "target": "Z",
                        "timeline_days": 1,
                        "purpose": "P",
                    }
                ],
                "intended_effect": "stated intent",
                "why_a_red_planner_could_justify_this": "named anchor + goal + relaxed constraint",
                "which_convergence_pattern_it_breaks": "modal cluster — assumption violated",
                "risks_red_accepts": ["specific Blue countermove A", "specific failure condition B"],
            }
        ]
    }


def _build_sibling_payload(title: str) -> dict[str, Any]:
    return {
        "siblings": [
            {
                "move_title": f"sibling: {title}",
                "summary": "sibling summary",
                "actions": [
                    {
                        "actor": "X'",
                        "action": "Y'",
                        "target": "Z'",
                        "timeline_days": 2,
                        "purpose": "P'",
                    }
                ],
                "intended_effect": "stated intent (sibling)",
                "how_it_diverges_from_original": "sibling diverges along the requested axis",
                "why_a_red_planner_could_justify_this": "anchor + goal + relaxed constraint",
                "which_convergence_pattern_it_breaks": "cluster — different assumption",
                "risks_red_accepts": ["sibling-specific Blue countermove"],
            }
        ]
    }


@pytest.mark.asyncio
async def test_tree_search_runs_initial_then_expansion(tmp_path):
    from src.memory.store import MemoryStore

    store = MemoryStore(path=tmp_path / "memory.db")
    idx = load_index()
    personas = select_for_scenario("taiwan_strait_spring_2028", k=2, index=idx)
    assert len(personas) == 2

    # 2 personas × 1 init each = 2 root calls; each root → 1 sibling expansion call.
    # Plus 4 importance-score calls (one per proposal observed).
    cfg = TreeSearchConfig(persona_k=2, persona_init_k=1, persona_expand_k=1, tree_depth=2)

    # Build canned responses. Order matters: gather is parallel so stub MUST return
    # an envelope independent of order; we use the same payload shape for both
    # personas to make this robust.
    canned: list[Any] = []
    # 2 initial-generation calls (one per persona) + 2 importance scorings for the roots
    canned.append(_build_proposal_payload("initial-A"))
    canned.append({"rating": 7})  # importance for the root
    canned.append(_build_proposal_payload("initial-B"))
    canned.append({"rating": 6})
    # 2 expansion calls (one per root) + 2 importance scorings for the siblings
    canned.append(_build_sibling_payload("sib-A"))
    canned.append({"rating": 8})
    canned.append(_build_sibling_payload("sib-B"))
    canned.append({"rating": 8})

    # logged_completion is imported into the agent modules at import time, so we
    # have to patch each import site rather than the wrapper module itself.
    import src.agents.base
    import src.agents.red_planner

    stub = _make_stub_completion(canned)
    with patch.object(src.agents.base, "logged_completion", new=stub), \
         patch.object(src.agents.red_planner, "logged_completion", new=stub):
        leaves = await grow_persona_tree(
            personas=personas,
            scenario={"scenario_id": "taiwan_strait_spring_2028", "title": "Taiwan"},
            convergence_summary={
                "convergence_summary": "ensemble converged",
                "clusters": [{"cluster_id": 0, "theme": "quarantine"}],
                "notable_absences": [],
            },
            run_id="test-run",
            embed=_stub_embed,
            store=store,
            config=cfg,
        )

    # Expect 2 roots + 2 siblings = 4 leaves.
    assert len(leaves) == 4
    roots = [p for p in leaves if p["tree_depth"] == 0]
    siblings = [p for p in leaves if p["tree_depth"] == 1]
    assert len(roots) == 2
    assert len(siblings) == 2

    # Each sibling carries a parent reference and an expansion axis.
    for s in siblings:
        assert s["parent_proposal_id"] in {r["proposal_id"] for r in roots}
        assert s["expansion_axis"] in {a for a, _ in EXPANSION_AXES}
        assert s["persona_id"] in {p.id for p in personas}


# ---- architectural test ------------------------------------------------------


def test_adversarial_does_not_import_doctrine_retrieve():
    """The off-distribution generator must NOT do doctrine retrieval (PROJECT_SPEC.md §5)."""
    import ast
    import pathlib

    src_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "pipeline"
        / "adversarial.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "doctrine" not in module.lower(), (
                f"adversarial.py imports from {module!r}; off-distribution generator must "
                "not do doctrine retrieval (PROJECT_SPEC.md §5)."
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "doctrine" not in alias.name.lower(), (
                    f"adversarial.py imports {alias.name!r}; off-distribution generator "
                    "must not do doctrine retrieval (PROJECT_SPEC.md §5)."
                )


def test_red_planner_does_not_import_doctrine_retrieve():
    """Same architectural rule for the persona generator."""
    import ast
    import pathlib

    src_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "agents"
        / "red_planner.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "doctrine" not in module.lower(), (
                f"red_planner.py imports from {module!r}; persona generator must not retrieve doctrine."
            )


def test_off_distribution_stage_has_no_doctrine_imports_anywhere():
    """The architectural commitment in PROJECT_SPEC.md §5 is that the off-distribution
    *stage as a whole* — not just one file — does not retrieve doctrine. A future edit
    that adds `from src.doctrine.retrieve import ...` to a sibling module would silently
    break the epistemological claim. This test walks every file in the off-distribution
    stage so the per-file AST checks above can't be circumvented by routing the import
    through a sibling.
    """
    import ast
    import pathlib

    src_root = pathlib.Path(__file__).resolve().parents[1] / "src"
    files_in_off_distribution_stage = [
        src_root / "pipeline" / "adversarial.py",
        src_root / "agents" / "red_planner.py",
        src_root / "pipeline" / "tree_search.py",
    ]
    for src_path in files_in_off_distribution_stage:
        assert src_path.exists(), f"expected file is missing: {src_path}"
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "doctrine" not in module.lower(), (
                    f"{src_path.relative_to(src_root)} imports from {module!r}; "
                    "the off-distribution stage as a whole must not retrieve doctrine "
                    "(PROJECT_SPEC.md §5)."
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "doctrine" not in alias.name.lower(), (
                        f"{src_path.relative_to(src_root)} imports {alias.name!r}; "
                        "the off-distribution stage as a whole must not retrieve doctrine "
                        "(PROJECT_SPEC.md §5)."
                    )


# ---- expected leaf-count math -------------------------------------------------


def test_expected_leaf_count_matches_intuition():
    # 6 personas × 2 init = 12 roots; each root produces 2 siblings → 24 expansions.
    # Total leaves = 12 + 24 = 36.
    cfg = TreeSearchConfig(persona_k=6, persona_init_k=2, persona_expand_k=2, tree_depth=2)
    assert cfg.expected_leaf_count(6) == 36

    # depth=3: 2 roots → 4 d1 → 8 d2; total = 2 + 4 + 8 = 14.
    cfg_deep = TreeSearchConfig(persona_k=2, persona_init_k=1, persona_expand_k=2, tree_depth=3)
    assert cfg_deep.expected_leaf_count(2) == 14
