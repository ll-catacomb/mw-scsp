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

- Should the topic vocabulary be locked at end of Tier 2 (`--strict` becomes default)? Tier 1 `feature/doctrine` added 24 passages using only existing `KNOWN_TOPICS` tags; locking the vocabulary now would let `--strict` ride.

## Tier 1 follow-ups (post-merge)

### From `feature/memory` Tier 1
- **Embedding callable signature.** `GenerativeAgent.__init__` accepts a callable with kwarg `is_query: bool` so the agent can route the BGE asymmetric prefix without owning the encoder. Pipeline worktree should construct the agent by passing in a thin closure over `sentence_transformers.SentenceTransformer.encode`. Tests stub the callable. Worth confirming this signature in Tier 2 when the OffDistributionGenerator is wired in.
- **`unreflected_importance_sum` semantics.** Implemented as: sum of importance for `observation` rows whose `created_at` is strictly greater than the most recent `reflection`'s `created_at` (or all observation importance if no reflection exists). This matches Park et al. §4.3 ("reset on reflection") but the spec didn't pin the wording — flag if Tier 2 wants different bookkeeping.
- **Default `decay_per_day = 0.99`.** PROJECT_SPEC.md §4.2 mentions Park et al.'s `0.995/sandbox-hour`; we picked 0.99/day as a reasonable hackathon default. Tunable per call via the `decay_per_day` kwarg on `score_memories`. Revisit during Tier 3 demo prep against actual run cadence.
- **Min-max degenerate case.** When all candidates have equal recency / importance / relevance, the normalized component is zeros (not NaN, not ones). This means a degenerate component contributes nothing to the weighted sum rather than artificially inflating it. Park et al. don't specify; choosing zeros felt safest.
- **`narrate_convergence` query construction.** Query string = `f"Convergence patterns relevant to {scenario.title}. {scenario.summary}"`. Could also use the cluster themes; left simple for Tier 1. Revisit if reflections fail to surface in the demo.
- **No reflection / OffDistributionGenerator / JudgePool yet.** Per the Tier 1 brief — those land in Tier 2.
- **Retrieved memories still bump `last_accessed_at` even when `now=` is passed.** This is intentional (retrieval is what counts as access in Park et al.). Mention to anyone writing a "what would this score" preview tool that they should pass a fresh MemoryStore or accept the side effect.

### From `feature/doctrine` Tier 1

Authored 24 new passages on top of the 9 Tier-0 exemplars (33 total: 6 jp3-0 + 5 jp5-0 + 8 pla + 5 me + 4 jp3-0 existing + 4 jp5-0 existing + 1 pla existing). Validation clean (no warnings). All four smoke tests in `tests/test_doctrine_index.py` pass.

Retrieval-quality findings worth knowing when iterating `modal_red.md` and `convergence_summary.md`:

- **Cross-scenario topic bleed via the substring topic-matcher.** `_candidate_topics` in `retrieve.py` matches a query token against any topic that contains it as a hyphen-segment. Because PLA uses `joint-firepower-strike` and ME uses `april-2024-strike` / `october-2024-strike` / `iran-strike-package`, queries containing the bare token `strike` retrieve passages from *both* scenario corpora. Example: `retrieve_sync("decapitation strike", "modal-grounding", 4)` returns `[pla-decapitation, pla-joint-firepower-strike, me-iran-april-2024-strike, me-iran-october-2024-strike]`. For Taiwan-only modal-grounding prompts, prefer scenario-anchored phrasing ("PLA decapitation", "cross-strait decapitation") or post-filter by id prefix in the pipeline. This is more annoyance than bug — the LLM-router fallback would prune it, but pass-1 alone leaks. Worth flagging in `modal_red.md` if it shows up in clustering.
- **Stem trimming is incomplete.** `transitions` (topic) does not match the query token `transition`; `phasing` (topic + keyword) does not match `phase`. `retrieve_sync("phase transition", "off-distribution-flag", 4)` returns only `jp3-0-phasing-model`, falling below the 2-hit pass-1 floor and triggering pass-2. Likely worth adding light stemming (drop trailing `s`, `ing`, `ion`) in a future iteration; held off in Tier 1 to keep the function signature stable.
- **Pass-1 `< 2 hits` triggers LLM router more often than the spec implies.** Several legitimately specific queries (`"quarantine"` modal-grounding → 2 hits; `"houthi red sea"` → 1 hit; `"phase transition"` off-distribution-flag → 1 hit) sit at or below the pass-2 threshold. Two practical consequences for the pipeline: (a) the modal ensemble's `top_k=6` retrieval will routinely fire the router, so budget for that; (b) test-mode runs that should be deterministic should use `retrieve_sync()` and accept fewer hits.
- **High-priority off-distribution-flag passages.** `jp5-0-most-probable-most-dangerous` is the single most-cited adjudication passage and is set `priority: high` to bias the score; it should appear in the top-3 for any query about "templated adversary," "JIPOE COA," or "the binary." `pla-volt-typhoon-class` and `me-lawfare-instrumental` are the cross-scenario substrate-targeting anchors; both `priority: high`.
- **Deliberate non-coverage.** No passage was authored *for* the off-distribution generator (Stage 4). The Volt-Typhoon, lawfare-instrumental, active-defense, most-probable-most-dangerous, and decisive-points passages are tagged `applies-to: off-distribution-flag` so that the Stage 5 judges and the Cartographer can *recognize* off-distribution moves — not so that the Stage 4 generator can seed from them. Per PROJECT_SPEC.md §5: pipeline wiring must enforce no doctrine block in the off-distribution generator's prompt template. (Re-flagging the existing open question for visibility.)
- **CSIS subdirectory not yet populated.** The `csis/` dir mentioned in SCHEMA.md was not created in Tier 1; CSIS-sourced material is currently filed under `pla/` (e.g., `pla-quarantine-vs-blockade`, which cites CSIS as primary source). If a future pass wants to separate CSIS analytic syntheses from PLA-doctrine-derived passages, splitting will require updated source/edition fields but no schema change.
