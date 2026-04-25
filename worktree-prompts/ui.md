# Tier 2 brief — `feature/ui` worktree

You are working in the `feature/ui` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

Tier 1 shipped: `src/ui/{streamlit_app,streamlit_proto,fixtures,scenarios_loader}.py`. The 5-section shell is wired against mocked data. Tier 2 swaps the mocks for real reads from `data/runs/{run_id}/` and `data/memory.db`.

## Read first

1. `PROJECT_SPEC.md` §13 (demo flow, especially §13.2's per-section timing) and §15 (definition of done).
2. `TASK_LEDGER.md` — Tier 1 follow-ups, especially the mock-shape gaps (`MOCK_MODAL_MOVES` missing `actions` and `move_id`; `MOCK_CONVERGENCE` uses `cluster_labels` instead of the spec's `clusters`).
3. `src/ui/streamlit_app.py` — the Tier 1 5-section app. Yours to extend.
4. `src/ui/streamlit_proto.py` — the alternative menu-first instrument-panel design. Decide which is the demo (you can keep both, but flag the canonical one).
5. `src/ui/fixtures.py` — the mocks to retire.
6. `data/runs/f2b0eb4c-6306-4876-b4db-46466b7c186e/{manifest,modal_moves,clusters}.json` — actual Tier-1 output, the canonical shape for what Section 5 reads.
7. `src/pipeline/schemas.py::ModalMoveSchema` — the real shape modal moves take.
8. `src/agents/convergence_cartographer.py::ConvergenceNarration` — the shape Stage-3 output takes.

## What you own

- `src/ui/*.py` — streamlit_app, streamlit_proto, fixtures, scenarios_loader, plus any new helpers you need.

## What is read-only for you

- All other directories.
- `pyproject.toml` is additive-only.

## Tier 2 deliverables

### 1. Real-data adapter layer

New module `src/ui/run_loader.py`:

```python
def list_runs() -> list[dict]:
    """Returns [{run_id, scenario_id, started_at, completed_at, status, total_cost}] sorted desc."""

def load_run(run_id: str) -> dict:
    """Returns {manifest, modal_moves, convergence, candidates, judgments, menu, llm_calls}.

    Each value is parsed JSON / markdown ready for the UI. Falls back to the corresponding
    mock fixture if the artifact is missing — useful during Tier 2 development when not
    every stage has run.
    """
```

Reads `data/runs/{run_id}/manifest.json`, `modal_moves.json`, `clusters.json`, `candidates.json`, `judgments.json`, `convergence.md`, `menu.md`, plus a query against `data/memory.db` for `llm_calls WHERE run_id=?`.

### 2. Wire all five sections to real data

For each section, replace the `MOCK_*` import with `run_loader.load_run(selected_run_id)`. Specifically:

- **Section 1 (Scenario):** unchanged — already loads from `scenarios/*.yaml`.
- **Section 2 (Modal ensemble):** read `modal_moves.json`. `actions`, `intended_effect`, `risks_red_accepts` now appear on each card. The 4-wide grid stays; consider an "expand" affordance per card to show the full move JSON.
- **Section 3 (Convergence):** read `clusters.json` for the structured `clusters` and `notable_absences`, `convergence.md` for the prose. The cross-run callout (`cross_run_observations`) is the demo's hero moment — render it distinctly even when empty (e.g., "No cross-run patterns yet — populate by running the same scenario family multiple times").
- **Section 4 (Menu):** read `judgments.json` and `candidates.json`. Per surviving proposal: collapsed by default, expand to show the 5 judge ratings (dots), each judge's rationale, and `which_convergence_pattern_it_breaks`. Non-surviving proposals visible behind a toggle.
- **Section 5 (Audit):** read `manifest.json` + the `llm_calls` SQL query. Filter by stage (modal_ensemble / 3_convergence / off_distribution / judging). Show prompt_hash + prompt_version per call; clicking a call expands to show the full system + user prompt + raw response.

### 3. Live "re-run one stage" button

Section 4 has a stub button. Wire it to actually re-run Stage 4 (off-distribution generation) against the currently-loaded run's Stage 3 output. Implementation:

```python
if st.button("Re-run off-distribution stage", help="..."):
    from src.pipeline.adversarial import generate_off_distribution
    proposals = asyncio.run(generate_off_distribution(
        convergence_summary=run["convergence"],
        scenario=run["scenario"],
        run_id=f"{base_run_id}_rerun_{int(time.time())}",
    ))
    # display the new proposals alongside the original menu
```

This is the highest-leverage demo move per §13. Costs ~$0.30, takes ~20 seconds. Show a spinner.

### 4. Run picker

Replace the implicit "load mock data" with a sidebar dropdown of `list_runs()` showing run_id + scenario + cost + status. Default to the most recent complete run on the canonical scenario.

### 5. Mock cleanup

Decide: keep `fixtures.py` as a fallback for development-mode (no runs on disk yet) OR delete it. If keeping, update the shapes:
- `MOCK_MODAL_MOVES`: add `actions` (list of `{actor, action, target, timeline_days, purpose}`), `intended_effect`, `risks_red_accepts`, `move_id`.
- `MOCK_CONVERGENCE`: rename `cluster_labels` → `clusters` and reshape per `ConvergenceNarration` (each cluster has `cluster_id`, `theme`, `member_move_ids`, `representative_actions`).

### 6. streamlit_app vs streamlit_proto

Pick one as the demo. Keep the other in the repo as `streamlit_proto.py` (already named that way) with a header comment naming it the alternative. The demo per §13 expects the 5-section flow in `streamlit_app.py` — default to that unless `streamlit_proto.py` lands a clearly better register.

## Definition of done

- `uv run streamlit run src/ui/streamlit_app.py` opens, picks the latest complete run, renders all 5 sections from real data with no mock fallback.
- The "re-run off-distribution" button runs the real Stage 4 against the loaded run, returns proposals, and displays them.
- Section 5 audit shows actual `llm_calls` rows from `data/memory.db`.
- TASK_LEDGER updated with anything you found in the real-vs-mock data shapes.

## What NOT to do

- No edits outside `src/ui/`.
- No new top-level deps.
- No re-running of Stage 1 or Stage 2 from the UI — the live button only re-runs Stage 4 (cheap, off-distribution, demo-relevant).

When you finish, commit with a clear message and push the branch.
