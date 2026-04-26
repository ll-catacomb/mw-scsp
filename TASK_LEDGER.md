# Task Ledger

Read this before editing shared files. Update by hand at tier boundaries.

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
- **Use `HEAVY_CLAUDE_MODEL=claude-sonnet-4-6`, NOT the spec default `claude-opus-4-7`**, until extended-thinking config is wired up. Opus 4.7 reasoning-mode generates K=10 structured proposals so slowly the request hangs past tenacity's 12-min retry window. Sonnet finishes the same call in <60s. The spec's stated preference for Opus on hard stages is a future Tier 3 question — see open question below.
- **Use `OFF_DIST_K=3`, NOT default 10**, for the demo runs that landed. K=10 with the existing prompt repeatedly stalled (could not isolate whether token volume or schema shape; K=3 lands cleanly in <5min). The brief flagged K=10 might not surface enough outliers anyway, so 3 is a sane demo default until the prompt + schema get tuned. Knob is env-driven.
- **`judge_pool.py` `max_tokens=4096`, NOT 512.** GPT-5 reasoning tokens consumed all 512 of the original budget on the first run, returning 0 content and a `LengthFinishReasonError`. Same issue as Opus — reasoning models need headroom or they emit empty completions. Fixed. Note this also affects future judges if the model changes.

## Tier 2 runs that landed (squash-merge fingerprint)

End-to-end on the live system, all artifacts present, all 27 tests green:

| run_id | scenario | survivors / K | cost | notes |
|---|---|---|---|---|
| `f0e61815-…` | taiwan_strait_spring_2028 | 3/3 | $0.95 | Tier-2 first complete end-to-end |
| `f137c64d-…` | israel_me_cascade_2026 | 2/3 | $1.025 | RA-4 scenario — works as authored |
| `499d1ed1-…` | taiwan_strait_spring_2028 | 3/3 | $0.935 | 2nd Taiwan; Cartographer recall returned 0 cross-run because filter was `memory_types=["reflection"]` and reflection isn't built yet |
| `7ce1d69b-…` | taiwan_strait_spring_2028 | 3/3 | $0.986 | 4th run, after loosening Cartographer recall to `memory_types=None` — `cross_run_observations` now populates with 5 substantive cross-run patterns. **This is the demo moment per PROJECT_SPEC §13.2.** |

Per-run stage counts match the spec exactly: `modal_ensemble=8`, `3_convergence=1`, `off_distribution=1`, `5_judging=30` (3 proposals × 5 judges × 2 questions). Plus per-run `memory_creation` rows from importance scoring (one per agent observation) and `doctrine-router` only when modal-grounding pass-1 returns <2 hits.

The 4th-run cross-run-observations content (verbatim, abridged) shows the Cartographer surfacing a **provider-family distributional split** as a stable cross-run pattern: Claude instances converge on Dongsha-seizure-with-conditional-withdrawal, GPT instances converge on CCG-law-enforcement-quarantine. Plus four more patterns: kinetic-first openings systematically avoided; cyber/space subordinated to maritime framing; specific recurring absences (decapitation, Kinmen/Matsu primary, economic warfare, nuclear signaling); conditional-withdrawal-tied-to-dialogue is anchored in specific training-data literature (an *interpretive* claim, worth flagging in demo register).

Total Tier-2 spend: ~$3.90 across 4 runs + ~$0.62 across early failed runs = ~$4.5.

## Tier 2 follow-ups (post-merge)

### From `feature/pipeline` Tier 2

- **Reflection module not yet shipped.** `feature/memory` owns this. Until then, `convergence_cartographer.narrate_convergence` retrieves `memory_types=None` (both observations and reflections) so cross-run patterns surface from raw observations. When reflection lands, consider tightening the filter back to `["reflection"]` only, OR keep it permissive and let Park et al. importance weighting do the prioritization.
- **K=3 vs K=10.** Demo runs use K=3. K=10 hung repeatedly on the off_distribution call; couldn't isolate whether the SDK's parse() implementation gets stuck on large nested-list structured outputs, whether tenacity's retry hides a real schema-validation failure, or whether the timeout itself needs to grow past 120s. Worth investigating once feature/memory and feature/doctrine are merged so the off_distribution prompt itself can be iterated. Knob: `OFF_DIST_K`.
- **HEAVY_CLAUDE_MODEL=claude-sonnet-4-6 in practice, not opus-4-7.** Opus-4-7 reasoning-mode hangs on K-multi structured output. To restore the spec's preference for Opus on hard stages, the wrapper would need to pass an `extended_thinking` budget config (Anthropic SDK supports it) so Opus can complete its internal reasoning within the timeout. Out of scope for Tier 2; flagged for Tier 3 demo-prep.
- **Bridge agents in `src/agents/`.** `OffDistributionGenerator` and `JudgePool` were authored in this worktree because `feature/memory`'s versions were stubs. Interfaces match the memory worktree's brief; on merge, take feature/memory's version. Pipeline-side imports remain unchanged.
- **Wrapper edits authorized by Tier 2** (parallel to Tier 1's OpenAI patch): Anthropic Opus-4-7 added to a no-temperature allowlist; APIConnectionError added to retryable types. See "Cross-worktree footprint" at top of file. Both edits are in service of long-pipeline reliability and are safe to keep on merge.
- **convergence_cartographer.py edits authorized by Tier 2**: `_Cluster.member_move_ids: list[Any] → list[str]` (Anthropic strict JSON schema rejects `Any`); narration `max_tokens` 2048→4096; recall filter loosened (see first bullet). Owned nominally by feature/memory; merge-time conflict resolution should keep these fixes regardless of which side wins on the surrounding code.
- **judge_pool max_tokens 512→4096.** GPT-5 reasoning consumed all of 512 on the first run, returning empty content. Worth verifying the same headroom is used if a different judge model is configured — particularly on the cheap-Haiku side.

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
