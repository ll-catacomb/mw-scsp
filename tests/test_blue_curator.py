"""Tests for the Blue Interpretive Curator (Stage 6).

Covers:
- BluePersona corpus loading + branch enum validation
- get_curator_persona scenario routing
- _BranchRating / _CuratorOutput pydantic round-trips
- BlueCurator.curate empty-survivors path (no LLM call)
- BlueCurator.curate happy path with stubbed logged_completion
- Curator drops ratings whose proposal_id isn't a survivor (defensive)
- AST architectural lock: blue_curator.py does not import src.doctrine.*
"""

from __future__ import annotations

import ast
import asyncio
import json
import pathlib
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.agents.blue_curator import BlueCurator, _BranchRating, _CuratorOutput
from src.personas.branches import (
    BluePersona,
    BranchPersonaSchemaError,
    branches_dir,
    get_curator_persona,
    load_branch_personas,
)

# ---- corpus loading ---------------------------------------------------------


def test_branch_personas_load():
    """Both authored personas parse and have all four body sections populated."""
    personas = load_branch_personas()
    assert "usn_taiwan_planner" in personas
    assert "usaf_israel_planner" in personas
    for pid, p in personas.items():
        assert p.identity_seed.strip(), f"{pid}: identity_seed empty"
        assert p.ethnographic_exterior.strip(), f"{pid}: ethnographic_exterior empty"
        assert p.doctrinal_priors.strip(), f"{pid}: doctrinal_priors empty"
        assert p.blind_spots_and_ergonomics.strip(), f"{pid}: blind_spots_and_ergonomics empty"


def test_branch_persona_branch_enum_rejects_unknown(tmp_path):
    """branch must be one of USN/USAF/USMC/USA/USSF/CYBER."""
    bad = tmp_path / "bad.md"
    bad.write_text(
        """---
id: bad
name: Bad
branch: USCG
agent_id: blue_curator_bad
applies_to_scenario: x
---

# Identity seed (Park et al. §A.1)
seed text

# Ethnographic exterior
ext text

# Doctrinal priors
priors text

# Blind spots and ergonomics
blind text
""",
        encoding="utf-8",
    )
    with pytest.raises(BranchPersonaSchemaError):
        load_branch_personas(root=tmp_path)


def test_branches_dir_resolves():
    """Default resolution lands on data/personas/branches under the repo root."""
    p = branches_dir()
    assert p.name == "branches"
    assert p.parent.name == "personas"


# ---- scenario routing --------------------------------------------------------


def test_get_curator_persona_taiwan_picks_usn():
    persona = get_curator_persona(
        {"scenario_id": "taiwan_strait_spring_2028", "lead_branch": "USN"}
    )
    assert persona is not None
    assert persona.id == "usn_taiwan_planner"
    assert persona.branch == "USN"


def test_get_curator_persona_israel_picks_usaf():
    persona = get_curator_persona(
        {"scenario_id": "israel_me_cascade_2026", "lead_branch": "USAF"}
    )
    assert persona is not None
    assert persona.id == "usaf_israel_planner"
    assert persona.branch == "USAF"


def test_get_curator_persona_unknown_returns_none():
    assert get_curator_persona({"scenario_id": "made_up", "lead_branch": "USN"}) is None
    assert get_curator_persona({"scenario_id": "taiwan_strait_spring_2028"}) is None
    assert get_curator_persona({"lead_branch": "USN"}) is None


# ---- schema round-trip -------------------------------------------------------


def test_branch_rating_schema_roundtrip():
    fixture = {
        "proposal_id": "abc-123",
        "branch": "USN",
        "wargame_prep_value": "A",
        "assumption_it_breaks": "DMO presumes intact ISR substrate.",
        "cell_to_run_it_against": "N5 Plans cell",
        "next_question_for_players": "What if the substrate is gone on D+1?",
        "nearest_branch_concept_to_check": "DMO sensor-to-shooter latency",
        "where_it_overstates": "Assumes Tokyo will fold inside 72h.",
        "rationale": "High prep value because players will resist this.",
        "refer_to_other_cell": None,
    }
    parsed = _BranchRating.model_validate(fixture)
    assert parsed.wargame_prep_value == "A"
    dumped = parsed.model_dump()
    assert dumped["proposal_id"] == "abc-123"
    assert dumped["refer_to_other_cell"] is None


def test_curator_output_schema_roundtrip():
    payload = {
        "preamble": "The menu pressures two assumptions in the OPLAN.",
        "ratings": [
            {
                "proposal_id": "p1",
                "branch": "USAF",
                "wargame_prep_value": "B",
                "assumption_it_breaks": "x",
                "cell_to_run_it_against": "CAOC strategy",
                "next_question_for_players": "y",
                "nearest_branch_concept_to_check": "ACE",
                "where_it_overstates": "z",
                "rationale": "w",
                "refer_to_other_cell": "USCYBERCOM",
            }
        ],
    }
    out = _CuratorOutput.model_validate(payload)
    assert len(out.ratings) == 1
    assert out.ratings[0].refer_to_other_cell == "USCYBERCOM"


def test_branch_rating_rejects_invalid_branch():
    with pytest.raises(ValidationError):
        _BranchRating.model_validate(
            {
                "proposal_id": "p",
                "branch": "USCG",
                "wargame_prep_value": "A",
                "assumption_it_breaks": "x",
                "cell_to_run_it_against": "y",
                "next_question_for_players": "z",
                "nearest_branch_concept_to_check": "w",
                "where_it_overstates": "v",
                "rationale": "u",
            }
        )


def test_branch_rating_rejects_invalid_tier():
    with pytest.raises(ValidationError):
        _BranchRating.model_validate(
            {
                "proposal_id": "p",
                "branch": "USN",
                "wargame_prep_value": "D",
                "assumption_it_breaks": "x",
                "cell_to_run_it_against": "y",
                "next_question_for_players": "z",
                "nearest_branch_concept_to_check": "w",
                "where_it_overstates": "v",
                "rationale": "u",
            }
        )


# ---- BlueCurator.curate ------------------------------------------------------


def _fake_persona() -> BluePersona:
    return BluePersona(
        id="usn_taiwan_planner",
        name="Test Planner",
        branch="USN",
        agent_id="blue_curator_test",
        applies_to_scenario="test_scenario",
        identity_seed="seed",
        ethnographic_exterior="ext",
        doctrinal_priors="priors",
        blind_spots_and_ergonomics="blind",
    )


def _make_stub_completion(canned: dict[str, Any]) -> Any:
    """Stub for logged_completion that returns one canned _CuratorOutput-shaped dict."""

    async def stub(*args, **kwargs):  # noqa: ANN001
        response_format = kwargs.get("response_format")
        parsed = response_format.model_validate(canned) if response_format else None
        return {
            "call_id": "stub",
            "raw_text": json.dumps(canned),
            "parsed": parsed,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
        }

    return stub


def test_curator_handles_empty_survivors():
    """Empty survivors -> empty output, no LLM call."""
    curator = BlueCurator(persona=_fake_persona())
    out = asyncio.run(
        curator.curate(
            survivors=[],
            judgments=[],
            scenario={"scenario_id": "test_scenario", "lead_branch": "USN"},
            narration={"convergence_summary": ""},
            run_id="test-run",
        )
    )
    assert out == {"branch": "USN", "preamble": "", "ratings": []}


def test_curator_happy_path_with_stub():
    """Curator calls logged_completion once; output includes preamble + ratings."""
    survivors = [
        {
            "proposal_id": "p1",
            "move_title": "Move 1",
            "summary": "A summary",
            "actions": [{"actor": "X", "action": "do", "target": "T", "timeline_days": 1, "purpose": "P"}],
            "which_convergence_pattern_it_breaks": "cluster X",
            "risks_red_accepts": ["risk A"],
        },
        {
            "proposal_id": "p2",
            "move_title": "Move 2",
            "summary": "Another summary",
        },
    ]
    judgments = [
        {"proposal_id": "p1", "judge_id": "judge_0", "central_gambit": "gambit p1"},
    ]
    canned = {
        "preamble": "The menu pressures DMO and JOAC.",
        "ratings": [
            {
                "proposal_id": "p1",
                "branch": "USN",
                "wargame_prep_value": "A",
                "assumption_it_breaks": "ISR substrate intact",
                "cell_to_run_it_against": "N5 Plans",
                "next_question_for_players": "What if substrate is gone?",
                "nearest_branch_concept_to_check": "DMO",
                "where_it_overstates": "Tokyo fold inside 72h",
                "rationale": "high prep value",
            },
            {
                "proposal_id": "p2",
                "branch": "USN",
                "wargame_prep_value": "B",
                "assumption_it_breaks": "y",
                "cell_to_run_it_against": "z",
                "next_question_for_players": "w",
                "nearest_branch_concept_to_check": "v",
                "where_it_overstates": "u",
                "rationale": "t",
            },
        ],
    }
    stub = _make_stub_completion(canned)
    with patch("src.agents.blue_curator.logged_completion", new=stub):
        out = asyncio.run(
            BlueCurator(persona=_fake_persona()).curate(
                survivors=survivors,
                judgments=judgments,
                scenario={"scenario_id": "test_scenario", "lead_branch": "USN"},
                narration={"convergence_summary": "modal cluster description"},
                run_id="test-run",
            )
        )
    assert out["branch"] == "USN"
    assert "DMO" in out["preamble"]
    assert len(out["ratings"]) == 2
    assert {r["proposal_id"] for r in out["ratings"]} == {"p1", "p2"}
    assert all(r["branch"] == "USN" for r in out["ratings"])


def test_curator_drops_hallucinated_proposal_ids():
    """Ratings keyed to ids not in survivors are dropped silently."""
    survivors = [{"proposal_id": "real-id", "move_title": "Real", "summary": "s"}]
    canned = {
        "preamble": "preamble",
        "ratings": [
            {
                "proposal_id": "real-id",
                "branch": "USN",
                "wargame_prep_value": "A",
                "assumption_it_breaks": "x",
                "cell_to_run_it_against": "y",
                "next_question_for_players": "z",
                "nearest_branch_concept_to_check": "w",
                "where_it_overstates": "v",
                "rationale": "u",
            },
            {
                "proposal_id": "hallucinated-id",
                "branch": "USN",
                "wargame_prep_value": "B",
                "assumption_it_breaks": "x",
                "cell_to_run_it_against": "y",
                "next_question_for_players": "z",
                "nearest_branch_concept_to_check": "w",
                "where_it_overstates": "v",
                "rationale": "u",
            },
        ],
    }
    stub = _make_stub_completion(canned)
    with patch("src.agents.blue_curator.logged_completion", new=stub):
        out = asyncio.run(
            BlueCurator(persona=_fake_persona()).curate(
                survivors=survivors,
                judgments=[],
                scenario={},
                narration={},
                run_id="test-run",
            )
        )
    assert len(out["ratings"]) == 1
    assert out["ratings"][0]["proposal_id"] == "real-id"


def test_curator_overrides_branch_field_to_persona_branch():
    """If the model emits the wrong branch field, the curator forces it back."""
    survivors = [{"proposal_id": "p1", "move_title": "M", "summary": "s"}]
    canned = {
        "preamble": "preamble",
        "ratings": [
            {
                "proposal_id": "p1",
                "branch": "USAF",  # wrong — persona is USN
                "wargame_prep_value": "A",
                "assumption_it_breaks": "x",
                "cell_to_run_it_against": "y",
                "next_question_for_players": "z",
                "nearest_branch_concept_to_check": "w",
                "where_it_overstates": "v",
                "rationale": "u",
            }
        ],
    }
    stub = _make_stub_completion(canned)
    with patch("src.agents.blue_curator.logged_completion", new=stub):
        out = asyncio.run(
            BlueCurator(persona=_fake_persona()).curate(
                survivors=survivors,
                judgments=[],
                scenario={},
                narration={},
                run_id="test-run",
            )
        )
    assert out["ratings"][0]["branch"] == "USN"


# ---- architectural lock ------------------------------------------------------


def test_blue_curator_does_not_import_doctrine():
    """Defensive lock: the curator reads doctrinal priors statically through the
    persona prompt block, not via the doctrine retriever. Future edits that route
    a `from src.doctrine.retrieve import ...` here would silently re-couple the
    interpretive read to the corpus, weakening the demo's separation-of-concerns story.
    """
    src_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "agents"
        / "blue_curator.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "doctrine" not in module.lower(), (
                f"blue_curator.py imports from {module!r}; the curator must not "
                "retrieve doctrine."
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "doctrine" not in alias.name.lower(), (
                    f"blue_curator.py imports {alias.name!r}; the curator must not "
                    "retrieve doctrine."
                )
