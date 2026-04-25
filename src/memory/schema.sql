-- Adversarial-Distribution Red Team — SQLite schema.
-- See PROJECT_SPEC.md §7. Owned by feature/memory; pipeline requests new tables via TASK_LEDGER.

-- Master log of every LLM call.
CREATE TABLE IF NOT EXISTS llm_calls (
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
  prompt_version TEXT NOT NULL,        -- git blob hash of prompt file at call time
  input_tokens   INTEGER,
  output_tokens  INTEGER,
  latency_ms     INTEGER,
  cost_usd       REAL,
  timestamp      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS llm_calls_run_idx ON llm_calls(run_id);

CREATE TABLE IF NOT EXISTS runs (
  run_id        TEXT PRIMARY KEY,
  scenario_id   TEXT NOT NULL,
  started_at    TEXT NOT NULL,
  completed_at  TEXT,
  config_hash   TEXT NOT NULL,
  status        TEXT NOT NULL          -- 'running' | 'complete' | 'failed'
);

-- Generative-agents memory stream (Park et al. 2023, §4.1).
CREATE TABLE IF NOT EXISTS agent_memory (
  memory_id        TEXT PRIMARY KEY,
  agent_id         TEXT NOT NULL,
  memory_type      TEXT NOT NULL,      -- 'observation' | 'reflection'
  description      TEXT NOT NULL,
  embedding        BLOB NOT NULL,      -- numpy float32, .tobytes()
  importance       INTEGER NOT NULL,   -- 1-10
  created_at       TEXT NOT NULL,
  last_accessed_at TEXT NOT NULL,
  source_run_id    TEXT,
  cited_memory_ids TEXT                -- JSON array, for reflections
);
CREATE INDEX IF NOT EXISTS agent_memory_agent_idx ON agent_memory(agent_id);
CREATE INDEX IF NOT EXISTS agent_memory_run_idx   ON agent_memory(source_run_id);

-- Cached agent summaries (Park et al. Appendix A).
CREATE TABLE IF NOT EXISTS agent_summary (
  agent_id    TEXT NOT NULL,
  version     INTEGER NOT NULL,
  summary     TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  PRIMARY KEY (agent_id, version)
);

-- Stage tables.
CREATE TABLE IF NOT EXISTS modal_moves (
  move_id         TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL,
  instance_idx    INTEGER NOT NULL,    -- 0..7
  provider        TEXT NOT NULL,
  model           TEXT NOT NULL,
  temperature     REAL NOT NULL,
  move_json       TEXT NOT NULL,
  doctrine_cited  TEXT,                -- JSON array of passage_ids
  embedding       BLOB
);
CREATE INDEX IF NOT EXISTS modal_moves_run_idx ON modal_moves(run_id);

CREATE TABLE IF NOT EXISTS off_dist_proposals (
  proposal_id     TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL,
  move_json       TEXT NOT NULL,
  embedding       BLOB,
  surviving       INTEGER,
  median_plaus    REAL,
  would_gen_count INTEGER
);
CREATE INDEX IF NOT EXISTS off_dist_run_idx ON off_dist_proposals(run_id);

CREATE TABLE IF NOT EXISTS judgments (
  judgment_id     TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL,
  proposal_id     TEXT NOT NULL,
  judge_id        TEXT NOT NULL,
  plausibility    INTEGER NOT NULL,
  rationale       TEXT NOT NULL,
  would_have_gen  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS judgments_run_idx      ON judgments(run_id);
CREATE INDEX IF NOT EXISTS judgments_proposal_idx ON judgments(proposal_id);
