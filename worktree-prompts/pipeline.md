# Tier 1 brief — `feature/pipeline` worktree

You are working in the `feature/pipeline` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

## Read first

1. `PROJECT_SPEC.md` — sections §3 (pipeline), §6 (cross-family), §9 (logging). Whole spec is short; read it.
2. `TASK_LEDGER.md` — file ownership and current blockers.
3. `src/llm/wrapper.py` — every LLM call goes through `logged_completion`. **Read it carefully and use it correctly. Do not edit.**
4. `src/prompts/modal_red.md` — the prompt you'll be calling.
5. `_context/agent-output/ra6-cross-family-api.md` (when it lands) — current model ids and pricing. Defer to this over the spec.
6. `scenarios/taiwan_strait_spring_2028.yaml`.

## What you own

- `src/pipeline/orchestrator.py`
- `src/pipeline/modal_ensemble.py`
- `src/pipeline/convergence.py` — clustering helper only in Tier 1; the Cartographer narration call lives in `feature/memory` (Tier 2 wires it up).

## What is read-only for you

- `src/llm/wrapper.py`, `src/llm/manifest.py` — owned by `main`.
- `src/memory/`, `src/agents/` — owned by `feature/memory`. **Do not edit.** If your code needs to call an agent, do it via the public method on the agent class.
- `src/doctrine/` — owned by `feature/doctrine`. Call `retrieve()` only.

`pyproject.toml` is additive-only.

## Tier 1 deliverables

1. **`src/pipeline/modal_ensemble.py::generate_modal_moves(scenario: dict, run_id: str) -> list[dict]`**:
   - Build the prompt from `src/prompts/modal_red.md` by substituting `{{ scenario_block }}`, `{{ doctrine_block }}`, `{{ k }}`, `{{ red_team_question }}`. Use a small templating helper (str.replace is fine — keep it simple).
   - For each instance i in 0..7:
     - Pick model: i in 0..3 → `os.environ["MODAL_CLAUDE_MODEL"]`; i in 4..7 → `os.environ["MODAL_GPT_MODEL"]`.
     - Pick temperature: random.uniform(0.8, 1.0) seeded with `(run_id, i)` for reproducibility.
     - Retrieve top-6 doctrine passages via `src.doctrine.retrieve.retrieve(scenario["red_team_question"])`.
     - Call `logged_completion(run_id=run_id, stage="modal_ensemble", agent_id=None, model=..., system=..., user=..., temperature=..., prompt_path="src/prompts/modal_red.md", response_format=ModalMoveSchema)`.
   - Run all 8 calls concurrently with `asyncio.gather`. The wrapper enforces a global semaphore; you don't need a second one.
   - Persist each parsed move to `modal_moves` table with its `move_id` (uuid), `instance_idx`, `provider`, `model`, `temperature`, `move_json`, `doctrine_cited`, `embedding` (computed via the same sentence-transformers model used for doctrine — keep that as a thin re-use, not a new dep).
   - Return list of dicts (the parsed schemas as `model_dump()`s, with `move_id` added).

2. **`ModalMoveSchema`** as a pydantic model matching the JSON shape in `src/prompts/modal_red.md`. Co-locate with the pipeline module (or in a new `src/pipeline/schemas.py`).

3. **`src/pipeline/convergence.py`** — Tier 1 ships the clustering helper only:
   - `cluster_moves(moves: list[dict], n_clusters: int | None = None) -> dict` — KMeans over the move embeddings (sklearn). Auto-pick k via simple heuristic (e.g., `min(4, len(moves)//2)`) if not specified. Return `{cluster_assignments: list[int], cluster_centroids: list[list[float]], cluster_themes: None}`. Themes get filled in by the Cartographer in Tier 2.
   - **Do not** call the Cartographer here. Tier 2 wires that up via the orchestrator.

4. **`src/pipeline/orchestrator.py::run_pipeline(scenario_path, run_id=None)`** — Tier 1 ships through Stage 3 clustering only:
   - Load scenario YAML.
   - Generate run_id if missing (uuid).
   - `init_db()` and insert a row in `runs` with status='running'.
   - Call `manifest.write_manifest(run_id, scenario, config)`.
   - Call `generate_modal_moves`.
   - Call `cluster_moves`.
   - Write `data/runs/{run_id}/modal_moves.json` (list of moves) and `data/runs/{run_id}/clusters.json` (the cluster output).
   - Mark run status='complete'. Return run_id.

5. **Dry-run script**: `python -m src.pipeline.orchestrator scenarios/taiwan_strait_spring_2028.yaml` runs end-to-end through clustering and prints the run_id. (You can wire this via `if __name__ == "__main__":` at the bottom of `orchestrator.py` — argparse on a single positional arg is enough.)

## Definition of done

- `uv run python -m src.pipeline.orchestrator scenarios/taiwan_strait_spring_2028.yaml` completes without errors.
- `data/runs/{run_id}/manifest.json`, `modal_moves.json`, `clusters.json` are all written.
- `sqlite3 data/memory.db "SELECT COUNT(*) FROM llm_calls WHERE run_id='{run_id}';"` returns 8.
- `data/memory.db` `modal_moves` table has 8 rows with embeddings populated.

## What NOT to do in Tier 1

- No Off-Distribution Generator stage (Tier 2).
- No Judge Pool stage (Tier 2).
- No Cartographer narration (Tier 2; lives in `feature/memory`'s code).
- No Streamlit (Tier 2; `feature/ui`).
- No edits to `src/llm/wrapper.py`.

When you finish, commit with a clear message and push the branch.
