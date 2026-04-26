"""Blue-side branch persona corpus loader.

Parallel to `src.personas.index` (Red), but for Blue-side wargame-prep
curators — the staff planners who read the surviving Red menu and sort it
into wargame-prep tiers for their service. One persona per service-scenario
pair (USN/Taiwan, USAF/Israel, ...). Lives at `data/personas/branches/*.md`.

Why parallel rather than extending `index.py`:
- Red `Persona` enforces actor in {pla, iran, hezbollah, ...} and
  applies-to == scenario_id semantics that don't fit a Blue curator.
- Keeping them separate means `load_index()` (Red) is untouched and the
  curator's failure mode can't break Red persona loading.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, field_validator

ALLOWED_BRANCHES = frozenset({"USN", "USAF", "USMC", "USA", "USSF", "CYBER"})

# Body section structure matches Red personas (data/personas/SCHEMA.md) so the
# downstream prompt builder can reuse the same {{ persona_identity_seed }} etc.
# placeholder pattern from red_planner_persona.md.
REQUIRED_SECTIONS = (
    "identity_seed",
    "ethnographic_exterior",
    "doctrinal_priors",
    "blind_spots_and_ergonomics",
)
SECTION_HEADINGS = {
    "identity_seed": "# Identity seed (Park et al. §A.1)",
    "ethnographic_exterior": "# Ethnographic exterior",
    "doctrinal_priors": "# Doctrinal priors",
    "blind_spots_and_ergonomics": "# Blind spots and ergonomics",
}

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


class BluePersona(BaseModel):
    """A single Blue-side branch curator persona."""

    id: str
    name: str
    branch: str  # USN / USAF / etc.
    agent_id: str  # e.g. blue_curator_usn_taiwan; keys the audit log
    applies_to_scenario: str  # scenario_id this curator handles

    identity_seed: str = ""
    ethnographic_exterior: str = ""
    doctrinal_priors: str = ""
    blind_spots_and_ergonomics: str = ""

    file_path: str = ""

    @field_validator("branch")
    @classmethod
    def _check_branch(cls, v: str) -> str:
        if v not in ALLOWED_BRANCHES:
            raise ValueError(f"branch={v!r} not in {sorted(ALLOWED_BRANCHES)}")
        return v


class BranchPersonaSchemaError(RuntimeError):
    pass


def branches_dir() -> Path:
    raw = os.environ.get("BRANCH_PERSONAS_DIR", "data/personas/branches")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p


def _split_body_into_sections(body: str) -> dict[str, str]:
    offsets: list[tuple[int, str]] = []
    for key, heading in SECTION_HEADINGS.items():
        idx = body.find(heading)
        if idx == -1:
            continue
        offsets.append((idx, key))
    offsets.sort()

    sections: dict[str, str] = {}
    for i, (start, key) in enumerate(offsets):
        heading = SECTION_HEADINGS[key]
        section_start = start + len(heading)
        section_end = offsets[i + 1][0] if i + 1 < len(offsets) else len(body)
        sections[key] = body[section_start:section_end].strip()
    return sections


def parse_branch_persona_file(path: Path) -> BluePersona:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise BranchPersonaSchemaError(
            f"{path}: no YAML frontmatter (expected '---' delimiters)"
        )
    try:
        fm = yaml.safe_load(m.group("fm")) or {}
    except yaml.YAMLError as e:
        raise BranchPersonaSchemaError(f"{path}: invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise BranchPersonaSchemaError(f"{path}: frontmatter is not a mapping")
    body = m.group("body")
    sections = _split_body_into_sections(body)
    missing = [k for k in REQUIRED_SECTIONS if k not in sections or not sections[k].strip()]
    if missing:
        raise BranchPersonaSchemaError(
            f"{path}: missing required body sections: {missing}. "
            f"Expected headings: {[SECTION_HEADINGS[k] for k in missing]}"
        )
    fm.update(sections)
    fm["file_path"] = str(path)
    try:
        return BluePersona.model_validate(fm)
    except ValidationError as e:
        raise BranchPersonaSchemaError(f"{path}: schema violation:\n{e}") from e


def load_branch_personas(root: Path | None = None) -> dict[str, BluePersona]:
    """Walk the branch persona corpus and return personas keyed by id."""
    base = root or branches_dir()
    if not base.exists():
        return {}

    out: dict[str, BluePersona] = {}
    errors: list[str] = []
    for path in sorted(base.rglob("*.md")):
        if path.name == "SCHEMA.md" or path.name.startswith("README"):
            continue
        try:
            persona = parse_branch_persona_file(path)
        except BranchPersonaSchemaError as e:
            errors.append(str(e))
            continue
        if persona.id in out:
            errors.append(
                f"duplicate id {persona.id!r}: {persona.file_path} and {out[persona.id].file_path}"
            )
            continue
        out[persona.id] = persona
    if errors:
        raise BranchPersonaSchemaError("\n".join(errors))
    return out


def get_curator_persona(
    scenario: dict,
    *,
    personas: dict[str, BluePersona] | None = None,
) -> BluePersona | None:
    """Return the curator persona for a scenario, or None if not configured.

    Selection: scenario['lead_branch'] picks the branch; persona's
    applies_to_scenario picks the scenario. The first persona whose branch
    matches and whose applies_to_scenario equals scenario_id wins.
    """
    lead_branch = scenario.get("lead_branch")
    scenario_id = scenario.get("scenario_id")
    if not lead_branch or not scenario_id:
        return None
    pool = personas if personas is not None else load_branch_personas()
    for p in pool.values():
        if p.branch == lead_branch and p.applies_to_scenario == scenario_id:
            return p
    return None
