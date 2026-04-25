# Tier 1 brief — `feature/doctrine` worktree

You are working in the `feature/doctrine` worktree of the Adversarial-Distribution Red Team project (SCSP Hackathon 2026, Wargaming track, Boston). Three other Claude Code instances are working in parallel. Coordinate via `TASK_LEDGER.md`.

## Read first

1. `PROJECT_SPEC.md` — section §5 (doctrine RAG) is your spec. Skim §3 and §6 for context.
2. `TASK_LEDGER.md` — file ownership and current blockers.
3. `_context/agent-output/ra2-jp-3-0-5-0.md` (when it lands) — section reading guide for JP 3-0 / 5-0.
4. `_context/agent-output/ra1-pla-doctrine.md` (when it lands) — CSIS/RAND PLA Taiwan corpus.
5. `_context/agent-output/ra7-chroma-rag.md` (when it lands) — current ChromaDB API and embedding-model recommendation. **Defer to this for any API specifics; the spec is older.**

## What you own

- `src/doctrine/ingest.py`
- `src/doctrine/retrieve.py`
- `data/doctrine/raw/` — drop PDFs here. Already `.gitignored`.
- `data/chroma/` — local persistent index. Already `.gitignored`.

## What is read-only for you

- `src/llm/wrapper.py`, `src/llm/manifest.py` — owned by `main`.
- `src/memory/`, `src/agents/`, `src/pipeline/`, `src/ui/` — other worktrees.

`pyproject.toml` is additive-only; if you need a dep, add it and note it in TASK_LEDGER.

## Tier 1 deliverables

1. **`src/doctrine/ingest.py`**:
   - Walks `data/doctrine/raw/*.pdf`.
   - For each PDF: extract text per page (use `pypdf`), feed into `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)` from `langchain_text_splitters`.
   - Each chunk gets metadata: `passage_id` (stable id, e.g. `<doc_slug>:<page>:<chunk_idx>`), `doc_title`, `page`, `chunk_index`.
   - Embed via `sentence-transformers` `BAAI/bge-base-en-v1.5` (or whatever RA-7 currently recommends — confirm in the agent-output before locking in).
   - Persist to ChromaDB at `data/chroma/` using a single named collection `doctrine`.
   - Idempotent re-runs: skip docs whose `(doc_title, page, chunk_index)` already in the collection (use `.get(ids=...)`).
   - `if __name__ == "__main__":` runs ingest with progress to stdout.

2. **`src/doctrine/retrieve.py::retrieve(query, top_k=6) -> list[dict]`**:
   - Lazy-load the embedding model and Chroma client at module level (singleton).
   - Embed `query`, call `collection.query(query_embeddings=..., n_results=top_k, include=["documents","metadatas","distances"])`.
   - Return `[{passage_id, doc_title, page, chunk_index, text, score}]` where `score = 1 - distance` (or whatever maps cleanly to "higher is better"; document your choice).

3. **Smoke test**:
   - Drop 2–3 JCS PDFs into `data/doctrine/raw/` (Joint Publication 3-0, Joint Publication 5-0; CSIS PLA brief if available).
   - Run `uv run python -m src.doctrine.ingest`. Verify it reports number of chunks ingested.
   - Run a small Python snippet (committed as `tests/test_doctrine_smoke.py` or just an inline check) querying for "adversary course of action development" and verify the top result is from JP 5-0.

4. **Tier 2 prep (do not block Tier 1 on this)**: take notes on which retrieval queries return useful Red-side passages vs. which return Blue-side passages. The modal_red.md prompt iteration in Tier 2 will use these notes.

## Definition of done

- `uv run python -m src.doctrine.ingest` runs cleanly and creates `data/chroma/`.
- `uv run python -c "from src.doctrine.retrieve import retrieve; print(retrieve('amphibious operations', top_k=3))"` returns 3 sensible passages.
- Notes added to `TASK_LEDGER.md` if Red/Blue partition turned out tricky.

## What NOT to do in Tier 1

- No Streamlit visualization of retrieval — that's Tier 2 / `feature/ui`.
- No re-implementation of `logged_completion` for embedding-model calls. Embedding calls are local (sentence-transformers), they don't need audit logging.
- No edits outside your owned files.

When you finish, commit with a clear message and push the branch.
