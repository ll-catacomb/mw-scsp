# Tier 2 brief — `feature/doctrine` worktree

You are working in the `feature/doctrine` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

Tier 1 shipped: `src/doctrine/{index,retrieve}.py`, 33 passages on disk validating clean (5 stages, 44 topics). Live smoke test on Taiwan exposed a real signal: all 8 modal moves cited the same 3 passages (`jp3-0-phasing-model`, `jp3-0-cog`, `pla-gray-zone-coercion`); zero cited the off-distribution-flag passages. Tier 2 is prompt-iteration and corpus tuning.

## Read first

1. `PROJECT_SPEC.md` §5 (markdown corpus) and §13 (demo flow).
2. `TASK_LEDGER.md` Tier 1 follow-ups, especially the doctrine retrieval-quality findings (cross-scenario topic bleed, incomplete stem trimming, pass-2 router fires more than expected).
3. `data/runs/f2b0eb4c-6306-4876-b4db-46466b7c186e/{modal_moves,manifest}.json` — the actual smoke-test output. **Read this first.** The convergence pattern (4×Dongsha, 4×quarantine) is the empirical anchor for prompt iteration.
4. `_context/agent-output/{ra1,ra2,ra3,ra5}-*.md` — corpus and register.
5. `data/doctrine/passages/SCHEMA.md` — settled.
6. `src/prompts/*.md` — the 9 stub prompts. Yours to iterate.

## What you own

- `src/prompts/*.md` — coordinate via TASK_LEDGER on edits to existing files (avoid concurrent edits with feature/memory or feature/pipeline if they need to touch the same file). You own the *content*; they own the *call sites*.
- `data/doctrine/passages/**/*.md` — corpus authoring continues if needed (RA-3 off-distribution corpus, CSIS subdirectory, missing passages surfaced by Stage-5 judges).
- `src/doctrine/{index,retrieve}.py` — minor iteration only (e.g., light stemming if retrieval-quality findings demand it).

## What is read-only for you

- `src/llm/`, `src/memory/`, `src/pipeline/`, `src/agents/`, `src/ui/` — other worktrees.
- `data/doctrine/passages/SCHEMA.md` — settled.

`pyproject.toml` is additive-only.

## Tier 2 deliverables

### 1. Iterate `src/prompts/modal_red.md`

Open `data/runs/f2b0eb4c-6306-4876-b4db-46466b7c186e/modal_moves.json`. Read all 8 moves. Specific findings to address in the prompt:

- **Citation flattening:** 8/8 moves cited exactly 3 passages (phasing-model + cog + gray-zone). Either retrieval is over-anchoring on those (high-priority + common keywords), or the prompt is implicitly biasing the model to default to gray-zone framings. Investigate both. Try: explicitly tell the model to cite ONLY passages it drew on (the prompt already says this — strengthen if needed); and check whether the doctrine-block ordering is biasing toward the first-listed passages.
- **Cluster narrowness:** 4 distinct titles for "Dongsha seizure" suggest the model is genuinely converging on that move at high temperature. This is the failure mode the system is built to expose, so it's a feature for Stage 3, not a bug. But: if the prompt's example phrasing or doctrine excerpts themselves seed this convergence, soften them.
- **`risks_red_accepts` quality:** check whether models actually populate this with substantive risk language vs. boilerplate. The Cartographer relies on this for "notable absences" framing.

Iterate, then re-run the modal stage on Taiwan. Cost ~$0.15. Compare convergence patterns before/after; **document in TASK_LEDGER**.

### 2. Iterate `src/prompts/convergence_summary.md`

This prompt drives the Cartographer's narration. After `feature/pipeline` lands the Stage-3 wire-up, iterate against the first 1–2 real Cartographer outputs. Specific things to tune:

- The `notable_absences` format — RA-5 register requires "specific" not "the ensemble underweights X" hand-waving. The prompt already says this; check whether outputs comply.
- Length: spec says 4–8 absences. Verify.
- Cross-run observations should appear blank on Run 1 (no prior reflections), populated on Run 3+ for the same scenario family.

### 3. Iterate `src/prompts/off_distribution.md`

Once `feature/memory` ships `OffDistributionGenerator` and `feature/pipeline` runs Stage 4 end-to-end, examine the K proposals. Specific signal to watch:

- The `which_convergence_pattern_it_breaks` field is the cleanest evidence of whether the generator escaped the gap. If proposals all break the *same* convergence pattern, the prompt isn't pushing hard enough.
- The `why_a_red_planner_could_justify_this` field separates plausible-but-novel from implausible-and-novel. Strengthen the rubric if proposals are pure provocation.

### 4. Iterate the two judge prompts

Calibration drift: if the 5 judges' median plausibility is consistently 4–5 across all proposals, plausibility isn't discriminating. If would-have-generated is True too often, the survival filter never fires. Tune temperature, examples, or rubric language.

### 5. Topic vocabulary lock decision

The Tier 1 doctrine pass added 24 passages without introducing new topics. If Tier 2 holds the line, consider making `--strict` the default in `index.py` (treat unknown topics as errors). One-line change in `main()`. Decide and document.

### 6. Optional: CSIS subdirectory

If RA-3 surfaces off-distribution PLA concepts not yet in the corpus, author them under `data/doctrine/passages/csis/` (or split out from `pla/`). Mark as `applies-to: off-distribution-flag` so Stage 5 judges and the Cartographer can recognize escape.

### 7. Optional: light stemming

The Tier-1 finding that `phase` doesn't match `phasing` and `transition` doesn't match `transitions` is real. A simple `re.sub(r'(ing|ion|ions|ed|s)$', '', token)` pass on both query tokens and stored keywords would close this without changing function signatures. Held off in Tier 1; pick up if retrieval misses become demo-blocking.

## Definition of done

- One full pipeline re-run on Taiwan after the modal_red iteration; document the change in convergence pattern.
- `convergence_summary.md` and `off_distribution.md` have been touched at least once based on real LLM output (not just spec-reading).
- Topic-vocabulary lock decided.
- TASK_LEDGER updated with prompt-iteration findings.

## What NOT to do

- No edits to `src/llm/wrapper.py`, `src/memory/`, `src/pipeline/`, `src/agents/`, `src/ui/`.
- No edits to `data/doctrine/passages/SCHEMA.md` (locked).
- No new doctrine passages authored *for* the off-distribution generator (Stage 4). It's doctrine-free by design. Passages tagged `applies-to: off-distribution-flag` are for Stage 5 judges and the Cartographer to *recognize* off-distribution moves, not to seed Stage 4.

When you finish, commit with a clear message and push the branch.
