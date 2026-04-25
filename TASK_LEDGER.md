# Task Ledger

Read this before editing shared files. Update by hand at tier boundaries.

## Current Tier: 0 (about to ship to main)

## Worktree assignments

- `main`              → integration, not actively developing during Tier 1+
- `feature/memory`    → MemoryStore + GenerativeAgent base + Cartographer (skeleton)
- `feature/doctrine`  → index.py (markdown corpus loader) + retrieve.py (two-pass) + author 20-30 passages from RA-1/RA-2
- `feature/pipeline`  → modal_ensemble.py + cross-family async fan-out + convergence clustering
- `feature/ui`        → idle in Tier 1; scaffold Streamlit shell with mocked data if time permits

## File ownership (touch with care)

| File | Owner | Notes |
|---|---|---|
| `src/llm/wrapper.py` | `main` | Owned by `main` after Tier 0. Treat as read-only in feature worktrees. Coordinate any change via this ledger. |
| `src/llm/manifest.py` | `main` | Same as above. |
| `src/memory/schema.sql` | `feature/memory` | Pipeline requests new columns/tables here. |
| `src/memory/store.py` | `feature/memory` | Tier 0 ships init/connect; Tier 1 adds CRUD. |
| `src/memory/retrieval.py` | `feature/memory` | |
| `pyproject.toml` | shared (additive only) | If two worktrees add deps, easy merge. |
| `src/prompts/*.md` | shared (additive only) | Coordinate edits to existing files via this ledger. |
| `_context/agent-output/*.md` | research agents (separate process) | Read-only for the four feature worktrees. |

## Independent (no coordination needed)

- `src/agents/*.py`
- `src/doctrine/*.py`
- `src/ui/*.py`
- `src/pipeline/{modal_ensemble,convergence,adversarial,judging}.py`
- individual prompt files
- scenario YAMLs

## Tier 1 deliverables

### `feature/memory`
- `MemoryStore` class with: `add_observation`, `add_reflection`, `retrieve(agent_id, query_embedding, k)`, `bump_last_accessed`, `summary_paragraph(agent_id, query)`.
- `GenerativeAgent` base class.
- `ConvergenceCartographer` skeleton (observation + retrieval; NO reflection yet — Tier 2).
- Unit tests: `tests/test_memory_retrieval.py` covering recency decay + min-max normalization + weighted score.

### `feature/doctrine`
**Architecture changed Tier 0 → markdown corpus, no Chroma.** See PROJECT_SPEC.md §5 and `data/doctrine/passages/SCHEMA.md`.

- `src/doctrine/index.py::load_index() -> DoctrineIndex` — walks `data/doctrine/passages/`, parses YAML frontmatter, validates against pydantic model, builds `by_id` / `by_topic` / `by_keyword` / `by_applies_to` dicts. CLI flag `--validate` exits non-zero on any schema error.
- `src/doctrine/retrieve.py::retrieve(query, stage, top_k=6) -> list[Passage]` — two-pass: keyword/topic intersection scored by (kw hits + 0.5·topic hits + priority weight), then LLM-router fallback if pass 1 returns < 2 hits.
- Author 20–30 passages: cover RA-2's high-priority JP 3-0/5-0 hooks (cog, decisive-points, phasing, branches-sequels, coa-screening, wargaming-action-reaction, never-assume-away, systems-perspective) and RA-1's PLA highlights. Three exemplars are already shipped in `data/doctrine/passages/{jp3-0,jp5-0}/`.
- Smoke test: query "adversary course of action development" with `stage=modal-grounding` should return at least one JP 5-0 COA passage; query "fait accompli" with `stage=off-distribution-flag` should hit `jp5-0-never-assume-away` via the LLM router fallback.

### `feature/pipeline`
- `src/pipeline/modal_ensemble.py::generate_modal_moves(scenario, run_id) -> list[dict]` with cross-family async fan-out (4 Claude + 4 GPT) via `logged_completion`.
- `src/pipeline/convergence.py` — KMeans clustering on move embeddings, `convergence_summary.md` is called by the Cartographer in Tier 2 but the clustering helper ships in Tier 1.
- End-to-end dry-run script: scenario YAML → 8 modal moves → cluster assignments. Print to stdout.

### `feature/ui`
- (Optional in Tier 1.) `streamlit_app.py` with mocked-data tabs: Scenario / Modal Ensemble / Convergence / Menu / Audit.

## Blockers

- (none currently)

## RA outputs incorporated (post-Tier-0 reconciliation)

- **RA-6** — adopted: dropped LiteLLM, wrapper now uses `AsyncAnthropic` + `AsyncOpenAI` directly with per-provider semaphores (Anthropic=8, OpenAI=16), vendored `PRICE_TABLE` for cost computation, RUN_COST_CAP_USD lowered to $1.10. Model defaults updated to `claude-sonnet-4-6` / `claude-opus-4-7` / `claude-haiku-4-5-20251001` / `gpt-5.5` / `gpt-5`.
- **RA-5** — adopted: README rephrased as hypothesis-generator register; "external validity" bullet added; "documented, reproducible, auditable" inserted into the audit-trail bullet. **Do not name-check Wong in the demo.**
- **RA-4** — adopted: `scenarios/israel_me_cascade_2026.yaml` populated with the trigger, capability blocks, historical analogies, and source anchors. Status flipped from WIP to ready.
- **RA-2** + **RA-1** — partially adopted: 9 sample passages on disk under `data/doctrine/passages/`. Tier 1 `feature/doctrine` authors ~20 more.
- **RA-7** — historical; produced under the original Chroma plan, now superseded by the markdown-corpus pivot. Only useful finding salvaged: BGE query prefix `"Represent this sentence for searching relevant passages: "` (used in memory layer, see `worktree-prompts/memory.md`).
- **RA-8** — confirms "build custom, no framework"; reuse Park et al. retrieval formula (already in spec). DSPy reserved for Tier 3 prompt optimization (out of scope for Tier 0/1).
- **RA-3** — sample passages-from list; informs Tier 1 corpus authoring on the off-distribution side.

## Open questions

- The off-distribution generator does NOT do doctrine retrieval (PROJECT_SPEC.md §5). Pipeline wiring must enforce this — no doctrine block in its prompt template.
- Move clustering: KMeans needs embeddings, but doctrine no longer ships sentence-transformers for that purpose. Two options in `worktree-prompts/pipeline.md`; pipeline worktree picks one in Tier 1.
- `data/doctrine/passages/SCHEMA.md` allows topic vocabulary growth; new tags trigger warnings only (use `--strict` to make them errors). Decide in Tier 1 whether to lock the topic vocabulary at the end of corpus authoring.
- Snapshot pinning: only `claude-haiku-4-5-20251001` exposes a snapshot string; Opus 4.7, Sonnet 4.6, GPT-5.5 are floating aliases. Run-manifest records the alias; reproducibility across alias rolls is not guaranteed by us.
