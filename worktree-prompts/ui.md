# Tier 1 brief — `feature/ui` worktree

You are working in the `feature/ui` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

## Read first

1. `PROJECT_SPEC.md` — sections §13 (demo strategy) and §15 (definition of done). The UI exists to make Tier 3 land in 5 minutes.
2. `TASK_LEDGER.md`.
3. `_context/agent-output/ra5-yuna-wong-register.md` (when it lands) — language to use and language to avoid in user-facing strings.

## What you own

- `src/ui/streamlit_app.py`
- Anything new under `src/ui/` (helpers, components).

## What is read-only for you

- All other directories under `src/`.
- `pyproject.toml` is additive-only.

## Tier 1 status

This worktree is **optional in Tier 1**. The pipeline's data shapes will solidify only at the end of Tier 1 (modal moves, cluster output) and then again at the end of Tier 2 (off-distribution proposals, judgments). Building the real UI before then risks rework.

Tier 1 deliverable, if you choose to build it now: a **Streamlit shell with mocked data** that locks in the demo's information architecture. The shell becomes real in Tier 2 by replacing the mocks with reads from `data/runs/{run_id}/*.json`.

## Tier 1 deliverables (optional)

1. **Demo information architecture as a single Streamlit page** with collapsible sections in the order the demo runs (PROJECT_SPEC.md §13.2):
   - Header: project title, "SCSP Hackathon 2026 · Wargaming · Boston," and a one-line disclaimer ("This is a menu of hypotheses, not a forecast.").
   - **Section 1 — Scenario.** Reads `scenarios/*.yaml`, displays the selected scenario as a clean panel. Dropdown to switch scenarios.
   - **Section 2 — Modal Ensemble.** 8 cards laid out 4-wide, 2-deep. Each card: provider, model, temperature, move_title, summary, doctrine_cited as small chips. Mock data for now.
   - **Section 3 — Convergence + Absences.** Cluster visualization (Plotly scatter of 2D-projected embeddings, color = cluster). Below: `convergence_summary` text, `notable_absences` as a list, and a callout box for `cross_run_observations` (this is the moment in §13.2; visually distinct).
   - **Section 4 — Menu.** A list of surviving off-distribution proposals. Each row is collapsible to reveal: judge ratings as a small bar (5 dots colored by rating), each judge's `rationale`, and `which_convergence_pattern_it_breaks`.
   - **Section 5 — Audit.** Picks a `run_id` from `data/runs/`, shows the `manifest.json`, prompt versions, total cost, and a search box over `llm_calls`.

2. **Mock data fixtures** in `src/ui/fixtures.py` — Python dicts shaped like the eventual schemas. Documented with `# TIER 2: replace with read from data/runs/{run_id}/`.

3. **A "live re-run one stage" button** stub on Section 4 — disabled in Tier 1, with a tooltip explaining it's wired up in Tier 2. This is the credibility move in the demo (§13).

## Definition of done

- `uv run streamlit run src/ui/streamlit_app.py` opens without errors.
- All five sections render with mock data.
- Visual hierarchy matches the demo flow in §13.2 — the cross-run reflection callout is unmistakable.

## What NOT to do in Tier 1

- No real pipeline calls. Mocks only.
- No Plotly cluster viz from real embeddings — use synthetic 2D points.
- No edits to `src/llm/`, `src/memory/`, `src/agents/`, `src/pipeline/`, `src/doctrine/`.

When you finish, commit with a clear message and push the branch. If you decide to skip Tier 1 entirely and start UI in Tier 2, leave `src/ui/streamlit_app.py` as the Tier-0 stub and note the choice in `TASK_LEDGER.md`.
