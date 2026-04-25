# Tier 1 brief — `feature/pipeline` worktree

You are working in the `feature/pipeline` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

## Read first

1. `PROJECT_SPEC.md` — sections §3 (pipeline), §5 (markdown doctrine corpus, **not RAG**), §6 (cross-family), §9 (logging). Whole spec is short; read it.
2. `TASK_LEDGER.md` — file ownership and current blockers.
3. `src/llm/wrapper.py` — every LLM call goes through `logged_completion`. Direct SDK calls per RA-6 (no LiteLLM). Per-provider semaphores. Vendored price table. **Read it carefully and use it correctly. Do not edit.**
4. `src/doctrine/retrieve.py` — call `await retrieve(query, stage='modal-grounding', top_k=6, run_id=run_id)`. The two-pass retriever returns `[{id, source, edition, section, page, type, priority, topics, body, score, ...}]` — full passage bodies inline.
5. `src/prompts/modal_red.md` — the prompt you'll be calling.
6. `_context/agent-output/ra6-cross-family-api.md` — model ids (`claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5-20251001`, `gpt-5.5`, `gpt-5`), pricing, structured-output specifics.
7. `scenarios/taiwan_strait_spring_2028.yaml` and `scenarios/israel_me_cascade_2026.yaml`.

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
   - **Doctrine block:** call `await retrieve(scenario["red_team_question"], stage="modal-grounding", top_k=6, run_id=run_id)` ONCE per run (not per instance — same retrieval feeds all 8 modal calls). Render hits as `## {id} — {source} {section} (p.{page})\n\n{body}` separated by `---`. The list of returned `id`s populates each move's `doctrine_cited` field.
   - For each instance i in 0..7:
     - Pick model: i in 0..3 → `os.environ["MODAL_CLAUDE_MODEL"]`; i in 4..7 → `os.environ["MODAL_GPT_MODEL"]`.
     - Pick temperature: `random.Random((run_id, i)).uniform(0.8, 1.0)` for reproducibility.
     - Call `await logged_completion(run_id=run_id, stage="modal_ensemble", agent_id=None, model=..., system=..., user=..., temperature=..., prompt_path="src/prompts/modal_red.md", response_format=ModalMoveSchema)`.
   - Run all 8 calls concurrently with `asyncio.gather`. The wrapper has per-provider semaphores (Anthropic=8, OpenAI=16); you don't need to add another.
   - Persist each parsed move to `modal_moves` table with `move_id` (uuid), `instance_idx`, `provider`, `model`, `temperature`, `move_json`, `doctrine_cited` (JSON list of passage ids the model said it used). The `embedding` column is `NULL` in this build — clustering happens via the Cartographer in Tier 2, not via sentence-transformers on move bodies.
   - Return list of dicts (the parsed schemas as `model_dump()`s, with `move_id` added).

2. **`ModalMoveSchema`** as a pydantic model matching the JSON shape in `src/prompts/modal_red.md`. Co-locate with the pipeline module (or in a new `src/pipeline/schemas.py`).

3. **`src/pipeline/convergence.py`** — Tier 1 ships clustering only. Two options; pick one:
   - **Option A (preferred):** **No clustering math.** Move clustering is moved from KMeans (which needed embeddings) to LLM-driven grouping by the Cartographer in Tier 2. In Tier 1 just write `def cluster_moves(moves) -> dict` that returns `{"cluster_assignments": [None]*len(moves), "cluster_themes": None}` as a placeholder so the orchestrator's contract is stable.
   - **Option B (fallback):** Compute embeddings of move summaries via `sentence-transformers` (`os.environ["MEMORY_EMBEDDING_MODEL"]`) just for clustering, KMeans with `min(4, len(moves)//2)`. Same model the memory layer uses; no new dep. Document the choice in TASK_LEDGER.
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
- `data/memory.db` `modal_moves` table has 8 rows. The `embedding` column may be NULL (Option A above) — that's expected.
- Each row's `doctrine_cited` is a JSON list of passage ids that exist in the corpus. Validate by joining against `data/doctrine/passages/` ids.

## What NOT to do in Tier 1

- No Off-Distribution Generator stage (Tier 2).
- No Judge Pool stage (Tier 2).
- No Cartographer narration (Tier 2; lives in `feature/memory`'s code).
- No Streamlit (Tier 2; `feature/ui`).
- No edits to `src/llm/wrapper.py`.

When you finish, commit with a clear message and push the branch.
