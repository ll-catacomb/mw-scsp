"""Tier 0 sanity tests for the wrapper. Pure-function pieces only — no actual LLM calls."""

from __future__ import annotations

from pathlib import Path

from src.llm.wrapper import (
    _git_blob_hash,
    _prompt_hash,
    _provider_for,
)


def test_prompt_hash_is_deterministic():
    a = _prompt_hash("system A", "user A")
    b = _prompt_hash("system A", "user A")
    assert a == b
    assert len(a) == 64


def test_prompt_hash_distinguishes_system_user():
    # Same concatenation, different split: must produce different hashes thanks to the \0.
    a = _prompt_hash("foo", "barbaz")
    b = _prompt_hash("foobar", "baz")
    assert a != b


def test_git_blob_hash_matches_known_value():
    # `git hash-object` of "hello\n" is well-known.
    assert _git_blob_hash(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_provider_routing():
    assert _provider_for("claude-sonnet-4-6") == "anthropic"
    assert _provider_for("claude-opus-4-7") == "anthropic"
    assert _provider_for("claude-haiku-4-5-20251001") == "anthropic"
    assert _provider_for("gpt-5.5") == "openai"
    assert _provider_for("gpt-5") == "openai"
    assert _provider_for("o1-mini") == "openai"
    assert _provider_for("anthropic/claude-haiku-4-5") == "anthropic"
    assert _provider_for("openai/gpt-5.5") == "openai"
    assert _provider_for("mistral-medium") == "unknown"


def test_price_table_priced_models():
    """Vendored prices exist for every model id we name in .env.example."""
    from src.llm.wrapper import PRICE_TABLE
    for model in [
        "claude-opus-4-7", "claude-sonnet-4-6",
        "claude-haiku-4-5", "claude-haiku-4-5-20251001",
        "gpt-5.5", "gpt-5",
    ]:
        assert model in PRICE_TABLE, f"price not vendored for {model}"
        rin, rout = PRICE_TABLE[model]
        assert rin > 0 and rout > 0, f"non-positive rates for {model}"


def test_repo_scaffold_is_intact():
    # Cheap structural test — fail fast if someone deletes the spec or schema.
    root = Path(__file__).resolve().parents[1]
    for required in [
        "PROJECT_SPEC.md",
        "TASK_LEDGER.md",
        "RESEARCH_PROMPTS.md",
        "src/memory/schema.sql",
        "src/llm/wrapper.py",
        "src/llm/manifest.py",
        "src/doctrine/index.py",
        "src/doctrine/retrieve.py",
        "data/doctrine/passages/SCHEMA.md",
        "scenarios/taiwan_strait_spring_2028.yaml",
        "scenarios/israel_me_cascade_2026.yaml",
    ]:
        assert (root / required).exists(), f"missing scaffold file: {required}"
