# Worktree initial prompts

Paste the matching file's content as the **first message** to the Claude Code instance you open in each worktree. Each prompt is self-contained — it tells the agent which files it owns, which files are read-only, and its Tier deliverables.

## Tier 2 setup

```bash
# from the main worktree, after Tier 1 has been squash-merged to main:
git -C /Users/madeleinewoods/Development/mw-scsp worktree add ../mw-scsp-memory   -b feature/memory
git -C /Users/madeleinewoods/Development/mw-scsp worktree add ../mw-scsp-doctrine -b feature/doctrine
git -C /Users/madeleinewoods/Development/mw-scsp worktree add ../mw-scsp-pipeline -b feature/pipeline
git -C /Users/madeleinewoods/Development/mw-scsp worktree add ../mw-scsp-ui       -b feature/ui
```

Then open one Claude Code instance per directory and paste the corresponding prompt as your first message:

| Worktree | Prompt file | What it builds in Tier 2 |
|---|---|---|
| `mw-scsp-memory` (`feature/memory`) | `memory.md` | `OffDistributionGenerator`, `JudgePool`, reflection module, agent_summary regenerator |
| `mw-scsp-doctrine` (`feature/doctrine`) | `doctrine.md` | Prompt iteration against real Tier-1 retrievals + Tier-2 outputs; topic-vocab lock decision |
| `mw-scsp-pipeline` (`feature/pipeline`) | `pipeline.md` | `adversarial.py` + `judging.py` + Stage-3 narration wire-up + full pipeline run on both scenarios |
| `mw-scsp-ui` (`feature/ui`) | `ui.md` | Swap mocks for real reads; live "re-run Stage 4" button; run picker |

Quick clipboard helper on macOS: `cat worktree-prompts/<name>.md | pbcopy`, then ⌘V into the new Claude Code session.

## Stream priority (if working serially rather than parallel)

1. **memory** — `OffDistributionGenerator` and `JudgePool` are the dependency for pipeline Stages 4/5. Highest leverage.
2. **pipeline** — once memory's agents are interface-stable, pipeline can wire Stages 3/4/5 and produce the artifacts the UI reads.
3. **ui** — needs real artifacts on disk; cleanest done after pipeline.
4. **doctrine** — prompt iteration. Can start the moment any real Tier-2 output lands; mostly content work.

## After each tier

Squash-merge to main from the main worktree:

```bash
cd /Users/madeleinewoods/Development/mw-scsp
git merge --squash feature/memory && git commit -m "Tier 2 feature/memory: ..."
git merge --squash feature/doctrine && git commit -m "Tier 2 feature/doctrine: ..."
git merge --squash feature/pipeline && git commit -m "Tier 2 feature/pipeline: ..."
git merge --squash feature/ui && git commit -m "Tier 2 feature/ui: ..."
```

Watch for `TASK_LEDGER.md` conflicts at the bottom of the file; resolution is usually preserving both halves and reordering by stream.

See `PROJECT_SPEC.md` §10 for the full worktree spec.
