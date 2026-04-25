# Agent output

Outputs from the eight parallel research agents defined in `/RESEARCH_PROMPTS.md`. Each file is a self-contained deliverable from one agent.

| File | Topic | Used by |
|---|---|---|
| `ra1-pla-doctrine.md` | CSIS / RAND / IISS PLA Taiwan operational concepts | Tier 1 doctrine ingest, modal_red prompt iteration |
| `ra2-jp-3-0-5-0.md` | Joint Publication 3-0 / 5-0 section reading guide | Tier 1 doctrine ingest |
| `ra3-pla-off-dist-corpus.md` | Off-distribution PLA concepts (cognitive, third-front, fragmentation) | Tier 2 off_distribution prompt iteration |
| `ra4-me-cascade-corpus.md` | Middle East cascade scenario population | `scenarios/israel_me_cascade_2026.yaml` |
| `ra5-yuna-wong-register.md` | Validation literature, register calibration | Demo script, README, prompt language |
| `ra6-cross-family-api.md` | Current model ids, pricing, structured-output | `.env.example`, `pyproject.toml`, cost cap config |
| `ra7-chroma-rag.md` | Working ChromaDB / sentence-transformers config | `src/doctrine/ingest.py`, `src/doctrine/retrieve.py` |
| `ra8-multi-agent-frameworks.md` | Framework survey (justify rolling our own) | Tier 1 architecture sanity-check |

Read these before iterating prompts in `src/prompts/` or scenario YAMLs. Treat as authoritative for the topics they cover; flag disagreements in `TASK_LEDGER.md` rather than silently overriding.
