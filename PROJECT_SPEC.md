# Adversarial-Distribution Red Team
## Claude Code project spec — SCSP Hackathon 2026, Wargaming Track, Boston

You are scaffolding and building a hackathon prototype. Read this whole document before starting, then plan and build. This spec is authoritative. The user is working solo across multiple Claude Code instances in parallel git worktrees — coordination rules are in §10. Move fast; ask before non-obvious architectural changes.

---

## 1. What we're building

A wargame Red-team tool that uses an ensemble of LLMs as a **mirror of the modal** to surface adversary moves that are plausible but off-distribution — the moves a smart-but-average AI red team *doesn't* think of. The output is a menu of hypotheses for a human red team to evaluate. Not a forecast. Not a replacement for human judgment. A tool that makes one specific failure mode of LLM-driven wargaming visible and addressable.

Four properties make this different from a generic "LLM plays Red" demo:

1. **Adversarial-distribution generation.** The system explicitly searches the gap between "plausible" and "predictable" by using the convergence of an ensemble as a map of what *not* to propose.
2. **Persistent generative-agent memory.** Each persistent role (Convergence Cartographer, Off-Distribution Generator, Judge Pool) is implemented as a generative agent in the Park et al. (2023) sense — full memory stream with recency/importance/relevance retrieval and periodic reflection. The system gets sharper across runs.
3. **Cross-family ensemble.** The modal stage runs Claude and GPT side by side. Different model families have different distributional centers; convergence between them is more meaningful than convergence within one family.
4. **Full audit trail.** Every LLM call, every parsed output, every judge rationale is logged at the decision level. Reproducibility from a `run_id` is a first-class feature.

The core epistemic claim is the contribution as much as the code: **wargaming AI tools that overclaim are the failure mode the field is already drowning in. This system is built to resist that.**

---

## 2. Why this matters for the SCSP track

The Wargaming track explicitly asks for AI-driven Red Cell adversaries that adapt to player behavior, modular adjudication, and ways to "transform wargaming from a static, episodic event into a rapid, on-demand capability." Most teams will build the obvious version: an LLM prompted to play Red, maybe with doctrine RAG, maybe with multi-turn play. That version produces fluent, plausible, **predictable** adversary behavior — which is the worst possible failure mode for the function red-teaming actually serves. We are building the version that knows this is a problem and addresses it directly.

Yuna Wong is on the Boston judging panel. Her published work has been consistently sharp on the validation problem in wargaming, the field's failure to accumulate empirical knowledge across one-off games, and the institutional habit of consuming wargame outputs as predictions when they aren't. Our project is designed to land in front of someone who has read that literature: outputs structured as hypotheses, full provenance, knowledge accumulation across runs, and loud disclaimers about limits. **Do not name-check her work in the demo.** She'll recognize the register; flattery undercuts it.

---

## 3. Architecture: the five-stage pipeline

```
[Scenario YAML]
     │
     ▼
[Stage 2: Modal Ensemble]      N=8 independent calls, mixed Claude + GPT,
     │                          temp 0.8–1.0, doctrine-grounded (markdown index)
     ▼
[Stage 3: Convergence Cartographer]   Generative agent with persistent memory.
     │                                Embedding-cluster the modal moves; produce
     │                                structured summary + "notable absences";
     │                                cross-references prior-run convergence patterns.
     ▼
[Stage 4: Off-Distribution Generator] Generative agent with persistent memory of
     │                                past proposals. K=10 candidate moves
     │                                instructed to escape the convergence summary.
     ▼
[Stage 5: Judge Pool]                 5 judges, fresh contexts, mixed providers.
     │                                Two questions per move: plausibility (1–5)
     │                                and "would you have generated this?" (Y/N).
     ▼
[Menu: surviving moves, full audit trail, doctrine citations, judge rationales]
```

**Survival criteria:** median plausibility ≥ 3 AND fewer than half of judges said "I would have generated this myself." The two thresholds together are the filter.

---

## 4. Memory architecture (Generative Agents, adapted)

The persistent agents are implemented following Park, O'Brien, Cai, Morris, Liang & Bernstein, *Generative Agents: Interactive Simulacra of Human Behavior* (UIST '23, arXiv:2304.03442). That paper's three modules — memory stream, reflection, planning — translate cleanly to our use case, with planning de-emphasized (we don't need agents that "live a day"; we need agents that accumulate analytical state across runs).

### 4.1 Memory stream

Each persistent agent maintains a memory stream: a list of memory objects, each with a natural-language description, a creation timestamp, and a most-recent-access timestamp. Memory objects come in two types for our use case:

- **Observation:** something the agent perceived. For the Cartographer, observations are the modal moves of a given run plus the convergence summary it produced. For the Off-Distribution Generator, observations are its proposed moves plus their judgment outcomes. For judges, observations are their per-move ratings.
- **Reflection:** higher-level synthesis (see §4.3).

Park et al.'s third type, **plans**, we don't use. Their agents simulate daily life; ours accumulate analytical state across discrete pipeline runs. Memory is persisted in SQLite; schema in §7.

### 4.2 Retrieval scoring

When an agent acts, retrieval surfaces the top-k memory objects most relevant to the current situation. Park et al. score each memory by a weighted combination of recency, importance, and relevance:

```
score = α_recency · recency + α_importance · importance + α_relevance · relevance
```

with all α = 1, recency as exponential decay over time-since-last-access (decay factor 0.995 per sandbox hour in their work; we use decay-per-day-since-last-access since our agents run intermittently across runs, not continuously), importance as a 1–10 score generated at memory-creation time, and relevance as cosine similarity between the current query embedding and the memory embedding. Final scores are min-max normalized to [0, 1] before weighting.

**Importance prompt** (verbatim adapted from Park et al., §4.1):

```
On the scale of 1 to 10, where 1 is a routine adversary move (e.g., standard
ISR posture, scheduled exercise) and 10 is a doctrine-violating off-distribution
move that fundamentally changes the strategic calculus, rate the likely
significance of the following piece of memory.

Memory: {memory_text}
Rating: <fill in>
```

Asked at memory-creation time; the integer is stored alongside the memory.

### 4.3 Reflection

Reflections are higher-level inferences synthesized from observations. Park et al. trigger reflection when the sum of importance scores for unreflected memories exceeds 150; their agents reflect roughly 2–3 times per day. We trigger reflection per-agent at the end of each pipeline run, conditional on accumulated importance crossing a threshold (start at 50, tune from there — our memory volume is much smaller than Smallville's).

Reflection generation follows the two-step prompt from Park et al. §4.2:

**Step 1 — generate questions:**
```
[100 most recent memory descriptions]

Given only the information above, what are 3 most salient
high-level questions we can answer about the patterns in these memories?
```

**Step 2 — extract insights with citations:**
```
Statements about {agent_name}:
1. {memory_1}
2. {memory_2}
...

What 5 high-level insights can you infer from the above statements?
(example format: insight (because of 1, 5, 3))
```

The cited insights are stored as reflection-type memories with pointers to the source memories. Reflections can themselves be retrieved in future runs and cited in further reflections, producing a tree (Park et al. Fig. 7).

**For the Convergence Cartographer specifically**, reflection is where the system's knowledge accumulation lives. After several runs, the Cartographer reflects on convergence patterns and produces insights like *"the ensemble has proposed quarantine-as-opening-move in 4 of 5 PLA Taiwan scenarios — this is a recurring model-wide blind spot, not scenario-specific."* This is the line that, when surfaced in the demo, sells the persistent-memory architecture in a single sentence.

### 4.4 Agent summary cache

Park et al. cache a paragraph-long summary of each agent that gets prepended to many prompts (their Appendix A). We do the same, with three queries:
- "{agent_name}'s core analytical disposition"
- "{agent_name}'s recent focus"
- "{agent_name}'s observed blind spots and tendencies"

The summary is regenerated whenever the agent's memory has changed materially (heuristic: every 3 runs, or whenever a new reflection is produced). Cached in an `agent_summary` table keyed by agent_id + version.

### 4.5 The four persistent agents

| Agent | Memory consists of | Used for |
|---|---|---|
| `convergence_cartographer` | Past convergence patterns, scenario summaries, prior reflections | Stage 3 — produces the convergence summary, references prior runs |
| `off_distribution_generator` | All previously proposed off-distribution moves, with plausibility and survival outcomes | Stage 4 — instructed not to repeat near-duplicates, push further into novelty |
| `judge_pool` (logical, with 5 instances each tagged) | Per-judge calibration history: how often each judge rates plausible, how often each says "would have generated" | Stage 5 — used to detect outlier judges and surface drift in the audit |
| `audit_trail` | Master log of every LLM call | Not really an agent; the full logging spine (§9) |

### 4.6 Park et al.'s ablation finding (the citation that justifies the architecture)

In their controlled evaluation, Park et al. report TrueSkill ratings: full architecture μ=29.89, no-reflection μ=26.88, no-reflection-no-planning μ=25.64, human crowdworkers μ=22.95, no-memory-no-planning-no-reflection μ=21.21. The gap between full architecture and the no-memory baseline — which corresponds to a generic "LLM plays a role" agent — was Cohen's d = 8.16, eight standard deviations. Every component contributed significantly. This is the citation that justifies including all three modules even at hackathon scale: the no-memory baseline is what every other team will ship, and the literature says it's eight standard deviations worse on believability.

### 4.7 Acknowledged failure modes

Park et al. document three failure modes we will inherit and the README should acknowledge: (a) memory retrieval failures (the agent fails to surface a relevant memory), (b) hallucinated embellishments (the agent invents details beyond what memory supports), (c) instruction-tuning-induced over-formality and over-cooperation.

---

## 5. Doctrine index (markdown corpus, not RAG)

The modal ensemble's "smartness" depends on grounding. We index:

- Joint Publication 3-0 (Joint Operations / Joint Campaigns and Operations) — adversary planning, operational design, phasing
- Joint Publication 5-0 (Joint Planning) — COA development, wargaming, assumptions
- Selected CSIS open-access analysis on PLA Taiwan operational concepts (specific selection from RA-1)
- Selected open-access analysis on Iran/Israel/Hezbollah/Houthi operations for the second scenario (RA-4)

**Implementation.** A directory of small markdown files under `data/doctrine/passages/`, one passage per file, with YAML frontmatter the loader parses into a pydantic model. No embeddings, no Chroma, no chunking. The bounded corpus (well under 100 files of curated passages) does not justify the overhead, and the frontmatter approach gives auditable provenance "for free": citations in `modal_moves.doctrine_cited` are stable file slugs, and the loader records which passages were retrieved on which call into the audit log.

The schema is defined in `data/doctrine/passages/SCHEMA.md` — required fields are `id`, `source`, `edition`, `section`, `page`, `type`, `priority`, `topics`, `keywords`, `applies-to`. Optional: `synonyms`, `related`. See the schema doc for the controlled vocabulary on `type`, `priority`, and `applies-to`.

**Retrieval.** Two-pass:

1. **Keyword/topic match.** Tokenize the query, intersect with `by_keyword` (incl. synonyms) and `by_topic`, filter by `applies-to == stage`, score by (keyword hits + 0.5 × topic hits + priority weight), take top-k.
2. **LLM router (only if pass 1 returns < 2 hits).** Pass the index summary (id + section + one-line frontmatter description) to a small Claude/GPT call that returns up to top-k passage ids. Catches off-distribution Red vocabulary that doesn't lexically match the doctrine.

The loader is cheap enough to call at the start of every pipeline run (< 200 ms for a corpus this size); no persistent index needed.

**Use.** The modal ensemble's prompt does retrieval before generation (top-k=6 passages, `applies-to: modal-grounding`) and includes the matched passage bodies inline. Each generated modal move includes a `doctrine_cited` field listing passage `id` strings. **The off-distribution generator does NOT do retrieval** — its job is to escape the gap, not stay in it. The Blue adjudicator retrieves with `applies-to: adjudication` (and `off-distribution-flag` when scoring whether a Red move slipped the doctrinal frame).

`src/doctrine/index.py` builds the index; `src/doctrine/retrieve.py` runs the two-pass query. Raw PDFs in `data/doctrine/raw/` are gitignored; the curated `passages/` tree is tracked.

---

## 6. Cross-family ensemble (Claude + GPT)

The modal ensemble is N=8 calls: 4 Claude, 4 GPT. The judge pool is 5 calls split 3/2 by family, rotated per move so family-bias doesn't compound.

### 6.1 Implementation

Use `litellm` (BerriAI) as the unified API layer. It handles provider abstraction, retries, and cost tracking, and lets us swap models without changing the wrapper. Configure both providers via env vars:

```bash
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

Models (current identifiers and pricing to be confirmed in RA-6 output):
- Claude: `claude-sonnet-4-6` for the modal ensemble (cheaper, fast, N=4 instances), `claude-opus-4-7` for the off-distribution generator and Cartographer (better at the harder generative + synthesis tasks).
- GPT: latest GPT-4-class model for the modal ensemble (N=4) and judge pool slots.

### 6.2 Concurrency and retries

Use `asyncio.gather` with bounded concurrency (semaphore at 4) and `tenacity` for exponential-backoff retries on rate-limit and transient errors. The `logged_completion()` wrapper handles all of this; downstream code awaits it like a normal function.

### 6.3 Structured output

For stages that need JSON (modal moves, judge ratings), use the providers' structured-output features:
- Claude: tool use with a forced tool schema
- OpenAI: JSON mode with response_format

`litellm` papers over both. Prompts produce the same JSON schema regardless of provider; the wrapper validates against a pydantic model and retries once with a clarifying note if parsing fails.

### 6.4 Prompt portability

Avoid model-family-specific quirks: no Claude-specific XML tags in shared prompts (use them only in Claude-only prompts if needed); no OpenAI-specific function-calling syntax in shared prompts. Prompts live in `src/prompts/*.md` and are model-agnostic. Where a prompt needs to differ by family, suffix the file: `modal_red.claude.md`, `modal_red.gpt.md`, with a default `modal_red.md` that works for both.

### 6.5 Cost budgeting

One full pipeline run is roughly 75K tokens mixed across providers, ≈ $1–3 per run at current pricing. Budget 30 runs across the hackathon for prompt iteration and demo prep; cap at $100 total spend with hard limits in `logged_completion()`. RA-6 should confirm current per-token rates.

---

## 7. SQLite schema

```sql
-- Master log of every LLM call
CREATE TABLE llm_calls (
  call_id        TEXT PRIMARY KEY,
  run_id         TEXT NOT NULL,
  stage          TEXT NOT NULL,
  agent_id       TEXT,
  provider       TEXT NOT NULL,        -- 'anthropic' | 'openai'
  model          TEXT NOT NULL,
  temperature    REAL,
  system_prompt  TEXT,
  user_prompt    TEXT NOT NULL,
  raw_response   TEXT NOT NULL,
  parsed_output  TEXT,
  prompt_hash    TEXT NOT NULL,        -- SHA256 of (system + user)
  prompt_version TEXT NOT NULL,        -- git hash of prompt file at call time
  input_tokens   INTEGER,
  output_tokens  INTEGER,
  latency_ms     INTEGER,
  cost_usd       REAL,
  timestamp      TEXT NOT NULL
);

CREATE TABLE runs (
  run_id        TEXT PRIMARY KEY,
  scenario_id   TEXT NOT NULL,
  started_at    TEXT NOT NULL,
  completed_at  TEXT,
  config_hash   TEXT NOT NULL,
  status        TEXT NOT NULL          -- 'running' | 'complete' | 'failed'
);

-- Generative-agents memory stream
CREATE TABLE agent_memory (
  memory_id        TEXT PRIMARY KEY,
  agent_id         TEXT NOT NULL,
  memory_type      TEXT NOT NULL,      -- 'observation' | 'reflection'
  description      TEXT NOT NULL,
  embedding        BLOB NOT NULL,       -- numpy float32, serialized
  importance       INTEGER NOT NULL,    -- 1-10
  created_at       TEXT NOT NULL,
  last_accessed_at TEXT NOT NULL,
  source_run_id    TEXT,
  cited_memory_ids TEXT                 -- JSON array, for reflections
);

CREATE INDEX agent_memory_agent_idx ON agent_memory(agent_id);

-- Cached agent summaries (Park et al. Appendix A)
CREATE TABLE agent_summary (
  agent_id    TEXT NOT NULL,
  version     INTEGER NOT NULL,
  summary     TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  PRIMARY KEY (agent_id, version)
);

-- Stage tables
CREATE TABLE modal_moves (
  move_id         TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL,
  instance_idx    INTEGER NOT NULL,    -- 0..7
  provider        TEXT NOT NULL,
  model           TEXT NOT NULL,
  temperature     REAL NOT NULL,
  move_json       TEXT NOT NULL,
  doctrine_cited  TEXT,                 -- JSON array of passage_ids
  embedding       BLOB
);

CREATE TABLE off_dist_proposals (
  proposal_id     TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL,
  move_json       TEXT NOT NULL,
  embedding       BLOB,
  surviving       INTEGER,
  median_plaus    REAL,
  would_gen_count INTEGER
);

CREATE TABLE judgments (
  judgment_id     TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL,
  proposal_id     TEXT NOT NULL,
  judge_id        TEXT NOT NULL,
  plausibility    INTEGER NOT NULL,
  rationale       TEXT NOT NULL,
  would_have_gen  INTEGER NOT NULL
);
```

---

## 8. File structure

```
adversarial-redteam/
├── README.md
├── pyproject.toml
├── PROJECT_SPEC.md              ← this file (drop in main worktree)
├── RESEARCH_PROMPTS.md          ← parallel-agent prompts (see §11)
├── TASK_LEDGER.md               ← worktree coordination, see §10.3
├── .env.example
├── .gitignore                   ← data/doctrine/raw, data/memory.db, data/runs, .env
├── src/
│   ├── __init__.py
│   ├── pipeline/
│   │   ├── orchestrator.py
│   │   ├── modal_ensemble.py
│   │   ├── convergence.py
│   │   ├── adversarial.py
│   │   └── judging.py
│   ├── agents/
│   │   ├── base.py              ← GenerativeAgent base class
│   │   ├── convergence_cartographer.py
│   │   ├── off_distribution_generator.py
│   │   └── judge_pool.py
│   ├── memory/
│   │   ├── store.py             ← MemoryStore: SQLite-backed CRUD
│   │   ├── retrieval.py         ← scoring + min-max normalization
│   │   └── schema.sql
│   ├── doctrine/
│   │   ├── index.py              ← walks data/doctrine/passages/, parses frontmatter
│   │   └── retrieve.py           ← two-pass retrieval (keyword/topic + LLM router fallback)
│   ├── llm/
│   │   ├── wrapper.py           ← logged_completion()
│   │   └── manifest.py
│   ├── prompts/
│   │   ├── modal_red.md
│   │   ├── convergence_summary.md
│   │   ├── off_distribution.md
│   │   ├── judge_plausibility.md
│   │   ├── judge_off_dist_check.md
│   │   ├── reflection_questions.md
│   │   ├── reflection_insights.md
│   │   ├── importance_score.md
│   │   └── agent_summary.md
│   └── ui/
│       └── streamlit_app.py
├── scenarios/
│   ├── taiwan_strait_spring_2028.yaml
│   └── israel_me_cascade_2026.yaml
├── data/
│   ├── doctrine/
│   │   ├── raw/                 ← .gitignored, source PDFs
│   │   └── passages/            ← TRACKED. Curated markdown corpus, one passage per file.
│   │       ├── SCHEMA.md
│   │       ├── jp3-0/*.md
│   │       ├── jp5-0/*.md
│   │       ├── pla/*.md
│   │       └── csis/*.md
│   ├── memory.db                ← .gitignored
│   └── runs/{run_id}/
│       ├── manifest.json
│       ├── modal_moves.json
│       ├── convergence.md
│       ├── candidates.json
│       ├── judgments.json
│       └── menu.md
├── _context/
│   └── agent-output/            ← research-agent deliverables (this repo: under _context/, not top-level)
│       ├── README.md
│       ├── ra1-pla-doctrine.md
│       ├── ra2-jp-3-0-5-0.md
│       ├── ra3-pla-off-dist-corpus.md
│       ├── ra4-me-cascade-corpus.md
│       ├── ra5-yuna-wong-register.md
│       ├── ra6-cross-family-api.md
│       ├── ra7-chroma-rag.md
│       └── ra8-multi-agent-frameworks.md
└── tests/
    ├── test_memory_retrieval.py
    ├── test_logged_completion.py
    └── test_pipeline_dry_run.py
```

> **Note on layout deviations from the spec as originally drafted.** Two paths differ from the original §8 in this concrete repo: (1) `agent-output/` lives at `_context/agent-output/` (Madeleine's existing convention, pre-staged), and (2) the repo root is `mw-scsp/`, not `adversarial-redteam/`.

---

## 9. Logging and audit

Every LLM call goes through `src/llm/wrapper.py::logged_completion()`. The wrapper:

1. Hashes (system + user) prompts → `prompt_hash`
2. Reads the git hash of the prompt file at call time → `prompt_version`
3. Awaits the LLM call via litellm
4. Records: full prompt, full response, model + params, parsed output, tokens, latency, cost, run_id, stage, agent_id
5. Writes a row to `llm_calls`
6. Enforces the per-run cost cap; raises if exceeded

Every run also produces `data/runs/{run_id}/manifest.json` with the scenario, the pipeline config, the prompt file hashes, and pointers to all artifacts. A reviewer should be able to take a `run_id` and reconstruct exactly what the system did.

The Streamlit UI surfaces the audit trail as collapsible "show your work" panels for each stage. This is the technical-difficulty payoff during the demo.

---

## 10. Worktree parallelization plan

### 10.1 Setup

```bash
# from main repo root, after initial commit on main
git worktree add ../mw-scsp-memory   feature/memory
git worktree add ../mw-scsp-doctrine feature/doctrine
git worktree add ../mw-scsp-pipeline feature/pipeline
git worktree add ../mw-scsp-ui       feature/ui
```

You'll have 5 directories total: the main worktree (`mw-scsp/` on `main`) and four feature worktrees, each on its own branch. Open one Claude Code instance per worktree, in separate terminals. Paste the relevant `worktree-prompts/<branch>.md` as that instance's first message.

### 10.2 Branch / merge strategy

Solo work, fast iteration: squash-merge feature branches to main as each tier completes. Keep main always-buildable. Don't rebase shared branches mid-tier — squash at the end of each tier instead.

### 10.3 The TASK_LEDGER.md pattern

The main worktree contains `TASK_LEDGER.md`, which every Claude Code instance reads on startup. Update it by hand at tier boundaries. Each Claude Code instance is told in its initial prompt to read TASK_LEDGER.md before making changes. Lightweight, but prevents the worst foot-shooting.

### 10.4 Tiered build plan

**Tier 0 — Sequential, main worktree only, ~1 hour.** Repo skeleton, pyproject.toml, .env.example, SQLite schema, logged_completion wrapper, prompt file stubs, .gitignore. **Ship this to main before opening other worktrees.** Everything downstream depends on it.

**Tier 1 — Parallel, ~3 hours.**
- `feature/memory`: MemoryStore class, GenerativeAgent base, Cartographer skeleton (no reflection yet, just observation + retrieval), unit tests for retrieval scoring.
- `feature/doctrine`: pydantic schema for passage frontmatter, `index.py` loader (walk + validate), two-pass `retrieve.py`, author 20–30 representative passages from RA-2 (JP 3-0/5-0) and RA-1 (PLA), smoke test retrieval. **No Chroma, no embeddings** — see §5.
- `feature/pipeline`: `modal_ensemble.py` with cross-family async fan-out, `convergence.py` skeleton (clustering only, prompt comes from Cartographer in Tier 2), end-to-end dry-run scenario → 8 modal moves → cluster.
- `feature/ui`: idle, or scaffold the Streamlit shell with mocked data.

Squash-merge to main at end of Tier 1.

**Tier 2 — Parallel, ~3 hours.**
- `feature/memory`: Off-Distribution Generator agent, reflection module, judge pool with calibration memory.
- `feature/pipeline`: `adversarial.py`, `judging.py`, full pipeline run on Taiwan scenario.
- `feature/ui`: Streamlit demo flow per §13.
- `feature/doctrine`: prompt iteration on modal_red.md grounded in real retrieval; iterate convergence_summary.md.

Squash-merge to main at end of Tier 2.

**Tier 3 — Sequential, main worktree, ~2 hours.** Integration test, run on both scenarios, populate persistent memory across runs, demo dry-run, README, GitHub push.

### 10.5 Files where worktrees might collide

Coordinate via TASK_LEDGER:
- `src/llm/wrapper.py` — owned by main after Tier 0; treat as read-only in feature worktrees.
- `src/memory/schema.sql` — owned by `feature/memory`; pipeline requests new tables via TASK_LEDGER.
- `pyproject.toml` — additive only; conflicts on dependency adds are easy to resolve.
- `src/prompts/*.md` — additive is fine; edits to existing prompts coordinate via TASK_LEDGER.

Independent: anything under `src/agents/`, `src/doctrine/`, `src/ui/`, `src/pipeline/{modal_ensemble,convergence,adversarial,judging}.py`, individual prompt files, scenario YAMLs.

---

## 11. Research-agent prompts

Eight parallel research agents run in their own terminals or chat windows. Each writes its output to `_context/agent-output/raN-{slug}.md`. The main Claude Code instance reads from that folder when iterating on prompts and YAMLs.

The full prompts are in `RESEARCH_PROMPTS.md`. Copy each one into a separate Claude.ai chat or claude-code subagent. They are designed to run independently and do not require coordination.

---

## 12. The two scenario stubs

See `scenarios/taiwan_strait_spring_2028.yaml` and `scenarios/israel_me_cascade_2026.yaml` (the latter marked WIP pending RA-4).

---

## 13. Demo strategy (5 minutes, Sunday afternoon)

The full pipeline takes 5–10 minutes and ~70 LLM calls. **Do not run it live during the demo.** The Streamlit app replays a pre-computed run with full audit trail visible, plus a "live re-run one stage" button for credibility.

### 13.1 Pre-demo prep (Sunday morning)

1. Validate doctrine passage corpus: `uv run python -m src.doctrine.index --validate` should load and validate every passage; verify retrieval works on test queries.
2. Run pipeline on Taiwan scenario. Inspect menu manually. If no move feels interesting, iterate prompts. Budget 3 hours.
3. Run on Israel scenario (after RA-4 has populated it). Capture cross-run convergence-pattern reflection in the Cartographer's memory. **This is the moment that sells the architecture in the demo.**
4. Pre-run 2–3 additional scenario variants (e.g., Korean Peninsula, Russia/Baltic gray-zone) to give the Cartographer's memory more substance.

### 13.2 Demo flow

**0:00 — Hook (30s).** "Most LLM red-team systems fail in the same way: fluent, plausible, predictable adversary behavior. We built the system that searches the gap between plausible and predictable — and that accumulates what it learns across runs."

**0:30 — Scenario (30s).** Streamlit loads the Taiwan YAML.

**1:00 — Modal ensemble (1m).** 8 modal moves shown side by side. Embedding-cluster visualization. Doctrine each move cited. Land the point: *coherent, plausible, clustered. This is the failure mode.*

**2:00 — Convergence + absences (1m).** The Cartographer's output. Highlight "notable absences." **Highlight the cross-run reflection** — *"this convergence pattern also appeared in our Russia/Baltic and Korean Peninsula runs, suggesting it's a model-wide blind spot, not scenario-specific."* This is the moment.

**3:00 — Menu (1.5m).** Surviving off-distribution moves. Expand audit trail on one: prompt → 5 judge ratings → judge rationales → which convergence pattern it violates. **This is the technical-difficulty payoff.**

**4:30 — Honest close (30s).** "This is not a forecast. This is a menu of hypotheses for a human red team to evaluate. The system tells you what it is, every time. That's the discipline AI red-teaming needs."

---

## 14. README requirements

Per SCSP submission rules, the GitHub README must include:

- Team name, track (Wargaming), location (Boston)
- One-paragraph summary
- Datasets / APIs (Joint Chiefs Doctrine Library, CSIS Analysis Library, Anthropic API, OpenAI API)
- How to run: `uv sync; cp .env.example .env; uv run python -m src.doctrine.index --validate; uv run streamlit run src/ui/streamlit_app.py`
- Honest limitations section. This is part of the pitch.

---

## 15. Definition of done

Streamlit app that:

1. Replays a pre-computed run with full audit trail visible.
2. Demonstrates persistent memory: the Cartographer references at least one cross-run pattern.
3. Surfaces at least one off-distribution move on the Taiwan menu that a thoughtful person says "huh, that's interesting" about.
4. Re-runs the off-distribution stage live on demand.
5. Clean, version-controlled GitHub repo with the README above.

That's the bar. Not "we built an autonomous wargame." *We built a system that surfaces what an averaged AI red team misses, accumulates that across runs, and shows its work.*

---

## 16. Bibliography (extends as RA outputs land)

- Park, J.S., O'Brien, J.C., Cai, C.J., Morris, M.R., Liang, P., Bernstein, M.S. (2023). *Generative Agents: Interactive Simulacra of Human Behavior.* UIST '23. arXiv:2304.03442. [Memory stream architecture, retrieval scoring, reflection mechanism.]
- Wong, Y. et al. (RAND). Wargaming validation literature. [Expanded by RA-5.]
- Perla, P. *The Art of Wargaming.* [Foundational text.]
- Sabin, P. *Simulating War.*
- Joint Publication 3-0, *Joint Operations.* [Ingested into doctrine RAG.]
- Joint Publication 5-0, *Joint Planning.* [Ingested into doctrine RAG.]
- CSIS open-access wargaming and PLA analysis. [Selected by RA-1, RA-3.]

End of spec.
