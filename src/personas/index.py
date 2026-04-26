"""Red-planner persona corpus loader and validator.

Walks `data/personas/**/*.md`, parses YAML frontmatter + structured body,
validates against a pydantic model, builds a `PersonaIndex` keyed by id, actor,
scenario, formation.

CLI:
    python -m src.personas.index --validate              # strict by default
    python -m src.personas.index --validate --no-strict  # downgrade unknown tags to warnings
    python -m src.personas.index --validate --quiet

See `data/personas/SCHEMA.md` for the schema.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

ALLOWED_ACTORS = frozenset({
    "pla", "iran", "hezbollah", "houthi", "iraqi-militia", "syrian-militia",
})
ALLOWED_FORMATIONS = frozenset({
    "doctrinal", "improvisational", "political", "technocratic",
})
ALLOWED_GENERATIONS = frozenset({
    "cold-war", "post-2001", "post-2014", "post-2024",
})
ALLOWED_TEMPERAMENTS = frozenset({
    "cautious", "aggressive", "patient", "risk-tolerant", "factional",
})
ALLOWED_PRIORITIES = frozenset({"high", "medium", "low"})

PRIORITY_WEIGHT = {"high": 1.0, "medium": 0.5, "low": 0.0}

# Required body sections, in order. The loader splits the body on these headings
# and stores each section as a Persona attribute. Unknown headings warn.
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


class Persona(BaseModel):
    """A single Red-planner persona. One per markdown file."""

    id: str
    name: str
    actor: str
    formation: str
    generation: str
    temperament: str
    applies_to: list[str] = Field(default_factory=list, alias="applies-to")
    priority: str
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    # Body sections, populated by the loader.
    identity_seed: str = ""
    ethnographic_exterior: str = ""
    doctrinal_priors: str = ""
    blind_spots_and_ergonomics: str = ""

    file_path: str = ""

    model_config = {"populate_by_name": True}

    @field_validator("actor")
    @classmethod
    def _check_actor(cls, v: str) -> str:
        if v not in ALLOWED_ACTORS:
            raise ValueError(f"actor={v!r} not in {sorted(ALLOWED_ACTORS)}")
        return v

    @field_validator("formation")
    @classmethod
    def _check_formation(cls, v: str) -> str:
        if v not in ALLOWED_FORMATIONS:
            raise ValueError(f"formation={v!r} not in {sorted(ALLOWED_FORMATIONS)}")
        return v

    @field_validator("generation")
    @classmethod
    def _check_generation(cls, v: str) -> str:
        if v not in ALLOWED_GENERATIONS:
            raise ValueError(f"generation={v!r} not in {sorted(ALLOWED_GENERATIONS)}")
        return v

    @field_validator("temperament")
    @classmethod
    def _check_temperament(cls, v: str) -> str:
        if v not in ALLOWED_TEMPERAMENTS:
            raise ValueError(f"temperament={v!r} not in {sorted(ALLOWED_TEMPERAMENTS)}")
        return v

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, v: str) -> str:
        if v not in ALLOWED_PRIORITIES:
            raise ValueError(f"priority={v!r} not in {sorted(ALLOWED_PRIORITIES)}")
        return v

    @field_validator("applies_to")
    @classmethod
    def _check_applies_to(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("applies-to must contain at least one scenario_id")
        return v

    def priority_weight(self) -> float:
        return PRIORITY_WEIGHT[self.priority]

    def agent_id(self) -> str:
        """The agent_id key under which this persona's memory is stored."""
        return self.id


_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass
class PersonaIndex:
    by_id: dict[str, Persona] = field(default_factory=dict)
    by_actor: dict[str, list[Persona]] = field(default_factory=lambda: defaultdict(list))
    by_scenario: dict[str, list[Persona]] = field(default_factory=lambda: defaultdict(list))
    by_formation: dict[str, list[Persona]] = field(default_factory=lambda: defaultdict(list))
    by_generation: dict[str, list[Persona]] = field(default_factory=lambda: defaultdict(list))
    warnings: list[str] = field(default_factory=list)


class PersonaSchemaError(RuntimeError):
    """Raised by --validate on hard schema violations."""


def personas_dir() -> Path:
    """Resolve the personas directory from env, default data/personas."""
    raw = os.environ.get("PERSONAS_DIR", "data/personas")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p


def _split_body_into_sections(body: str) -> dict[str, str]:
    """Split persona body markdown into the four required sections.

    Headings are matched literally (per SECTION_HEADINGS). Unknown headings end the
    current section but their content is discarded with a warning at the loader level.
    """
    # Pre-scan: find offsets of each known heading in the body.
    offsets: list[tuple[int, str]] = []
    for key, heading in SECTION_HEADINGS.items():
        idx = body.find(heading)
        if idx == -1:
            continue
        offsets.append((idx, key))
    offsets.sort()

    sections: dict[str, str] = {}
    for i, (start, key) in enumerate(offsets):
        # Body of this section starts after its heading line.
        heading = SECTION_HEADINGS[key]
        section_start = start + len(heading)
        # Ends at the next heading or end-of-body.
        section_end = offsets[i + 1][0] if i + 1 < len(offsets) else len(body)
        sections[key] = body[section_start:section_end].strip()
    return sections


def parse_persona_file(path: Path) -> Persona:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise PersonaSchemaError(f"{path}: no YAML frontmatter (expected '---' delimiters)")
    try:
        fm = yaml.safe_load(m.group("fm")) or {}
    except yaml.YAMLError as e:
        raise PersonaSchemaError(f"{path}: invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise PersonaSchemaError(f"{path}: frontmatter is not a mapping")
    body = m.group("body")
    sections = _split_body_into_sections(body)
    missing = [k for k in REQUIRED_SECTIONS if k not in sections or not sections[k].strip()]
    if missing:
        raise PersonaSchemaError(
            f"{path}: missing required body sections: {missing}. "
            f"Expected headings: {[SECTION_HEADINGS[k] for k in missing]}"
        )
    fm.update(sections)
    fm["file_path"] = str(path)
    try:
        return Persona.model_validate(fm)
    except ValidationError as e:
        raise PersonaSchemaError(f"{path}: schema violation:\n{e}") from e


def load_index(root: Path | None = None, *, strict: bool = False) -> PersonaIndex:
    """Walk the persona corpus and build the index.

    Strict-mode is mostly placeholder for future tag-vocabulary lockdown; current
    enum fields are always strict (validator rejects). The flag exists so the CLI
    can mirror `src.doctrine.index`'s ergonomics.
    """
    base = root or personas_dir()
    if not base.exists():
        raise PersonaSchemaError(f"personas directory not found: {base}")

    index = PersonaIndex()
    errors: list[str] = []
    for path in sorted(base.rglob("*.md")):
        if path.name == "SCHEMA.md" or path.name.startswith("README"):
            continue
        # Blue branch curator personas live under data/personas/branches/ and have
        # a separate schema (no actor/formation/generation). They're loaded by
        # src.personas.branches; skip them here so the Red loader doesn't trip.
        if "branches" in path.relative_to(base).parts:
            continue
        try:
            persona = parse_persona_file(path)
        except PersonaSchemaError as e:
            errors.append(str(e))
            continue
        if persona.id in index.by_id:
            other = index.by_id[persona.id].file_path
            errors.append(f"duplicate id {persona.id!r}: {persona.file_path} and {other}")
            continue
        index.by_id[persona.id] = persona
        index.by_actor[persona.actor].append(persona)
        for scenario in persona.applies_to:
            index.by_scenario[scenario].append(persona)
        index.by_formation[persona.formation].append(persona)
        index.by_generation[persona.generation].append(persona)

    if errors:
        if strict:
            raise PersonaSchemaError("\n".join(errors))
        # In non-strict mode duplicate ids and parse failures are still hard errors —
        # there's no useful "warn-only" interpretation of those. Always raise.
        raise PersonaSchemaError("\n".join(errors))
    return index


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="src.personas.index", description=__doc__)
    ap.add_argument("--validate", action="store_true",
                    help="Load and validate the persona corpus. Exit non-zero on errors.")
    ap.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True,
                    help="Strict mode (default). --no-strict downgrades non-fatal warnings.")
    ap.add_argument("--quiet", action="store_true", help="Only print errors / warnings.")
    args = ap.parse_args(argv)

    if not args.validate:
        ap.error("currently --validate is the only supported action")

    try:
        idx = load_index(strict=args.strict)
    except PersonaSchemaError as e:
        print(f"ERROR: persona corpus failed validation:\n{e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Loaded {len(idx.by_id)} persona(s) from {personas_dir()}")
        print(f"  by actor:      {dict((k, len(v)) for k, v in sorted(idx.by_actor.items()))}")
        print(f"  by formation:  {dict((k, len(v)) for k, v in sorted(idx.by_formation.items()))}")
        print(f"  by generation: {dict((k, len(v)) for k, v in sorted(idx.by_generation.items()))}")
        print(f"  by scenario:   {dict((k, len(v)) for k, v in sorted(idx.by_scenario.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
