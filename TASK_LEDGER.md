# Task Ledger

Read this before editing shared files. Update by hand at tier boundaries.

## Persona-rooted tree-search (Tier 2.5)

Stage 4 reworked from a single-call OffDistributionGenerator to a persona-rooted bounded tree search inspired by Brenner-Cohen-Addad-Woodruff 2026 §2.2 (negative-prompting tree expansion) and Park et al. 2023 §A.1 (identity-seed agents). Six ethnographic Red-planner personas under `data/personas/`; `select_for_scenario()` picks a structurally-diverse subset by tag-match + greedy diversity; each persona is a `RedPlanner(GenerativeAgent)` with its own memory stream and identity-seed-prepended system prompt. Tree depth + branching configurable via `PERSONA_K` (default 6), `PERSONA_INIT_K` (2), `PERSONA_EXPAND_K` (2), `PERSONA_TREE_DEPTH` (2). Default config = ~36 leaves per run; the user's "true outliers" knob.

Critical architectural commitments preserved: no doctrine retrieval in the off-distribution path (AST tests guard `adversarial.py` and `red_planner.py`); persona ≠ named individual (anonymized handles only); ethnographic detail must be specific (concrete behaviors and visible signals, not psychological labels). Schema in `data/personas/SCHEMA.md`; CLI validator at `python -m src.personas.index --validate` (strict by default).

Backward-compatible: `OFF_DIST_K` env var still honored — when `PERSONA_K=0` is set explicitly OR the persona corpus has no entries for the scenario, `adversarial.py` falls back to the legacy single-call `OffDistributionGenerator` so existing runs/tests don't break.

12 new tests in `tests/test_personas.py` cover corpus loading, selector diversity, tree-search expansion (mocked LLM), AST architectural rules, and config arithmetic. All 50 tests green.

Cost note: at default config the persona tree adds ~$0.40-0.60/run (12 persona generations + 24 sibling expansions, all on Opus 4.7). Bump `RUN_COST_CAP_USD` to 3.00 for the full pipeline. Each axis-of-divergence in `EXPANSION_AXES` is one round; if running depth=3 cycles through (actor → timing → domain) by index.

## Tier 2 in progress on `feature/pipeline`

End-to-end pipeline shipped: Stage 3 (Cartographer narration) → Stage 4 (off-distribution proposals, K configurable via `OFF_DIST_K`) → Stage 5 (5-judge pool with two questions per move). Survival filter: `median_plausibility >= 3 AND would_have_gen_count < ceil(N_judges/2)`. Orchestrator writes the full artifact set: `manifest.json`, `modal_moves.json`, `convergence.md`, `clusters.json`, `candidates.json`, `judgments.json`, `menu.md`, `menu.json`. New tests at `tests/test_pipeline_dry_run.py` (cartographer shape with stub completion + stub embedder; survival math; AST check that `adversarial.py` imports nothing from `src.doctrine`). All 27 tests green.

**Cross-worktree footprint** (read this when squash-merging Tier 2):

- `feature/memory`'s `OffDistributionGenerator` and `JudgePool` were stubs at the start of Tier 2; pipeline's end-to-end depends on them. Bridge implementations were authored in `feature/pipeline` so the run could land. Interfaces match `worktree-prompts/memory.md` exactly (`propose(convergence_summary, scenario, run_id, k)` and `pool.judge(proposal, scenario, run_id, proposal_index)`). When `feature/memory`'s Tier 2 lands, take their version on conflict — they own these files. Pipeline-side callers need no changes.
- Authorized `wrapper.py` patches (parallel to the Tier 1 OpenAI `max_completion_tokens` patch):
  1. `_ANTHROPIC_NO_TEMPERATURE = {"claude-opus-4-7"}` — Opus 4.7 rejects `temperature` ("400: temperature is deprecated for this model"), same shape as GPT-5/o-series. Wrapper now skips the param for models in the set. Add new reasoning-mode models to the set as they ship.
  2. Added `APIConnectionError` (both providers) to the retryable types. Long pipelines see transient connection drops; the existing retry list only had RateLimit + Timeout + APIStatusError, leaving connection drops to bubble up uncaught after a single attempt.
- `convergence_cartographer.py`: `_Cluster.member_move_ids: list[Any]` → `list[str]` (Anthropic strict JSON schema rejects `Any`); narration `max_tokens` 2048 → 4096 (real outputs hit the cap mid-JSON). Both are bug fixes exposed by the first real Cartographer call.

**Tier 2 environment notes:**
- Bumping `RUN_COST_CAP_USD` to ~2.50 for the run is necessary; default 1.10 is below the spec's expected ~$1.00–1.50 plus headroom.
- `default_embedder()` lives in `orchestrator.py`; lazy-loads `BAAI/bge-base-en-v1.5` and applies the BGE asymmetric query prefix only for `is_query=True`. Override the model id via `MEMORY_EMBEDDING_MODEL`.

## Current Tier: 2 (Tier 1 squash-merged: memory 504e3b3, doctrine fdcefe6, pipeline 66c72d7, ui 73eb290)

Tier 1 shipped a working end-to-end pipeline through Stage 3 clustering. Live smoke test on Taiwan scenario completed in 50s for $0.436 (8 modal moves, 1 doctrine-router fallback; full audit trail in `data/runs/f2b0eb4c-6306-4876-b4db-46466b7c186e/`). The modal ensemble exhibited clean convergence (4/4 Claude on Dongsha-seizure variants; 4/4 GPT on quarantine + Pratas-seizure) — exactly the failure mode Tier 2 is built to expose.

## Worktree assignments (Tier 2)

- `main`              → integration; runs the full pipeline at end of tier
- `feature/memory`    → OffDistributionGenerator + JudgePool + reflection module + agent_summary regenerator
- `feature/doctrine`  → prompt iteration (modal_red, convergence_summary, off_distribution, judges) against real Tier-1 retrievals; topic-vocab lock decision
- `feature/pipeline`  → adversarial.py + judging.py + Stage-3 narration wire-up + full pipeline run
- `feature/ui`        → swap mocks for real reads from `data/runs/{run_id}/`; live "re-run one stage" button

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

## Tier 2 deliverables

### `feature/memory`
- `OffDistributionGenerator` agent in `src/agents/off_distribution_generator.py` — persistent memory of past proposals + outcomes (plausibility, would-have-generated, surviving). `propose(convergence_summary, scenario, run_id, k)` calls `off_distribution.md` with retrieved past-proposal memories injected; persists each proposal as an observation.
- `JudgePool` in `src/agents/judge_pool.py` — 5 logical judge instances (3/2 family split per move with rotation); each judge has its own per-instance calibration history (rate-of-plausible, rate-of-would-have-generated). Two calls per proposal: `judge_plausibility.md` and `judge_off_dist_check.md` (fresh contexts so the two signals are independent).
- Reflection module in `src/agents/base.py::GenerativeAgent.reflect()` — Park et al. §4.2 two-step (questions → insights with citations). Triggered after pipeline run when `unreflected_importance_sum >= 50` (start threshold; tune from there).
- `agent_summary` regenerator: re-run the three queries in `agent_summary.md` and write a new versioned row when memory changed materially (every 3 runs OR after a new reflection lands).
- Unit tests for the new agents (mock `logged_completion` to stay offline) and the reflection trigger.

### `feature/doctrine`
- Iterate `src/prompts/modal_red.md` against actual Tier-1 retrievals. The smoke run showed all 8 moves citing `jp3-0-phasing-model` + `jp3-0-cog` + `pla-gray-zone-coercion` — possibly retrieval bias, possibly the prompt over-anchoring. Investigate and tune.
- Iterate `src/prompts/convergence_summary.md` against the Cartographer's first real outputs (will land mid-tier when pipeline wires up Stage 3).
- Iterate `src/prompts/off_distribution.md` against the new generator's behavior — particularly the "which_convergence_pattern_it_breaks" field, which is the cleanest signal of whether escape worked.
- Iterate the two judge prompts based on rate-of-plausible drift across instances.
- Decide whether to lock topic vocab (`--strict` becomes default in `index.py`).
- Author the CSIS subdirectory if any RA-3 off-distribution corpus material is missing.

### `feature/pipeline`
- `src/pipeline/adversarial.py::generate_off_distribution(convergence_summary, scenario, run_id, k) -> list[dict]` — Stage 4. Calls `OffDistributionGenerator.propose()`. **No doctrine retrieval** — enforce by not passing a doctrine block.
- `src/pipeline/judging.py::judge_proposals(proposals, scenario, run_id) -> list[dict]` — Stage 5. Per proposal: 5 judges (3/2 family split, rotated per move), 2 questions per judge, asyncio.gather. Survival filter: `median_plausibility >= 3 AND would_have_gen_count < ceil(N_judges / 2)`.
- Wire the Cartographer's `narrate_convergence()` (already shipped) into `src/pipeline/convergence.py` so Stage 3 produces real cluster_assignments + notable_absences.
- Update `orchestrator.py::run_pipeline()` to run Stages 3 → 4 → 5, persist to `off_dist_proposals` and `judgments` tables, write `data/runs/{run_id}/{convergence,candidates,judgments,menu}.{md,json}`.
- **K (off-distribution candidates) is configurable** via `OFF_DIST_K` env var, default 10. Madeleine flagged Tier 1 outputs may not surface enough true outliers at K=10; a future scaling pass can crank this without code changes.
- End-to-end run on both scenarios. Costs ~$0.40/run; budget for 5–10 iterative runs during Tier 2.

### `feature/ui`
- Swap the Tier-1 mock fixtures for real reads from `data/runs/{run_id}/{manifest,modal_moves,convergence,candidates,judgments,menu}.json` and `data/memory.db`.
- **Mock shape fixes (Tier 1 carry-over):** `MOCK_MODAL_MOVES` is missing `actions` and `move_id`; `MOCK_CONVERGENCE` uses `cluster_labels` instead of the spec's `clusters` list. Fix as part of the mock-to-real swap.
- Wire the "Live re-run one stage" button (currently stubbed) — re-runs Stage 4 only, against the existing run's Stage 3 output. Cheapest credibility move in the demo.
- Run picker (`_list_run_ids()` already exists) becomes the entry point; the demo loads a pre-computed canonical run.
- Decide which of `streamlit_app.py` vs `streamlit_proto.py` is the demo. Keep the other for reference.

## Blockers

- (none currently)

## Mid-Tier-2 main-worktree edits (heads-up for `feature/pipeline`)

`main` landed two integration fixes that touch files `feature/pipeline` is also editing in
Tier 2. Rebase / forward-merge before submitting. Both are small and additive — conflicts
should resolve straightforwardly.

- **`src/pipeline/modal_ensemble.py::_build_doctrine_query`** — new helper. Doctrine-flagged
  bug: pass-1 of `retrieve(red_team_question, ...)` returned 0 hits on Taiwan, forcing the
  LLM-router to feed all 8 modal calls from a single pick. Fixed by concatenating
  red_team_question + title + situation + red_strategic_goals + red_force into the query.
  Verified: Taiwan 0 → 6 pass-1 hits, Israel 3 → 6 pass-1 hits.
- **`src/pipeline/convergence.py`** — added `cartographer_narrate(modal_moves, scenario,
  run_id, *, embedder=None, store=None)` plus `make_default_embedder()` (sentence-transformers
  BGE wrapper with the asymmetric query prefix per RA-7, module-level singleton). The Tier-1
  no-op `cluster_moves()` is preserved for tests that don't want sentence-transformers.
- **`src/pipeline/orchestrator.py::run_pipeline`** — calls `cartographer_narrate` after the
  modal stage, writes `data/runs/{run_id}/convergence.json` (full ConvergenceNarration shape
  for the UI loader) and `convergence.md` (readable). The Cartographer call is wrapped in
  try/except so a Stage-3 failure doesn't kill the run; on error, convergence.json carries
  `{"_error": ..., "_stage": "3_convergence"}` and the rest of the pipeline continues.

What `feature/pipeline` still owns in Tier 2: `adversarial.py` (Stage 4), `judging.py`
(Stage 5), and the orchestrator wire-up to chain Stages 3 → 4 → 5 with persistence to
`off_dist_proposals` / `judgments` and `candidates.json` / `judgments.json` / `menu.md`
artifacts. The Stage-3 narration call site is now in place; pipeline can build on top.

## Tier 1 wrapper fix (pre-merge note for `main`)

`feature/pipeline` patched `src/llm/wrapper.py::_call_openai` to use
`max_completion_tokens=max_tokens` instead of `max_tokens=max_tokens`. GPT-5.5 and
GPT-5 (and the o-series) reject `max_tokens` with HTTP 400
`Unsupported parameter: 'max_tokens' is not supported with this model. Use
'max_completion_tokens' instead.`. The function signature still exposes `max_tokens`
to callers — only the OpenAI SDK call site changed. Authorized by Madeleine.

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

- ~~Should the topic vocabulary be locked at end of Tier 2 (`--strict` becomes default)?~~ **Resolved (Tier 2 `feature/doctrine`):** locked. CLI default is now strict; opt out via `--no-strict`. See Tier-2 follow-ups below for details.

## Tier 1 follow-ups (post-merge)

### From `feature/memory` Tier 1
- **Embedding callable signature.** `GenerativeAgent.__init__` accepts a callable with kwarg `is_query: bool` so the agent can route the BGE asymmetric prefix without owning the encoder. Pipeline worktree should construct the agent by passing in a thin closure over `sentence_transformers.SentenceTransformer.encode`. Tests stub the callable. Worth confirming this signature in Tier 2 when the OffDistributionGenerator is wired in.
- **`unreflected_importance_sum` semantics.** Implemented as: sum of importance for `observation` rows whose `created_at` is strictly greater than the most recent `reflection`'s `created_at` (or all observation importance if no reflection exists). This matches Park et al. §4.3 ("reset on reflection") but the spec didn't pin the wording — flag if Tier 2 wants different bookkeeping.
- **Default `decay_per_day = 0.99`.** PROJECT_SPEC.md §4.2 mentions Park et al.'s `0.995/sandbox-hour`; we picked 0.99/day as a reasonable hackathon default. Tunable per call via the `decay_per_day` kwarg on `score_memories`. Revisit during Tier 3 demo prep against actual run cadence.
- **Min-max degenerate case.** When all candidates have equal recency / importance / relevance, the normalized component is zeros (not NaN, not ones). This means a degenerate component contributes nothing to the weighted sum rather than artificially inflating it. Park et al. don't specify; choosing zeros felt safest.
- **`narrate_convergence` query construction.** Query string = `f"Convergence patterns relevant to {scenario.title}. {scenario.summary}"`. Could also use the cluster themes; left simple for Tier 1. Revisit if reflections fail to surface in the demo.
- **No reflection / OffDistributionGenerator / JudgePool yet.** Per the Tier 1 brief — those land in Tier 2.
- **Retrieved memories still bump `last_accessed_at` even when `now=` is passed.** This is intentional (retrieval is what counts as access in Park et al.). Mention to anyone writing a "what would this score" preview tool that they should pass a fresh MemoryStore or accept the side effect.

### From `feature/memory` Tier 2

- **`summary_paragraph` is now async.** Was sync in Tier 1 (cache read only); the brief asks
  for a fresh-generation fallback when the cache is empty, which requires LLM calls.
  No external callers existed at the time of the change. Pipeline worktree should `await`.
- **`reflect()` returns the new reflection memory_ids.** Brief said "implement" without pinning
  a return shape; returning the ids lets the caller decide whether to regenerate the agent
  summary immediately. `reflect_if_due()` (threshold-gated) is the convenience wrapper the
  pipeline should call at end-of-run.
- **Reflection citations may point to earlier reflections in the same `reflect()` invocation.**
  Park et al. Fig. 7 explicitly allows this; we don't filter it out. The test
  `test_reflect_persists_reflections_with_citations` asserts citations resolve to *some*
  memory the agent owns, not strictly observations.
- **Agent-summary cold start.** `summary_paragraph(query)` on an empty cache generates a
  single paragraph for the supplied query rather than running the full three-query
  Appendix-A regeneration. The pipeline calls `regenerate_summary()` explicitly when it
  wants the canonical three-query version. Compromise to keep the cold-start cheap.
- **`regenerate_summary_if_stale(run_count)` triggers.** True iff `run_count > 0 and
  run_count % 3 == 0` OR there is a reflection memory created after the most recent
  cached summary (or no summary exists yet alongside reflections). The "after a new
  reflection lands" rule is implemented by a SQL comparison against `agent_summary` —
  no caller bookkeeping required.
- **`_JudgeInstance` per judge_id.** Each judge in `JudgePool.judges` is its own
  `GenerativeAgent` with `agent_id == judge_id` (e.g. `"judge_0"`). Per-instance
  calibration history is therefore stored under `judge_0` … `judge_4` in `agent_memory`,
  not under a single `"judge_pool"` row. This matches PROJECT_SPEC.md §4.5's "logical
  with 5 instances each tagged" framing.
- **Family rotation at temp=0.2 is structural.** `JudgePool.judge(..., proposal_index)`
  changes `asyncio.gather` argument order on odd indices but the output is re-sorted by
  judge_id so downstream code sees a stable shape. Worth flagging if the pipeline starts
  caring about call ordering for some non-behavioral reason (e.g. retry budget).

### From `feature/ui` Tier 2

Tier-2 work shipped: `src/ui/run_loader.py` (list_runs / load_run); `src/ui/streamlit_app.py` rewired to read from `data/runs/` + `data/memory.db`; `src/ui/fixtures.py` reshaped to mirror real schemas; `src/ui/streamlit_proto.py` flagged as the alternative design.

Real-vs-mock shape findings (worth knowing if pipeline worktree iterates on artifact writers):

- **`manifest.json` carries no `totals` / `completed_at` / `status` / `artifacts` fields.** Those come from the `runs` table (status, completed_at) and from summing `llm_calls` (totals: llm_calls / input_tokens / output_tokens / cost_usd). `run_loader.load_run()` synthesizes them onto the manifest so the UI's audit panel doesn't have to know the difference. If the orchestrator ever writes `totals` directly, the loader keeps the orchestrator's value; remove the `setdefault` if you want to force loader-computed totals.
- **`clusters.json` (Tier-1 shape) is `{cluster_assignments, cluster_themes}` — the raw clustering, not the Cartographer's narration.** The richer ConvergenceNarration (`convergence_summary`, `clusters[{cluster_id, theme, member_move_ids, representative_actions}]`, `notable_absences[{absence, why_it_might_be_proposed, why_the_ensemble_missed_it}]`, `cross_run_observations[]`) is what the UI's Section 3 actually wants. The loader looks for `convergence.json` first (preferred Tier-2 artifact name) and falls back to building a minimal narration from the raw clustering. **Suggestion for `feature/pipeline`:** wire `narrate_convergence()` into the orchestrator and dump the parsed dict to `data/runs/{run_id}/convergence.json`. Optional `convergence.md` for prose rendering is also read.
- **`notable_absences` is a list of objects, not strings.** UI handles both; pipeline writers should produce the object shape. `cross_run_observations` is also a list, not a single string — the UI iterates.
- **`candidates.json` + `judgments.json` are joined inside the loader** (`run_loader._menu_from_artifacts`) into the per-proposal `menu` shape the UI consumes. Expected candidate-row keys: `proposal_id`, `move_title`, `summary`, `which_convergence_pattern_it_breaks`, optional `actions/intended_effect/risks_red_accepts`. Expected judgment-row keys mirror the SQLite `judgments` table: `proposal_id`, `judge_id`, `plausibility`, `would_have_generated`, `rationale`. Survival is recomputed from ratings if not pre-set on the candidate.
- **Live re-run button** imports `src.pipeline.adversarial.generate_off_distribution` lazily and shows a clean error message if Stage 4 isn't on the branch yet — so the UI ships before the pipeline worktree's adversarial.py lands.
- **`streamlit_proto.py` kept** for reference; not the demo. Header comment names it as the alternative. Both `streamlit_app.py` and `streamlit_proto.py` import the same `fixtures.py`, so the proto's render functions were lightly patched to consume the new ConvergenceNarration shape (cluster_labels lookup built from `clusters[]`, notable_absences treated as objects, cross_run_observations as a list).
- **Data symlinks for cross-worktree testing.** `data/runs` and `data/memory.db` are gitignored; the feature/ui worktree symlinks both into the main worktree's `data/` so the UI can be smoke-tested against the actual Tier-1 run without copying. Symlinks are local-only and not committed.

### From `feature/doctrine` Tier 1

Authored 24 new passages on top of the 9 Tier-0 exemplars (33 total: 6 jp3-0 + 5 jp5-0 + 8 pla + 5 me + 4 jp3-0 existing + 4 jp5-0 existing + 1 pla existing). Validation clean (no warnings). All four smoke tests in `tests/test_doctrine_index.py` pass.

Retrieval-quality findings worth knowing when iterating `modal_red.md` and `convergence_summary.md`:

- **Cross-scenario topic bleed via the substring topic-matcher.** `_candidate_topics` in `retrieve.py` matches a query token against any topic that contains it as a hyphen-segment. Because PLA uses `joint-firepower-strike` and ME uses `april-2024-strike` / `october-2024-strike` / `iran-strike-package`, queries containing the bare token `strike` retrieve passages from *both* scenario corpora. Example: `retrieve_sync("decapitation strike", "modal-grounding", 4)` returns `[pla-decapitation, pla-joint-firepower-strike, me-iran-april-2024-strike, me-iran-october-2024-strike]`. For Taiwan-only modal-grounding prompts, prefer scenario-anchored phrasing ("PLA decapitation", "cross-strait decapitation") or post-filter by id prefix in the pipeline. This is more annoyance than bug — the LLM-router fallback would prune it, but pass-1 alone leaks. Worth flagging in `modal_red.md` if it shows up in clustering.
- **Stem trimming is incomplete.** `transitions` (topic) does not match the query token `transition`; `phasing` (topic + keyword) does not match `phase`. `retrieve_sync("phase transition", "off-distribution-flag", 4)` returns only `jp3-0-phasing-model`, falling below the 2-hit pass-1 floor and triggering pass-2. Likely worth adding light stemming (drop trailing `s`, `ing`, `ion`) in a future iteration; held off in Tier 1 to keep the function signature stable.
- **Pass-1 `< 2 hits` triggers LLM router more often than the spec implies.** Several legitimately specific queries (`"quarantine"` modal-grounding → 2 hits; `"houthi red sea"` → 1 hit; `"phase transition"` off-distribution-flag → 1 hit) sit at or below the pass-2 threshold. Two practical consequences for the pipeline: (a) the modal ensemble's `top_k=6` retrieval will routinely fire the router, so budget for that; (b) test-mode runs that should be deterministic should use `retrieve_sync()` and accept fewer hits.
- **High-priority off-distribution-flag passages.** `jp5-0-most-probable-most-dangerous` is the single most-cited adjudication passage and is set `priority: high` to bias the score; it should appear in the top-3 for any query about "templated adversary," "JIPOE COA," or "the binary." `pla-volt-typhoon-class` and `me-lawfare-instrumental` are the cross-scenario substrate-targeting anchors; both `priority: high`.
- **Deliberate non-coverage.** No passage was authored *for* the off-distribution generator (Stage 4). The Volt-Typhoon, lawfare-instrumental, active-defense, most-probable-most-dangerous, and decisive-points passages are tagged `applies-to: off-distribution-flag` so that the Stage 5 judges and the Cartographer can *recognize* off-distribution moves — not so that the Stage 4 generator can seed from them. Per PROJECT_SPEC.md §5: pipeline wiring must enforce no doctrine block in the off-distribution generator's prompt template. (Re-flagging the existing open question for visibility.)
- **CSIS subdirectory not yet populated.** The `csis/` dir mentioned in SCHEMA.md was not created in Tier 1; CSIS-sourced material is currently filed under `pla/` (e.g., `pla-quarantine-vs-blockade`, which cites CSIS as primary source). If a future pass wants to separate CSIS analytic syntheses from PLA-doctrine-derived passages, splitting will require updated source/edition fields but no schema change.

### From `feature/doctrine` Tier 2

Iterated four prompts and locked the topic vocabulary. Re-ran the modal stage on Taiwan to validate.

- **Root cause of Tier 1 citation flattening: the retrieval query, not the prompt.** The Tier-1 smoke run had `red_team_question` (a generic "Propose Red's opening move..." string) as the *only* query passed to `retrieve()`. This query yields **zero pass-1 hits** (no scenario tokens, no doctrine vocab). The LLM-router fallback fires once, picks 6 modal-grounding passages, and **the same 6 passages feed all 8 modal calls**. Citation flattening was therefore structurally guaranteed before the prompt was even invoked. **Action for `feature/pipeline`:** in `src/pipeline/modal_ensemble.py::generate_modal_moves`, construct the doctrine query as `f"{red_team_question}\n\n{scenario['title']}. {scenario.get('situation','')}\n\nRed strategic goals: {'; '.join(scenario.get('red_strategic_goals',[]))}"` (or similar). This will land scenario-specific tokens (Taiwan, PLA, amphibious, gray-zone, etc.) into pass-1 and stop forcing the router fallback. Will measurably diversify retrieval; the prompt iteration below addresses the residual issue.
- **Iterated `src/prompts/modal_red.md`.** Two changes: (a) added "doctrine excerpts are reference background, not a menu of options — decide your move first, then identify which excerpts shaped your reasoning; an empty `doctrine_cited` list is acceptable"; (b) tightened the `risks_red_accepts` rubric to require a specific Blue countermove or named failure condition, with a worked good/bad example.
- **Re-ran modal stage on Taiwan** (run `0bbeea21-b2bc-455d-9881-0ab4c30ed277`, `data/runs/` in the doctrine worktree). Results vs. Tier-1 baseline:
  - **Citation count per move: 4–6 → 2–3.** Models stopped padding; bloated co-citations of `jp3-0-cog` and `jp3-0-decisive-points` disappeared entirely. Only `jp3-0-phasing-model` survives at 6/8 (still some over-anchoring on phasing as default frame).
  - **Citation distribution: 8/8 → `pla-quarantine-vs-blockade` + `pla-gray-zone-coercion`** (the two passages actually relevant to the move all 8 instances chose). This is *correct* convergence given the convergence of the moves themselves — citation distribution now tracks move distribution, not retrieval pack composition.
  - **`risks_red_accepts` quality: massively better.** All 48 risk entries across the 8 moves now name a specific Blue countermove + a specific failure condition (e.g., "If Japan invokes Article V before Day 4..."). Zero "Blue may escalate" entries. The Cartographer will have rich material for "notable absences" framing.
  - **Convergence shifted: was 4 Dongsha + 4 quarantine; now 8 quarantine.** This is *more* convergent than Tier 1, not less. Plausible explanation: the LLM router's pick this time included `pla-quarantine-vs-blockade` (which was probably absent or lower-priority in the Tier-1 router pick), and once both Claude and GPT see it, both default to quarantine because it is *the* canonical sub-kinetic PLA opener for Taiwan. The convergence shift confirms the diagnosis above: at the current retrieval-query design, modal convergence is dominated by what the router happens to pick. Iterating only the prompt cannot break this; only fixing the retrieval query (in `feature/pipeline`) will.
  - This convergence is exactly what Stage 3 is designed to flag — for the demo, this is the failure mode the system surfaces. So it's not a problem to solve in `feature/doctrine`; it's the cleanest possible Stage-3 input.
- **Iterated `src/prompts/convergence_summary.md`.** Tightened the `notable_absences` rubric to require actor + instrument + intended effect for each absence (no categorical observations like "the ensemble underweights non-kinetic options"). Pinned `cross_run_observations` to MUST-be-empty on first run for a scenario family — Tier 1 didn't have the Cartographer wired to memory yet, so this is a pre-emptive guardrail for when `feature/pipeline` lands the Stage-3 wire-up.
- **Iterated `src/prompts/off_distribution.md`.** `which_convergence_pattern_it_breaks` now requires (a) the cluster name verbatim from the Cartographer + (b) the unstated assumption violated, with a "two distinct proposals must not break the same cluster-and-assumption pair" rule to prevent cosmetic variants. `why_a_red_planner_could_justify_this` now requires a named doctrinal/historical anchor, a Red goal it serves, and a political constraint it relaxes; if no anchor can be named, the move is probably pure provocation. `risks_red_accepts` mirrors the modal-stage rubric.
- **Iterated `src/prompts/judge_plausibility.md`.** Added explicit calibration anchors: (a) "if you find yourself rating every proposal a 4 or 5, you are anchoring on 'I can imagine a justification' rather than 'Red would brief this'"; (b) "do not rate a 1 or 2 unless you can name what the move violates." The rationale field now requires the violated constraint (low scores) or the matched calculus feature (high scores).
- **Iterated `src/prompts/judge_off_dist_check.md`.** Added the symmetric anti-monotonic guardrail (don't always-YES, don't always-NO) and a hard-cases protocol: if the actions look familiar but the framing/sequencing is off, anchor on "would this framing appear in my top three if I were briefing my boss." Without this, "would_have_generated" defaults to YES on anything that touches familiar instruments (CCG, PLAN, PLAAF), which would prevent the survival filter from firing.
- **Topic vocabulary lock decision: locked.** `--strict` is now the default in `src/doctrine/index.py::main()`; `--no-strict` exists as opt-out. Tier 1 added 24 passages without introducing new topics; Tier 2 added zero new passages, so the vocabulary is stable. Adding a new topic now requires editing `KNOWN_TOPICS` and SCHEMA.md in the same commit. The library function `load_index(strict=False)` default is unchanged — runtime retrieval should not hard-fail on an unknown topic if one slips into a future passage; only the validation CLI is strict by default. All 4 doctrine tests pass under both strict and non-strict modes (corpus is clean either way).
- **Light stemming decision: deferred, not demo-blocking.** The Tier-1 finding (`phase` ≠ `phasing`, `transition` ≠ `transitions`) is real, but the Tier-2 re-run validated that `pla-quarantine-vs-blockade` retrieves correctly via the LLM-router fallback even without stemming. The actual demo-blocker is the retrieval-query construction in `modal_ensemble.py` (see top item); stemming would not have helped that case (the generic question contains no doctrine vocab regardless of stem trimming). Pick up stemming if a downstream stage shows retrieval misses on specific scenario-anchored queries.
- **CSIS subdirectory: not authored.** No new RA-3 PLA off-distribution material surfaced during Tier 2 prompt iteration. The single CSIS-sourced passage (`pla-quarantine-vs-blockade`) remains under `pla/`. Splittable later without schema impact.
- **No new doctrine passages authored in Tier 2.** Stage-5 judges did not run end-to-end during Tier 2 in this worktree (depends on `feature/pipeline` shipping `judging.py`), so no missing-passage signals from judge feedback yet. Revisit once the full pipeline lands.
