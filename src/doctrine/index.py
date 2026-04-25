"""Doctrine corpus loader and validator.

Walks `data/doctrine/passages/**/*.md`, parses YAML frontmatter into a `Passage` pydantic
model, and builds a `DoctrineIndex` keyed for the two-pass retriever.

CLI:
    python -m src.doctrine.index --validate          # exit 0 on clean, non-zero on errors
    python -m src.doctrine.index --validate --quiet  # only print errors/warnings
    python -m src.doctrine.index --validate --strict # treat unknown topics as errors

See `data/doctrine/passages/SCHEMA.md` for the schema and PROJECT_SPEC.md §5 for the
architectural rationale (markdown corpus, no Chroma, no embeddings).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

# ---- Controlled vocabulary (mirrors SCHEMA.md "Controlled vocabulary" section) ----

ALLOWED_TYPES = frozenset({
    "definition", "principle", "procedure",
    "screening-criterion", "framework",
    "vocabulary", "warning", "example",
})
ALLOWED_PRIORITIES = frozenset({"high", "medium", "low"})
ALLOWED_APPLIES_TO = frozenset({
    "modal-grounding", "adjudication",
    "off-distribution-flag", "blue-frame-check", "judge-rubric",
})
KNOWN_TOPICS = frozenset({
    # Existing tags from SCHEMA.md.
    "cog", "decisive-points", "lines-of-operations", "phasing", "transitions",
    "branches-sequels", "operational-design", "operational-approach",
    "assumptions", "adversary-modeling", "off-distribution",
    "coa-development", "coa-screening", "wargaming", "risk",
    "termination", "systems-perspective", "pmesii", "clausewitz", "red-cell",
    # PLA / Taiwan corpus tags (RA-1, RA-3).
    "joint-firepower-strike", "joint-island-landing-campaign",
    "quarantine-vs-blockade", "decapitation", "outlying-island-seizure",
    "cross-strait-amphibious", "gray-zone", "cognitive-warfare",
    "volt-typhoon-class", "pla-rocket-force",
    # Middle East cascade tags (RA-4).
    "iran-strike-package", "axis-of-resistance-coordination",
    "hezbollah-degraded-recovery", "houthi-bab-al-mandeb",
    "iranian-aligned-iraq-syria", "centcom-posture", "tower-22-precedent",
    "april-2024-strike", "october-2024-strike",
    # Cross-cutting / RA-5 register.
    "escalation-thresholds", "attribution-engineering", "coalition-friction",
    "substrate-targeting", "third-actor-leverage", "validation-and-rigor",
    "joint-planning-process", "planning-process",
})


# Per SCHEMA.md "Retrieval contract", priority weights for pass-1 scoring.
# Pass-1 score = keyword_hits + 0.5 * topic_hits + priority_weight.
PRIORITY_WEIGHT = {"high": 1.0, "medium": 0.5, "low": 0.0}


# ---- Pydantic model ----

class Passage(BaseModel):
    """A single doctrine passage. One per markdown file under data/doctrine/passages/."""

    id: str
    source: str
    edition: str
    section: str
    page: str | int | None = None
    type: str
    priority: str
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    applies_to: list[str] = Field(default_factory=list, alias="applies-to")
    related: list[str] = Field(default_factory=list)
    notes: str | None = None

    # Populated by the loader after frontmatter parse.
    body: str = ""
    file_path: str = ""

    model_config = {"populate_by_name": True}

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in ALLOWED_TYPES:
            raise ValueError(f"type={v!r} not in {sorted(ALLOWED_TYPES)}")
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
        bad = [x for x in v if x not in ALLOWED_APPLIES_TO]
        if bad:
            raise ValueError(f"applies-to {bad!r} not in {sorted(ALLOWED_APPLIES_TO)}")
        if not v:
            raise ValueError("applies-to must contain at least one stage")
        return v

    @field_validator("keywords", "synonyms")
    @classmethod
    def _normalize_lower(cls, v: list[str]) -> list[str]:
        return [s.strip().lower() for s in v if s.strip()]

    def search_terms(self) -> set[str]:
        """All lowercase tokens this passage will match in pass-1 retrieval."""
        return {*self.keywords, *self.synonyms}

    def priority_weight(self) -> float:
        return PRIORITY_WEIGHT[self.priority]


# ---- Loader ----

# Frontmatter delimiter. We accept '---' on its own line at start of file.
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass
class DoctrineIndex:
    """Indexed corpus. Built once per pipeline run; ~< 100 files at hackathon scale."""

    by_id: dict[str, Passage] = field(default_factory=dict)
    by_topic: dict[str, list[Passage]] = field(default_factory=lambda: defaultdict(list))
    by_keyword: dict[str, list[Passage]] = field(default_factory=lambda: defaultdict(list))
    by_applies_to: dict[str, list[Passage]] = field(default_factory=lambda: defaultdict(list))
    warnings: list[str] = field(default_factory=list)

    def summary_line(self, passage: Passage) -> str:
        """One-line frontmatter description for the LLM-router fallback."""
        topics = ", ".join(passage.topics) or "(none)"
        return (
            f"{passage.id} | {passage.source} {passage.section} | "
            f"type={passage.type} pri={passage.priority} | topics: {topics}"
        )

    def all_summary_lines(self, stage: str | None = None) -> list[str]:
        passages: Iterable[Passage]
        if stage:
            passages = self.by_applies_to.get(stage, [])
        else:
            passages = self.by_id.values()
        return [self.summary_line(p) for p in passages]


class DoctrineSchemaError(RuntimeError):
    """Raised by --validate when the corpus has hard errors."""


def passages_dir() -> Path:
    """Resolve the doctrine passages directory from env, default data/doctrine/passages."""
    raw = os.environ.get("DOCTRINE_PASSAGES_DIR", "data/doctrine/passages")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p
    return p


def parse_passage_file(path: Path) -> Passage:
    """Read a markdown file, parse frontmatter, return a populated `Passage`.

    Raises:
        DoctrineSchemaError if frontmatter is missing or invalid.
    """
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise DoctrineSchemaError(f"{path}: no YAML frontmatter (expected '---' delimiters)")
    fm_raw = m.group("fm")
    body = m.group("body").strip()
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError as e:
        raise DoctrineSchemaError(f"{path}: invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise DoctrineSchemaError(f"{path}: frontmatter is not a mapping")
    fm["body"] = body
    fm["file_path"] = str(path)
    try:
        return Passage.model_validate(fm)
    except ValidationError as e:
        raise DoctrineSchemaError(f"{path}: schema violation:\n{e}") from e


def load_index(root: Path | None = None, *, strict: bool = False) -> DoctrineIndex:
    """Walk the passages tree and build the index.

    Args:
        root: directory containing the markdown corpus. Defaults to passages_dir().
        strict: if True, unknown topic tags become errors instead of warnings.

    Raises:
        DoctrineSchemaError on any hard violation: parse failure, schema fail, duplicate id,
        dangling 'related' reference, or (when strict) unknown topic.
    """
    base = root or passages_dir()
    if not base.exists():
        raise DoctrineSchemaError(f"passages directory not found: {base}")

    index = DoctrineIndex()
    errors: list[str] = []
    for path in sorted(base.rglob("*.md")):
        if path.name == "SCHEMA.md" or path.name.startswith("README"):
            continue
        try:
            passage = parse_passage_file(path)
        except DoctrineSchemaError as e:
            errors.append(str(e))
            continue
        if passage.id in index.by_id:
            other = index.by_id[passage.id].file_path
            errors.append(
                f"duplicate id {passage.id!r}: {passage.file_path} and {other}"
            )
            continue
        index.by_id[passage.id] = passage
        for kw in passage.search_terms():
            index.by_keyword[kw].append(passage)
        for topic in passage.topics:
            index.by_topic[topic].append(passage)
            if topic not in KNOWN_TOPICS:
                msg = (
                    f"{passage.file_path}: unknown topic {topic!r} "
                    "(add to KNOWN_TOPICS / SCHEMA.md if intentional)"
                )
                if strict:
                    errors.append(msg)
                else:
                    index.warnings.append(msg)
        for stage in passage.applies_to:
            index.by_applies_to[stage].append(passage)

    # Resolve `related` references. Dangling pointers are hard errors.
    for passage in index.by_id.values():
        for ref in passage.related:
            if ref not in index.by_id:
                errors.append(
                    f"{passage.file_path}: related id {ref!r} not found in corpus"
                )

    if errors:
        raise DoctrineSchemaError("\n".join(errors))
    return index


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="src.doctrine.index", description=__doc__)
    ap.add_argument("--validate", action="store_true",
                    help="Load and validate the corpus. Exit non-zero on schema errors.")
    ap.add_argument("--strict", action="store_true",
                    help="Treat unknown topics as errors instead of warnings.")
    ap.add_argument("--quiet", action="store_true",
                    help="Only print warnings/errors, not the success summary.")
    args = ap.parse_args(argv)

    if not args.validate:
        ap.error("currently --validate is the only supported action")

    try:
        idx = load_index(strict=args.strict)
    except DoctrineSchemaError as e:
        print(f"ERROR: doctrine corpus failed validation:\n{e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Loaded {len(idx.by_id)} passage(s) from {passages_dir()}")
        print(f"  topics indexed:    {len(idx.by_topic)}")
        print(f"  keywords indexed:  {len(idx.by_keyword)}")
        print(f"  applies-to stages: {sorted(idx.by_applies_to.keys())}")
    if idx.warnings:
        print(f"\n{len(idx.warnings)} warning(s):", file=sys.stderr)
        for w in idx.warnings:
            print(f"  - {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
