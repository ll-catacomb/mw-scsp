# Tier 1 brief — `feature/memory` worktree

You are working in the `feature/memory` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel on `feature/doctrine`, `feature/pipeline`, `feature/ui`. Coordinate via `TASK_LEDGER.md`.

## Read first

1. `PROJECT_SPEC.md` — sections §3, §4 (memory), §7 (schema), §10 (worktree rules) are most relevant.
2. `TASK_LEDGER.md` — file ownership and current blockers.
3. `src/memory/schema.sql` and `src/memory/store.py` — shipped in Tier 0. Build on these.
4. `src/llm/wrapper.py` — Tier 0 audit-log wrapper. Use it for any LLM call (reflection, importance scoring, agent-summary cache). **Do not edit.**
5. The reflection / importance / agent_summary prompts in `src/prompts/`.

## What you own

- `src/memory/store.py` — extend with full CRUD + retrieval helpers.
- `src/memory/retrieval.py` — implement Park et al. (2023) §4.2 scoring.
- `src/memory/schema.sql` — owner. If pipeline needs new columns, they ask via `TASK_LEDGER.md`; you decide.
- `src/agents/base.py` — `GenerativeAgent` base class.
- `src/agents/convergence_cartographer.py` — Tier 1: skeleton (observation + retrieval, no reflection yet).
- `tests/test_memory_retrieval.py` — unit tests for the retrieval scoring math.

## What is read-only for you

- `src/llm/wrapper.py`
- `src/llm/manifest.py`
- Anything outside `src/memory/`, `src/agents/`, `tests/test_memory_*.py`.

`pyproject.toml` is additive-only; if you need a new dep, add it and note it in TASK_LEDGER.

## Tier 1 deliverables

1. **`MemoryStore` class** in `src/memory/store.py` with these methods:
   - `add_observation(agent_id, description, importance, embedding, source_run_id) -> memory_id`
   - `add_reflection(agent_id, description, importance, embedding, cited_memory_ids, source_run_id) -> memory_id`
   - `retrieve(agent_id, query_embedding, k=8, now=None) -> list[Memory]` — calls into `retrieval.py::score_memories`, bumps `last_accessed_at` on returned rows.
   - `recent(agent_id, n=100) -> list[Memory]` — for reflection question-generation.
   - `unreflected_importance_sum(agent_id) -> int` — for the reflection trigger.

2. **`retrieval.py::score_memories`** implementing the spec faithfully:
   - recency = `decay_per_day ** days_since_last_access`
   - importance = stored 1–10 score
   - relevance = cosine similarity vs `query_embedding`
   - min-max normalize each component to [0,1] across the candidate set
   - `score = α_r·recency + α_i·importance + α_v·relevance` with all α=1 by default
   - Return `[(memory, score), ...]` sorted descending.

3. **`GenerativeAgent` base** in `src/agents/base.py`:
   - constructor takes `agent_id`, `agent_role`, embedding callable, `MemoryStore`.
   - `observe(description, source_run_id)` — calls importance-score prompt via `logged_completion`, embeds, persists.
   - `recall(query, k=8)` — embeds query, calls `MemoryStore.retrieve`, returns memories.
   - `summary_paragraph(query)` — pulls cached row from `agent_summary` table; placeholder regenerator hook (Tier 2 fills in).
   - `reflect()` — placeholder method that raises `NotImplementedError("Tier 2")`.

4. **`ConvergenceCartographer`** in `src/agents/convergence_cartographer.py`:
   - subclass of `GenerativeAgent` with `agent_id="convergence_cartographer"`, `agent_role="Convergence Cartographer for adversarial-distribution red team"`.
   - method `narrate_convergence(modal_moves, cluster_assignments, scenario, run_id) -> dict` — calls the `convergence_summary.md` prompt via `logged_completion` with retrieved prior reflections injected. Returns the parsed JSON from the prompt.

5. **Unit tests** in `tests/test_memory_retrieval.py`:
   - recency decay over a 30-day gap is detectably less than 1.
   - min-max normalization is correct on a hand-crafted 3-memory set.
   - weighted-sum ordering matches a manual computation.
   - relevance uses cosine, not dot product.
   - At least one test runs end-to-end against an in-memory SQLite db.

## Definition of done

- `uv run pytest tests/test_memory_retrieval.py` — all green.
- `uv run python -c "from src.agents.convergence_cartographer import ConvergenceCartographer; print('ok')"` — clean import.
- A short note added to `TASK_LEDGER.md` under "Open questions" if anything in the spec turned out to need clarification.

## What NOT to do in Tier 1

- No reflection module — Tier 2.
- No Off-Distribution Generator agent — Tier 2.
- No Judge Pool — Tier 2.
- No edits to `src/llm/wrapper.py` or `src/llm/manifest.py`.

When you finish, commit with a clear message and push the branch. The main worktree will squash-merge.
