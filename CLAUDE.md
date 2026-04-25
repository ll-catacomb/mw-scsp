# Adversarial-Distribution Red Team — Claude Code instructions

This is a hackathon prototype for SCSP 2026 (Wargaming track, Boston). Build per `PROJECT_SPEC.md`.

## Read first, every session

1. `PROJECT_SPEC.md` — authoritative spec for what we're building and why.
2. `TASK_LEDGER.md` — current tier, worktree assignments, file ownership, blockers. **Read before editing shared files.**
3. The current worktree's `worktree-prompts/<branch>.md` if you're on a feature branch.

## Repository shape

```text
src/             # Python package (pipeline, agents, memory, doctrine, llm, prompts, ui)
scenarios/       # Wargame scenarios (YAML)
data/            # Local-only: doctrine PDFs, Chroma index, memory.db, run artifacts (gitignored)
tests/           # pytest
_context/
  agent-output/  # Research-agent deliverables (raN-*.md). Read these when iterating prompts and YAMLs.
  dev/           # External tooling notes (Anthropic, OpenAI, etc.) — pre-existing background context.
  ll/            # Madeleine's prior writing — substrate, not project material.
worktree-prompts/  # Initial briefs for each parallel Claude Code instance (Tier 1+).
PROJECT_SPEC.md
RESEARCH_PROMPTS.md  # Prompts to paste into 8 parallel research agents.
TASK_LEDGER.md
```

## Tech

- **uv** for dependency + venv management. Never use `pip` directly.
- **litellm** for unified Anthropic + OpenAI calls.
- **Markdown + YAML frontmatter** for the doctrine corpus (see `data/doctrine/passages/SCHEMA.md`). No ChromaDB, no embeddings — bounded corpus, two-pass keyword/topic retrieval with LLM-router fallback.
- **SQLite** for memory store and audit log (schema in `src/memory/schema.sql`).
- **Streamlit** for the demo UI.
- **Python 3.11+**.

## Commands

- `uv sync` — install deps into `.venv`.
- `uv run pytest` — run tests.
- `uv run python -m src.doctrine.index --validate` — load and validate every passage in `data/doctrine/passages/`. Authoring new passages? Run this first.
- `uv run streamlit run src/ui/streamlit_app.py` — launch the demo UI.

## House rules

- Every LLM call goes through `src/llm/wrapper.py::logged_completion()`. No bare `litellm.acompletion` calls in pipeline code.
- Prompts live in `src/prompts/*.md` and are loaded by filename. The wrapper records the git blob hash of the prompt file at call time as `prompt_version`.
- The off-distribution generator must NOT do doctrine retrieval. Its job is to escape the gap, not stay in it.
- Don't name-check Yuna Wong's work in the demo. The register lands without flattery.
- Keep main always-buildable. Squash-merge feature branches at tier boundaries (see §10 of the spec).
