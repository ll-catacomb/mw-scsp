# Tier 2 brief — `feature/pipeline` worktree

You are working in the `feature/pipeline` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

Tier 1 shipped: `modal_ensemble.py` (8-call cross-family fan-out), `convergence.py` (no-op cluster placeholder, deferred to Cartographer LLM-grouping), `orchestrator.py` (end-to-end through Stage 3 placeholder). Live smoke test on Taiwan completed in 50s for $0.436. Modal output is on disk at `data/runs/f2b0eb4c-6306-4876-b4db-46466b7c186e/` — read it before iterating.

## Read first

1. `PROJECT_SPEC.md` — sections §3 (full pipeline), §6 (cross-family), §9 (logging), §15 (definition of done).
2. `TASK_LEDGER.md` — file ownership, Tier 1 follow-ups, the doctrine retrieval-quality findings.
3. `src/llm/wrapper.py` — `logged_completion` is the audit spine. Use it. **Do not edit.** (Tier 1 made one authorized OpenAI-param patch; no further edits expected.)
4. `src/agents/off_distribution_generator.py` and `src/agents/judge_pool.py` — being filled in by `feature/memory` in parallel. Coordinate via TASK_LEDGER if their interface changes.
5. `src/agents/convergence_cartographer.py::narrate_convergence()` — already shipped; you call it.
6. `src/prompts/{off_distribution,judge_plausibility,judge_off_dist_check,convergence_summary}.md`.
7. `data/runs/f2b0eb4c-6306-4876-b4db-46466b7c186e/modal_moves.json` — actual Tier-1 output. Use this as a fixture.

## What you own

- `src/pipeline/adversarial.py` — Stage 4 wiring around `OffDistributionGenerator`.
- `src/pipeline/judging.py` — Stage 5 wiring around `JudgePool`.
- `src/pipeline/convergence.py` — replace the no-op with the real Cartographer narration call.
- `src/pipeline/orchestrator.py` — extend `run_pipeline` to chain Stages 3 → 4 → 5.
- `src/pipeline/schemas.py` — extend with Stage-4/5 pydantic schemas if the agents don't already export them.

## What is read-only for you

- `src/llm/wrapper.py`, `src/llm/manifest.py` — `main`.
- `src/agents/`, `src/memory/` — `feature/memory`.
- `src/doctrine/` — `feature/doctrine`. Call `retrieve()` only.
- `src/ui/` — `feature/ui`.

## Tier 2 deliverables

### 1. Wire Stage 3 (`convergence.py`)

Replace the placeholder `cluster_moves()` with a function that constructs the `ConvergenceCartographer`, calls `narrate_convergence(modal_moves, cluster_assignments=None, scenario, run_id)`, and returns a dict matching the existing `clusters.json` contract:

```python
async def cartographer_narrate(
    modal_moves: list[dict],
    scenario: dict,
    run_id: str,
    *,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
) -> dict:
    """Returns {convergence_summary, clusters, notable_absences, cross_run_observations}."""
```

Construct a default `embedder` lazily via `sentence_transformers.SentenceTransformer(MEMORY_EMBEDDING_MODEL)` with the BGE asymmetric query prefix from `MEMORY_QUERY_PREFIX`. Default `store=MemoryStore()`. The Cartographer will recall any prior reflections relevant to the scenario before narrating — this is where the cross-run pattern hook lights up after multiple runs.

The orchestrator awaits this, persists `convergence.md` (the `convergence_summary` text + `notable_absences` list, formatted readable) and `clusters.json` (the structured cluster assignments).

### 2. Stage 4 (`adversarial.py`)

```python
async def generate_off_distribution(
    convergence_summary: dict,   # output of Stage 3
    scenario: dict,
    run_id: str,
    *,
    k: int | None = None,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
) -> list[dict]:
    """Returns K parsed off-distribution proposal dicts with proposal_id, ready to persist."""
```

- `k` defaults from `int(os.environ.get("OFF_DIST_K", "10"))`. Madeleine flagged that K=10 may not surface enough true outliers — keep this configurable so a future scaling pass can crank it without a code change.
- Constructs `OffDistributionGenerator(embed=embedder, store=store)`, calls `propose(...)`. The agent persists each proposal as an `observation` in its memory stream automatically.
- Persist proposals to `off_dist_proposals` table with `proposal_id`, `run_id`, `move_json` (full pydantic dump), `embedding=NULL`, `surviving=NULL` (filled by Stage 5), `median_plaus=NULL`, `would_gen_count=NULL`. Return the list.
- **Hard rule:** no `from src.doctrine.retrieve import retrieve` in this module. The off-distribution stage is doctrine-free by design (PROJECT_SPEC.md §5).

### 3. Stage 5 (`judging.py`)

```python
async def judge_proposals(
    proposals: list[dict],
    scenario: dict,
    run_id: str,
    *,
    embedder: Callable[..., np.ndarray] | None = None,
    store: MemoryStore | None = None,
) -> list[dict]:
    """Per proposal: 5 judges, 2 questions each, return list of judgment dicts."""
```

- Constructs `JudgePool(embed=embedder, store=store)`. Per proposal, calls `pool.judge(proposal, scenario, run_id)` which returns 5 judgment dicts.
- All proposals' judging fan-outs go through `asyncio.gather(*[pool.judge(p, scenario, run_id) for p in proposals])`. The wrapper's per-provider semaphores (Anthropic=8, OpenAI=16) bound the actual fan-out.
- After judging, compute `surviving`, `median_plausibility`, `would_have_gen_count` per proposal:
  - `median_plausibility = median([j.plausibility for j in proposal_judgments])`
  - `would_have_gen_count = sum([j.would_have_generated for j in proposal_judgments])`
  - `surviving = (median_plausibility >= 3) and (would_have_gen_count < ceil(N_judges / 2))` per spec §3.
- Persist each judgment row to `judgments` table; update the `off_dist_proposals` row with the three computed fields.
- Return list of judgment dicts (caller can group by proposal_id for the menu).

### 4. Orchestrator (`orchestrator.py`)

Extend `run_pipeline()` to chain stages:

```python
modal_moves = await generate_modal_moves(scenario, run_id)
convergence = await cartographer_narrate(modal_moves, scenario, run_id, embedder=..., store=...)
proposals = await generate_off_distribution(convergence, scenario, run_id, embedder=..., store=...)
judgments = await judge_proposals(proposals, scenario, run_id, embedder=..., store=...)
menu = build_menu(proposals, judgments)
```

Artifacts under `data/runs/{run_id}/`:
- `manifest.json` (already shipped)
- `modal_moves.json` (already shipped)
- `convergence.md` — readable narration: `## Convergence summary\n\n{text}\n\n## Notable absences\n- ...\n\n## Cross-run observations\n- ...` (empty section omitted)
- `clusters.json` — structured cluster + absence data
- `candidates.json` — list of off-distribution proposals
- `judgments.json` — list of all judgment rows
- `menu.md` — the survival menu, one section per surviving proposal with the audit trail expanded inline

`build_menu(proposals, judgments)` is yours; it's pure data shaping. Returns the markdown string and a JSON-shaped dict for the UI.

### 5. End-to-end runs

Run the full pipeline on both scenarios:

```bash
uv run python -m src.pipeline.orchestrator scenarios/taiwan_strait_spring_2028.yaml
uv run python -m src.pipeline.orchestrator scenarios/israel_me_cascade_2026.yaml
```

Each run will land ~$1.00–1.50 (Tier 1 modal alone was $0.44; Stages 3–5 add ~50 calls). Watch the cost cap; if you hit `CostCapExceeded`, raise `RUN_COST_CAP_USD` env var temporarily — don't edit the wrapper's default.

After both runs land, do a third run on Taiwan to populate the Cartographer's memory with cross-run material; on the *third* Taiwan run the `cross_run_observations` field should start populating with non-trivial content. That's the moment that sells the architecture in §13.2.

### 6. Tests

Add `tests/test_pipeline_dry_run.py`:
- `cartographer_narrate(modal_moves_fixture, scenario_fixture, run_id, embedder=stub, store=in_memory)` returns the right shape with `logged_completion` mocked.
- `judge_proposals` correctly computes survival on a hand-crafted set of judgments.
- `generate_off_distribution` does NOT import `src.doctrine.retrieve` (architectural test).

## Definition of done

- `uv run python -m src.pipeline.orchestrator scenarios/taiwan_strait_spring_2028.yaml` runs end-to-end through Stage 5, exits 0, prints a run_id.
- All 6 expected artifacts under `data/runs/{run_id}/`.
- `sqlite3 data/memory.db "SELECT stage, COUNT(*) FROM llm_calls WHERE run_id='{run_id}' GROUP BY stage;"` shows: modal_ensemble 8, 3_convergence 1, off_distribution 1, plus 5×K judgments × 2 (plausibility + would-have-gen). For K=10: 100 judging calls.
- `uv run pytest tests/` — all green.
- TASK_LEDGER updated with Tier 2 findings.

## What NOT to do

- No edits to `src/llm/wrapper.py` or `src/memory/`.
- No new top-level deps without coordinating in TASK_LEDGER (sentence-transformers, numpy, pydantic, anthropic, openai, tenacity, pyyaml, plotly, streamlit are all already in pyproject).
- No ad-hoc Anthropic / OpenAI SDK imports — every LLM call goes through `logged_completion`.
- No doctrine retrieval in `adversarial.py`.

When you finish, commit with a clear message and push the branch.
