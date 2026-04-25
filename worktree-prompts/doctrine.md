# Tier 1 brief — `feature/doctrine` worktree

You are working in the `feature/doctrine` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

## Read first

1. `PROJECT_SPEC.md` §5 (doctrine markdown corpus, **not RAG**) is your spec. Read §3 and §6 for context.
2. `data/doctrine/passages/SCHEMA.md` — frontmatter schema, controlled vocabulary, retrieval contract. **Authoritative.**
3. `TASK_LEDGER.md` — file ownership and current blockers.
4. `_context/agent-output/ra1-pla-doctrine.md` — PLA Taiwan source list. The passages you author are *distillations* of the cited material, not literal scrapes.
5. `_context/agent-output/ra2-jp-3-0-5-0.md` — JP 3-0 / 5-0 section guide. Direct quotes are usable.
6. `_context/agent-output/ra3-pla-off-dist-corpus.md` — Concepts the modal LLM under-weights. Drives `applies-to: off-distribution-flag` passages.
7. `_context/agent-output/ra4-me-cascade-corpus.md` — Israel/ME source list, for the second scenario's passages.
8. The 9 sample passages already on `main` under `data/doctrine/passages/`. Match their style.

## What you own

- `src/doctrine/index.py` (Tier 0 ships full loader + validator; you may extend, e.g. add embedding-free `summarize_corpus()` for the Streamlit "audit" tab if helpful).
- `src/doctrine/retrieve.py` (Tier 0 ships two-pass retrieval; you may iterate on scoring weights or tokenization, but keep the function signature stable).
- **Author 20–30 new passages** under `data/doctrine/passages/{jp3-0,jp5-0,pla,me,csis}/*.md`. Quality > count — every passage must validate, must have non-trivial body, must be retrievable on a query a Red planner would actually ask.

## What is read-only for you

- `src/llm/wrapper.py`, `src/llm/manifest.py` — owned by `main`.
- `src/memory/`, `src/agents/`, `src/pipeline/`, `src/ui/` — other worktrees.
- `data/doctrine/passages/SCHEMA.md` — schema is settled. Propose changes via `TASK_LEDGER.md` open-questions; do not edit.

`pyproject.toml` is additive-only; if you need a new dep, add it and note in TASK_LEDGER.

## Tier 1 deliverables

1. **Author the JP 3-0 corpus.** Target ~6 passages from RA-2's section list:
   - `jp3-0-phasing-model.md` (the six-phase model + competition continuum reframe)
   - `jp3-0-branches-sequels.md`
   - `jp3-0-operational-design-elements.md` (the seventeen)
   - `jp3-0-termination.md`
   - `jp3-0-lines-of-operations.md`
   - one of your choice from RA-2's "Why this matters" set

2. **Author the JP 5-0 corpus.** Target ~5 passages:
   - `jp5-0-jpp-overview.md` (the seven steps)
   - `jp5-0-mission-analysis.md`
   - `jp5-0-coa-comparison.md`
   - `jp5-0-risk-assessment.md`
   - `jp5-0-most-probable-most-dangerous.md` (call out how this passage is what the system is reacting against — high `priority`, `applies-to: off-distribution-flag`)

3. **Author the PLA corpus.** Target ~8 passages from RA-1:
   - `pla/quarantine-vs-blockade.md` (CSIS Bonny Lin et al.)
   - `pla/joint-island-landing-campaign.md` (the three-phase doctrine)
   - `pla/decapitation.md`
   - `pla/outlying-island-seizure.md` (Kinmen, Matsu, Dongsha)
   - `pla/gray-zone-coercion.md` (CSIS "Signals in the Swarm")
   - `pla/active-defense.md` (PLA historical doctrine; off-distribution-flag)
   - `pla/volt-typhoon-class.md` (off-distribution-flag; civilian-infra pre-positioning)
   - one PLAAF or Rocket Force technical anchor

4. **Author the ME corpus.** Target ~5 passages from RA-4 / RA-3:
   - `me/iran-april-2024-strike.md` (model anchor; will be over-cited)
   - `me/iran-october-2024-strike.md` (model anchor)
   - `me/tower-22-precedent.md` (attribution / coordination friction)
   - `me/houthi-bab-al-mandeb.md`
   - one off-distribution Cluster B move from RA-4 (e.g., `me/lawfare-instrumental.md` or `me/insurance-market-vector.md`)

5. **Smoke tests.** Add `tests/test_doctrine_index.py`:
   - `load_index()` succeeds without warnings.
   - `retrieve_sync('amphibious operations', 'modal-grounding', 3)` returns at least one PLA passage.
   - `retrieve_sync('the staff should reject this course of action', 'judge-rubric', 3)` returns `jp5-0-coa-screening` first.
   - Every authored passage's id is referenced from at least one other passage's `related` list (catches orphan passages).

6. **TASK_LEDGER notes** on prompt-iteration findings: which queries return useful passages vs. which return Blue-side noise. The pipeline worktree iterates `modal_red.md` against your retrieval; flagging quirks here saves them time.

## Authoring rules (from SCHEMA.md, restated)

- One concept per file. Body under ~500 lines.
- Cite source/edition/page exactly. Use blockquote markdown for verbatim quotes.
- Lowercase, stem-trimmed keywords. Generous synonyms but not promiscuous.
- Stable ids — they're the citation token in `modal_moves.doctrine_cited`.
- Run `uv run python -m src.doctrine.index --validate` before committing.
- The off-distribution generator (Stage 4) does NOT call `retrieve()`. No passage should be authored *for* that stage; an `applies-to: off-distribution-flag` passage is for the Stage 5 judges and the Cartographer to *recognize* off-distribution moves, not to seed them.

## Definition of done

- `uv run python -m src.doctrine.index --validate` exits 0.
- ≥ 25 passages on disk; every required `applies-to` stage has ≥ 3 passages.
- `uv run pytest tests/test_doctrine_index.py` — all green.
- A short note added to `TASK_LEDGER.md` open-questions listing any retrieval-quality issues you saw.

## What NOT to do in Tier 1

- No embeddings. No ChromaDB. No PDF chunking. The pivot to markdown corpus is settled (PROJECT_SPEC.md §5).
- No edits to `src/llm/wrapper.py`, `src/memory/`, `src/agents/`, `src/pipeline/`, `src/ui/`.
- No passages authored *for* the off-distribution generator. That stage is intentionally ungrounded.

When you finish, commit with a clear message and push the branch. The main worktree will squash-merge.
