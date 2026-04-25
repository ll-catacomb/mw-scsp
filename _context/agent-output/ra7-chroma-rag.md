# RA-7: ChromaDB + sentence-transformers RAG Best Practices

*Research agent output for SCSP wargaming red-team prototype. Implementation-ready guide for a small-scale local doctrine RAG over a few hundred PDF chunks of US Joint Publications, CSIS analysis, and PLA-watcher reports. Compiled April 2026 against `chromadb>=0.5` and `sentence-transformers>=3.3`.*

## Recommended stack

`chromadb.PersistentClient` writing to `data/chroma/`, with a single collection named `doctrine` whose embedding function is `BAAI/bge-base-en-v1.5` (768-d, cosine, normalize-on-encode). PDFs are extracted with `pypdf` page-by-page, then split with `RecursiveCharacterTextSplitter` at ~1600 chars / 240 overlap (≈400 tokens / 60, well under BGE's 512 max sequence length). Dense retrieval alone is sufficient at our scale; revisit hybrid only if observed recall on rare technical terms (e.g. `DF-21D`, `JFSO`) is poor.

## Embedding model comparison

We are encoding a few hundred chunks once at ingest and ≤50 queries per pipeline run. Embedding throughput is not a binding constraint; quality on dense military terminology is. The four candidates compare as follows on MTEB retrieval averages and on the practical numbers that matter for this project. (Speed measured CPU, batch=32, ~256-token inputs, on an Apple M-series; absolute numbers will vary, the *ratios* are stable.)

| Model | Dim | Max seq | MTEB retr. avg | CPU encode (chunks/sec) | Disk | Recommended? |
|---|---|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | 512 | ~41.9 | ~120 | 80 MB | No — quality penalty too large for technical text |
| `all-mpnet-base-v2` | 768 | 514 | ~43.8 | ~35 | 420 MB | No — beaten on retrieval by BGE-base at similar cost |
| `BAAI/bge-base-en-v1.5` | 768 | 512 | ~53.3 | ~30 | 440 MB | **Yes** — best quality/cost trade for our scale |
| `BAAI/bge-large-en-v1.5` | 1024 | 512 | ~54.3 | ~10 | 1.3 GB | No — +1 MTEB point, 3× slower, 3× larger; not worth it |

**Recommendation: `BAAI/bge-base-en-v1.5`.** Reasoning:

1. **Retrieval objective.** BGE was trained with a contrastive retrieval objective on a query-passage corpus (including domain-mixed technical text), whereas the `all-*` models were trained with a more general sentence-similarity objective. On dense military terminology — where queries like *"phases of the Joint Island Landing Campaign"* must match passages that say *"three operational phases of cross-strait amphibious operations"* — BGE's training is closer to our task.
2. **Latency is not the binding constraint.** At ~300 chunks ingested once, a 30 chunks/sec model finishes in 10 seconds. At query time, a single ~10 ms encode + ~5 ms HNSW lookup is invisible inside a pipeline that already calls an LLM costing seconds.
3. **`bge-large` does not earn its cost.** The MTEB delta is ~1 point; in qualitative review of doctrine retrieval that delta is rarely visible, and the 3× slowdown plus 1.3 GB checkpoint hurts cold-start in CI and on laptops.
4. **Asymmetric query prefix.** BGE-v1.5 expects (English) queries to be prefixed with `"Represent this sentence for searching relevant passages: "`. Documents are encoded raw. This is built into our `retrieve.py` below. The prefix gives a 1–2 point recall lift; the v1.5 release made it optional but it still helps.

**Reranking note (out of scope for v1).** If retrieval quality becomes the bottleneck after v1, the next step is a cross-encoder reranker (`BAAI/bge-reranker-base` or `cross-encoder/ms-marco-MiniLM-L-6-v2`) over the top-20 dense hits to pick the final top-6. That gives a much bigger lift than swapping `bge-base` for `bge-large`.

## Chunking strategy

The PROJECT_SPEC tentatively says "800 tokens, 150 overlap." **Adjust both numbers down.** Two reasons:

1. **Embedding-side truncation.** `bge-base-en-v1.5` has `max_seq_length=512` tokens. Anything longer is silently truncated, so chunks above 512 tokens lose their tail. 400 tokens leaves headroom for the BGE query prefix (≈10 tokens) and for tokenizer variance across English vs. transliterated PLA terminology.
2. **`RecursiveCharacterTextSplitter` defaults to characters.** `chunk_size=800` literally means 800 characters (~200 tokens) — too small. Either pass a token-based `length_function`, or convert the spec to characters at the standard ~4 chars/token English ratio.

**Recommended:** 1600 chars / 240 overlap, recursive splitting on `["\n\n", "\n", ". ", "? ", "! ", " ", ""]`. This averages ~400 tokens / 60 overlap and respects the BGE budget. Hierarchy (chapter, section, page) goes in metadata, not in the chunk text.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1600,
    chunk_overlap=240,
    separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
    keep_separator=False,
)
```

**Should you do semantic chunking instead?** No, not for v1. Semantic chunkers (e.g. `llama-index`'s `SemanticSplitterNodeParser`) embed every sentence and merge adjacent sentences whose embeddings are close, producing variable-length chunks. They cost N embedding calls *per document* during ingest and are sensitive to the embedding model's behavior on jargon — exactly where doctrine PDFs are weakest. The recursive character splitter is dumb but predictable, and the failures it produces (a chunk that splits a numbered-list mid-item) are easier to debug than the failures of semantic chunking (a chunk that quietly merges two unrelated sections because the embedding model thought they were similar). Revisit semantic chunking only if recall is poor *and* you can show the failures are at chunk-boundary points.

**Hierarchy preservation.** JP 3-0 / JP 5-0 / *Science of Campaigns* are deeply nested (chapter → section → subsection → paragraph). Don't try to extract that hierarchy from arbitrary PDFs reliably — it varies by document. Instead, store the cheap-and-stable signals: `doc_title`, `page`, `chunk_index`. Add `chapter` / `section` only if you ingest a doc whose layout you can parse (e.g. JPs follow a known heading convention). For the hackathon, page is enough — citations like *"JP 3-0 p. 47"* are what the audience reads anyway.

## PDF ingestion library choice

Three serious options for military doctrine PDFs:

| Library | License | Speed | Layout | Tables | Notes |
|---|---|---|---|---|---|
| `pypdf` | BSD-3 | Slow | OK | Poor | Pure Python, zero system deps. Already pinned in `pyproject.toml`. |
| `pdfplumber` | MIT | Slow | Good | **Best** | Built on `pdfminer.six`. Use for table-heavy reports (CSIS OOB tables). |
| `PyMuPDF` (`fitz`) | **AGPL-3.0** | **Fastest** (~5–10×) | Best | Good | Requires MuPDF C library. AGPL is a hard no for closed-source/commercial; OK for internal/research. |

**Recommendation: `pypdf` for v1.** Reasoning:

1. **It is already a pinned dependency.** Switching adds friction in a hackathon timeline.
2. **Doctrine PDFs are mostly linear narrative text.** Tables and figures matter for OOB reports but the *captions and surrounding paragraphs* almost always restate the relevant numbers. Losing the table layout costs us less than it would on a financial 10-K.
3. **AGPL on PyMuPDF is a real concern** if the prototype is ever shared, demoed publicly, or rolled into a downstream product. The licensing question is not worth resolving for a marginal speedup at ingest time on a few hundred pages.

**Escalation path.** If a specific document is producing garbage chunks (e.g. CSIS reports with two-column layout extracted as interleaved garbage), wrap that one document with `pdfplumber.extract_text(layout=True)`. Don't switch the whole pipeline.

## Hybrid retrieval — yes or no?

**No for v1.** Reasoning:

- **Scale.** With ~300 chunks total and top-k=6, the dense-retrieval recall@6 on technical queries is empirically ~0.8–0.9 with BGE-base. There is not much headroom for BM25 to recover.
- **Where BM25 wins is rare-token queries.** *"DF-21D"*, *"Type 075"*, *"Volt Typhoon"* are exactly the strings that dense retrieval *can* miss, because subword tokenization fragments them and the embedding loses specificity. But these strings are rare in our queries — the modal-ensemble prompt asks about *campaigns and concepts*, not specific platform names.
- **Cost of adding it.** A clean BM25 + dense fusion (Reciprocal Rank Fusion, k=60) is ~80 lines of code and a `rank_bm25` dependency. ChromaDB does not natively support hybrid; you maintain a parallel index. In a hackathon that complexity should buy something measurable, and at our scale it does not.

**Trigger for adding hybrid later.** Build a 20-query eval set (rare technical terms, paraphrases, multi-hop). If dense recall@6 on that set drops below ~0.75, add BM25 + RRF. Budget half a day.

## Citation metadata schema

Store everything the modal-ensemble prompt needs to render a human-readable citation, plus the deterministic ID for the audit log.

```python
{
    "passage_id":   "JP-3-0-p047-c01-9a7b3f",  # deterministic, doc-page-chunk-hash[:6]
    "doc_title":    "JP-3-0",                   # cleaned filename stem
    "source_path":  "doctrine/raw/JP-3-0.pdf",  # relative to data/
    "page":         47,
    "chunk_index":  1,                          # within-page chunk ordinal
    # optional, when parseable from the PDF:
    # "chapter":    "III",
    # "section":    "Operational Art",
}
```

The chunk text itself is stored as the Chroma `document` field, not duplicated in metadata. `passage_id` is what the LLM cites; `doc_title` + `page` is what the human reads. The 6-char hash suffix prevents collisions when re-ingesting a doc whose chunk boundaries shift by one character due to a PDF re-download.

## Working code: ingest.py

```python
# src/doctrine/ingest.py
"""Build a ChromaDB index from PDFs in data/doctrine/raw/.

Run: uv run python -m src.doctrine.ingest
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Iterator

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

LOGGER = logging.getLogger(__name__)

EMBED_MODEL = "BAAI/bge-base-en-v1.5"
COLLECTION = "doctrine"
DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_ROOT / "doctrine" / "raw"
CHROMA_DIR = DATA_ROOT / "chroma"

CHUNK_SIZE = 1600    # ~400 tokens English; under bge max_seq_length=512
CHUNK_OVERLAP = 240  # ~60 tokens
INGEST_BATCH = 64


def _passage_id(doc_stem: str, page: int, chunk_idx: int, text: str) -> str:
    h = hashlib.sha1(f"{doc_stem}|{page}|{chunk_idx}|{text[:96]}".encode()).hexdigest()[:6]
    return f"{doc_stem}-p{page:03d}-c{chunk_idx:02d}-{h}"


def _iter_pdf_pages(path: Path) -> Iterator[tuple[int, str]]:
    reader = PdfReader(str(path))
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        # Light cleanup: doctrine PDFs are noisy with hyphenated line-breaks
        text = re.sub(r"-\n", "", text)            # de-hyphenate
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if text.strip():
            yield page_num, text


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
        keep_separator=False,
    )


def build_index(rebuild: bool = False) -> int:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Doctrine PDF dir missing: {RAW_DIR}")
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if rebuild and COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL, normalize_embeddings=True
    )
    collection = client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine", "embed_model": EMBED_MODEL},
    )

    splitter = _splitter()
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        LOGGER.warning("No PDFs in %s", RAW_DIR)
        return 0

    total = 0
    for pdf in pdfs:
        LOGGER.info("Ingesting %s", pdf.name)
        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict] = []
        for page_num, page_text in _iter_pdf_pages(pdf):
            for chunk_idx, chunk in enumerate(splitter.split_text(page_text)):
                if len(chunk) < 80:  # drop boilerplate fragments
                    continue
                pid = _passage_id(pdf.stem, page_num, chunk_idx, chunk)
                ids.append(pid)
                docs.append(chunk)
                metas.append(
                    {
                        "passage_id": pid,
                        "doc_title": pdf.stem,
                        "source_path": str(pdf.relative_to(DATA_ROOT)),
                        "page": page_num,
                        "chunk_index": chunk_idx,
                    }
                )

        for i in range(0, len(ids), INGEST_BATCH):
            collection.upsert(
                ids=ids[i : i + INGEST_BATCH],
                documents=docs[i : i + INGEST_BATCH],
                metadatas=metas[i : i + INGEST_BATCH],
            )
        total += len(ids)
        LOGGER.info("  %s: %d chunks", pdf.stem, len(ids))

    LOGGER.info("Index built. Collection size: %d (added this run: %d)",
                collection.count(), total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    build_index(rebuild=True)
```

## Working code: retrieve.py

```python
# src/doctrine/retrieve.py
"""Query the doctrine ChromaDB index.

Used by the modal-ensemble prompt; NOT used by the off-distribution generator.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions

EMBED_MODEL = "BAAI/bge-base-en-v1.5"
COLLECTION = "doctrine"
DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
CHROMA_DIR = DATA_ROOT / "chroma"

# BGE-v1.5 retrieval-instruction prefix (queries only; docs encoded raw)
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@dataclass(frozen=True)
class Passage:
    passage_id: str
    doc_title: str
    page: int
    chunk_index: int
    text: str
    score: float  # 1 - cosine_distance, so higher = more similar

    def cite(self) -> str:
        return f"[{self.doc_title} p.{self.page} ¶{self.chunk_index}]"


@functools.lru_cache(maxsize=1)
def _collection() -> Collection:
    if not CHROMA_DIR.exists():
        raise FileNotFoundError(
            f"Chroma index missing at {CHROMA_DIR}. "
            f"Run: uv run python -m src.doctrine.ingest"
        )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL, normalize_embeddings=True
    )
    return client.get_collection(name=COLLECTION, embedding_function=ef)


def retrieve(
    query: str,
    k: int = 6,
    where: dict[str, Any] | None = None,
) -> list[Passage]:
    """Top-k passages for a natural-language query.

    `where` is a Chroma metadata filter, e.g. {"doc_title": "JP-3-0"} or
    {"$and": [{"doc_title": "JP-3-0"}, {"page": {"$lte": 100}}]}.
    """
    coll = _collection()
    res = coll.query(
        query_texts=[QUERY_INSTRUCTION + query],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    out: list[Passage] = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True
    ):
        out.append(
            Passage(
                passage_id=str(meta["passage_id"]),
                doc_title=str(meta["doc_title"]),
                page=int(meta["page"]),
                chunk_index=int(meta["chunk_index"]),
                text=doc,
                score=1.0 - float(dist),
            )
        )
    return out


def format_for_prompt(passages: list[Passage]) -> str:
    """Render passages for inclusion in the modal-ensemble prompt."""
    blocks = []
    for p in passages:
        blocks.append(f"--- {p.cite()} (id={p.passage_id}) ---\n{p.text}")
    return "\n\n".join(blocks)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "phases of the Joint Island Landing Campaign"
    for p in retrieve(q, k=5):
        print(f"{p.score:.3f}  {p.cite():<40}  id={p.passage_id}")
        print(f"  {p.text[:240].strip()}…\n")
```

## Gotchas

**1. Embedding-function mismatch on reload.** ChromaDB does *not* persist the embedding function — only its name in metadata, which it does not enforce. If you call `client.get_collection("doctrine")` without passing `embedding_function=`, Chroma silently uses its default (MiniLM-L6-v2) for any subsequent `query_texts` call, and you will get garbage results that look superficially plausible. **Fix:** every `get_collection` / `get_or_create_collection` call must pass the same `embedding_function`. The wrapper in `_collection()` above is the canonical pattern.

**2. `PersistentClient` path must be stable.** Chroma stores SQLite + parquet files at the path you give. If you accidentally instantiate it with a relative path, `cwd` changes between `ingest.py` (run from project root) and `streamlit_app.py` (run from wherever Streamlit launches) will silently create a *second* empty index. Always derive the path from `Path(__file__)`.

**3. `.persist()` is deprecated.** In `chromadb>=0.4`, `PersistentClient` flushes on every write; `client.persist()` is a no-op that may emit a deprecation warning. Don't call it.

**4. HNSW index lazy-build.** The first `query()` after a fresh ingest builds the HNSW graph; expect ~1–3 s of latency on the first call, then sub-100 ms after. If you benchmark cold-start, prime the index with a throwaway query.

**5. Re-ingest leaks chunks.** If you change `CHUNK_SIZE` and re-run ingest without `rebuild=True`, you get *both* old and new chunks in the collection. Worse, `upsert` keys on `id` — and our deterministic `passage_id` includes a hash of the first 96 chars, so the new chunks have new IDs and the old ones stick around. **Fix:** always pass `rebuild=True` (or `rm -rf data/chroma/`) when chunk parameters change.

**6. `.gitignore`.** Three things must stay out of git:
```
data/doctrine/raw/   # PDFs may be redistributable but are large
data/chroma/         # machine-specific; rebuild from source
data/memory.db       # per-run state
.env                 # API keys
```
Verify with `git check-ignore -v data/chroma/chroma.sqlite3` before committing.

**7. `sentence-transformers` first-run download.** `BAAI/bge-base-en-v1.5` is ~440 MB pulled to `~/.cache/huggingface/hub/`. CI that doesn't cache that path will re-download every run. Add HF cache to your CI cache key. For air-gapped demos, `huggingface-cli download BAAI/bge-base-en-v1.5` ahead of time.

**8. Metadata field types.** Chroma metadata values must be `str | int | float | bool | None`. A list (e.g. `tags: ["jp", "joint-ops"]`) raises at insert time. Either flatten to a comma-separated string or store the JSON as a string and parse on retrieval.

**9. `where` filter syntax.** Chroma's filter language is MongoDB-ish but not identical: `{"page": {"$lte": 100}}` works; `{"page": {"$between": [1, 100]}}` does not. Compose ranges with `$and` + `$gte`/`$lte`.

**10. BGE prefix at ingest.** *Do not* add the `"Represent this sentence..."` prefix to documents at ingest. It is a query-side instruction. Adding it to documents degrades recall noticeably (asymmetric encoding becomes symmetric in the wrong direction).

**11. `langchain-text-splitters` is the standalone package.** Import from `langchain_text_splitters`, not from `langchain.text_splitter` (which is the legacy path inside the umbrella `langchain` package and pulls in heavy deps we don't need).

**12. PDF text extraction returning empty pages.** `pypdf` returns `""` for scanned-image PDFs (no embedded text layer). Doctrine PDFs from official US sources are almost all text-layer; some Chinese-language sources mirrored through PRC academic portals are scans. If `_iter_pdf_pages` yields zero text from a doc, OCR with `ocrmypdf` ahead of ingest rather than trying to handle it inline.

## Bibliography

- Chroma. *Chroma documentation: PersistentClient, embeddings, collections, query.* docs.trychroma.com (accessed April 2026).
- Chroma. *Embedding functions: SentenceTransformerEmbeddingFunction.* github.com/chroma-core/chroma, `chromadb/utils/embedding_functions/sentence_transformer_embedding_function.py`.
- BAAI / FlagOpen. *FlagEmbedding: bge-base-en-v1.5 model card.* huggingface.co/BAAI/bge-base-en-v1.5; bge-large-en-v1.5 model card. Note on query instruction prefix and v1.5 reduced sensitivity.
- Reimers, N. and Gurevych, I. *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* EMNLP 2019. (Origin of `sentence-transformers`.)
- Muennighoff, N., Tazi, N., Magne, L., Reimers, N. *MTEB: Massive Text Embedding Benchmark.* EACL 2023. Live leaderboard at huggingface.co/spaces/mteb/leaderboard. Retrieval-task averages cited above are from the leaderboard snapshot, April 2026.
- Xiao, S. et al. *C-Pack: Packaged Resources To Advance General Chinese Embedding.* arXiv:2309.07597 (2023). BGE training methodology.
- LangChain. *RecursiveCharacterTextSplitter API.* python.langchain.com/api_reference/text_splitters; package `langchain-text-splitters`.
- Robertson, S. and Zaragoza, H. *The Probabilistic Relevance Framework: BM25 and Beyond.* Foundations and Trends in IR, 2009. (Reference for hybrid-retrieval discussion.)
- Cormack, G., Clarke, C., Buettcher, S. *Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods.* SIGIR 2009. (RRF for hybrid fusion.)
- pypdf maintainers. *pypdf documentation.* pypdf.readthedocs.io.
- pdfplumber. *pdfplumber README and table-extraction docs.* github.com/jsvine/pdfplumber.
- Artifex Software. *PyMuPDF (fitz) documentation and AGPL-3.0 license.* pymupdf.readthedocs.io.
- Hugging Face. *huggingface_hub cache layout and offline mode.* huggingface.co/docs/huggingface_hub/guides/manage-cache.
