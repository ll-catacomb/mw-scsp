# Tier 2 brief — `feature/memory` worktree

You are working in the `feature/memory` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel on `feature/doctrine`, `feature/pipeline`, `feature/ui`. Coordinate via `TASK_LEDGER.md`.

Tier 1 shipped: `MemoryStore` CRUD, Park et al. retrieval scoring, `GenerativeAgent` base, `ConvergenceCartographer` skeleton with `narrate_convergence()`. All on main.

## Read first

1. `PROJECT_SPEC.md` — sections §3 (pipeline), §4 (memory architecture, especially §4.3 reflection and §4.5 the four agents), §15 (definition of done).
2. `TASK_LEDGER.md` — current tier, Tier 1 follow-ups (especially the embedding-callable signature note and `unreflected_importance_sum` semantics).
3. `src/agents/base.py` — Tier 1 `GenerativeAgent`. The `reflect()` stub is yours to fill in.
4. `src/agents/convergence_cartographer.py` — exemplar for how a stage agent wires `narrate_convergence` against `logged_completion` + a pydantic schema. Copy this pattern.
5. `src/memory/store.py` and `retrieval.py` — already feature-complete; no edits expected.
6. `src/prompts/{off_distribution,judge_plausibility,judge_off_dist_check,reflection_questions,reflection_insights,agent_summary}.md`.

## What you own

- `src/agents/off_distribution_generator.py` — fill in `OffDistributionGenerator(GenerativeAgent)`.
- `src/agents/judge_pool.py` — fill in `JudgePool` with 5 calibrated judge instances.
- `src/agents/base.py::GenerativeAgent.reflect()` — implement Park et al. §4.2 two-step.
- New: `agent_summary` regenerator on `GenerativeAgent` (or a free function in `base.py`).
- `tests/test_memory_*.py` — extend with tests for the new agents and the reflection trigger.

## What is read-only for you

- `src/llm/wrapper.py`, `src/llm/manifest.py` — owned by `main`.
- `src/memory/{schema.sql,store.py,retrieval.py}` — settled in Tier 1.
- `src/doctrine/`, `src/pipeline/`, `src/ui/` — other worktrees.

`pyproject.toml` is additive-only.

## Tier 2 deliverables

### 1. `OffDistributionGenerator`

Subclass `GenerativeAgent` with `agent_id="off_distribution_generator"`, `agent_role="Off-distribution generator for adversarial-distribution red team"`. Methods:

```python
async def propose(
    self,
    convergence_summary: dict,   # output of ConvergenceCartographer.narrate_convergence
    scenario: dict,
    run_id: str,
    k: int = 10,
) -> list[dict]:
    """Generate K candidate off-distribution moves. Persists each as an observation."""
```

Behaviour:
- Recall past proposals via `self.recall(query=...)` where the query is the scenario+convergence summary. These are injected into `off_distribution.md`'s `{{ prior_proposals_block }}` slot.
- Pydantic response schema mirrors the JSON contract at the bottom of `off_distribution.md` (a list of K proposals, each with `move_title`, `summary`, `actions`, `intended_effect`, `which_convergence_pattern_it_breaks`, `why_a_red_planner_could_justify_this`, `risks_red_accepts`).
- After the LLM call, persist each proposal as an observation via `self.observe()` — that runs the importance-score prompt, embeds, writes to the memory stream. Importance prompts may rate proposals 6–9 on average (they're meant to be off-distribution).
- Return `list[dict]` of the parsed proposals with a synthetic `proposal_id` (uuid) added per item. The pipeline persists to the `off_dist_proposals` table.
- **Use `HEAVY_CLAUDE_MODEL`** (default `claude-opus-4-7`) — this stage benefits from the heavier model.
- **Temperature 0.9–1.2** — push the model out of the modal cluster. GPT-5/5.5 are pinned to 1.0 by their API; for this stage prefer Claude.
- **No doctrine retrieval.** This is the architectural commitment in PROJECT_SPEC.md §5. Do not import from `src.doctrine.retrieve`.

### 2. `JudgePool`

Five tagged judge instances, mixed family. Logical agent (judge_id encodes the instance + family); each has its own memory stream of past ratings (per-judge calibration history).

```python
JUDGE_INSTANCES = [
    ("judge_0", "anthropic"),
    ("judge_1", "anthropic"),
    ("judge_2", "anthropic"),
    ("judge_3", "openai"),
    ("judge_4", "openai"),
]

async def judge(
    self,
    proposal: dict,
    scenario: dict,
    run_id: str,
) -> list[dict]:
    """For one proposal, return 5 judgment dicts (one per judge instance)."""
```

Behaviour:
- Per proposal, run 5 judgments concurrently via `asyncio.gather`. Each judge calls `judge_plausibility.md` and `judge_off_dist_check.md` separately (fresh contexts so the two signals are independent — the spec's hard rule).
- Per-judge calibration: after each judgment, `observe()` an entry like `"judge_0 rated proposal abc123 plausibility=4, would_have_generated=False"` so calibration drift is visible in the audit.
- Family rotation across the 5 judges per proposal: judge_0..2 are anthropic, judge_3..4 are openai. To avoid family-bias compounding, rotate which family votes first by `proposal_index % 2` (this is structural, no behavior change at temp=0.2 but it's the spec).
- Return per-judgment dict: `{judgment_id, proposal_id, judge_id, plausibility (1–5), rationale, would_have_generated (bool)}`.
- Use `JUDGE_CLAUDE_MODEL` (default `claude-haiku-4-5-20251001`) and `JUDGE_GPT_MODEL` (default `gpt-5`). Temperature 0.2 (deterministic).

### 3. Reflection (`GenerativeAgent.reflect`)

Park et al. §4.2 two-step:

1. Run `reflection_questions.md` over the agent's 100 most recent memories (`self.store.recent(self.agent_id, n=100)`). Get 3 questions.
2. For each question: call `recall(question, k=12)`, render the retrieved memories as `1. {desc}\n2. {desc}\n...`, run `reflection_insights.md` to extract 5 insights with cited indices. Convert cited indices back to memory_ids.
3. For each insight: `observe()` it (gets importance scored + embedded) **but** as a `reflection` row not `observation`. Use `self.store.add_reflection(...)` directly so `cited_memory_ids` is populated.

Triggered when `self.store.unreflected_importance_sum(self.agent_id) >= 50`. Threshold is tunable.

Reflections can themselves be retrieved in future runs and cited in further reflections (Park et al. Fig. 7). The `recall(memory_types=["reflection"])` filter on `MemoryStore.retrieve` already supports this.

### 4. `agent_summary` regenerator

Cached paragraph from `agent_summary.md` (Park et al. Appendix A). Three queries per spec:
- `f"{agent_role}'s core analytical disposition"`
- `f"{agent_role}'s recent focus"`
- `f"{agent_role}'s observed blind spots and tendencies"`

Concatenate the three answers into one paragraph, write via `self.store.write_summary(agent_id, paragraph)`. Regenerate every 3 runs OR whenever a new reflection lands. Cache stays useful across runs because the `agent_summary` table is versioned.

Add `GenerativeAgent.regenerate_summary_if_stale(run_count: int) -> bool` and `GenerativeAgent.summary_paragraph()` should fall back to a freshly-generated summary if the cache is empty (currently returns `None`).

### 5. Tests

Mock `logged_completion` so tests stay offline. Cover:
- `OffDistributionGenerator.propose()` — calls the right prompt, persists K observations, returns K dicts with proposal_ids.
- `JudgePool.judge()` — calls both judge prompts per judge, returns 5 judgment dicts, each judgment is observed for calibration.
- `GenerativeAgent.reflect()` — given seeded memories, runs both reflection prompts, persists reflection-type memories with `cited_memory_ids` populated.
- Reflection trigger: `unreflected_importance_sum` resets after `reflect()` lands new reflection rows.
- `regenerate_summary_if_stale` — returns True every 3 calls; writes a new versioned row.

## Definition of done

- `uv run pytest tests/test_memory_retrieval.py tests/test_memory_agents.py` — all green.
- `uv run python -c "from src.agents.off_distribution_generator import OffDistributionGenerator; from src.agents.judge_pool import JudgePool; print('ok')"` — clean import.
- A short note in `TASK_LEDGER.md` Tier 2 follow-ups if anything in the spec turned out to need clarification.

## What NOT to do in Tier 2

- No edits to `src/llm/wrapper.py`, `src/llm/manifest.py`, `src/memory/{store,retrieval,schema.sql}`.
- No edits to `src/doctrine/`, `src/pipeline/`, `src/ui/`.
- No doctrine retrieval in the OffDistributionGenerator. This is the system's architectural commitment.

When you finish, commit with a clear message and push the branch.
