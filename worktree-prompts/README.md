# Worktree initial prompts

Paste the matching file's content as the **first message** to the Claude Code instance you open in each worktree. Each prompt is self-contained — it tells the agent which files it owns, which files are read-only, and what its Tier 1 deliverables are.

## Setup recap

```bash
# from this main worktree, after Tier 0 is committed to main:
git worktree add ../mw-scsp-memory   feature/memory
git worktree add ../mw-scsp-doctrine feature/doctrine
git worktree add ../mw-scsp-pipeline feature/pipeline
git worktree add ../mw-scsp-ui       feature/ui
```

Then open one Claude Code instance per directory, paste the corresponding prompt below.

| Worktree | Prompt file | What it builds in Tier 1 |
|---|---|---|
| `mw-scsp-memory` (`feature/memory`) | `memory.md` | `MemoryStore`, `GenerativeAgent` base, Cartographer skeleton, retrieval tests |
| `mw-scsp-doctrine` (`feature/doctrine`) | `doctrine.md` | Chroma ingest + retrieve, ingested 2–3 JCS PDFs, smoke test |
| `mw-scsp-pipeline` (`feature/pipeline`) | `pipeline.md` | `modal_ensemble.py` async fan-out, `convergence.py` clustering, dry-run |
| `mw-scsp-ui` (`feature/ui`) | `ui.md` | Streamlit shell with mocked data (Tier 1 optional) |

After each tier, squash-merge to main from this worktree. See `PROJECT_SPEC.md` §10.
