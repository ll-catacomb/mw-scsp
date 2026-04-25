"""Doctrine retrieval: two-pass match against the markdown corpus.

See PROJECT_SPEC.md §5 and data/doctrine/passages/SCHEMA.md.

Pass 1: tokenize query, intersect with index.by_keyword (incl. synonyms) and
        index.by_topic, filter by applies-to == stage, score by
        (keyword hits + 0.5 * topic hits + priority weight), take top-k.
Pass 2: only if pass 1 returns < 2 hits — pass the index summary to a small
        Claude/GPT call that returns up to top-k passage ids. Catches off-
        distribution Red vocabulary that doesn't lexically match the doctrine.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from pydantic import BaseModel, Field

from src.doctrine.index import DoctrineIndex, KNOWN_TOPICS, Passage, load_index


# Stop tokens that aren't useful for keyword matching against doctrine corpora.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "for", "from", "had",
    "has", "have", "he", "her", "him", "his", "how", "i", "in", "into", "is", "it", "its",
    "may", "of", "on", "or", "she", "such", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "those", "to", "was", "we", "were", "what", "when",
    "which", "who", "why", "will", "with", "would", "you", "your",
})

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-_0-9]+")


@dataclass
class RetrievalHit:
    """A single passage returned by retrieve(). Score combines pass-1 weights."""

    passage: Passage
    score: float
    matched_keywords: list[str]
    matched_topics: list[str]
    via: str  # 'keyword-topic' | 'llm-router'

    def to_dict(self) -> dict:
        """Serializable form for the audit log and prompt rendering."""
        p = self.passage
        return {
            "id": p.id,
            "source": p.source,
            "edition": p.edition,
            "section": p.section,
            "page": p.page,
            "type": p.type,
            "priority": p.priority,
            "topics": p.topics,
            "body": p.body,
            "score": round(self.score, 3),
            "matched_keywords": self.matched_keywords,
            "matched_topics": self.matched_topics,
            "via": self.via,
        }


@lru_cache(maxsize=1)
def _cached_index() -> DoctrineIndex:
    """Load the index once per process. Tests can pass a custom index via retrieve_with_index."""
    return load_index()


def _tokenize(query: str) -> list[str]:
    raw = (t.lower() for t in _TOKEN_RE.findall(query))
    return [t for t in raw if t not in _STOPWORDS and len(t) > 1]


def _candidate_topics(tokens: set[str]) -> set[str]:
    """Map free-text tokens to known controlled-vocab topic tags by substring/equality."""
    candidates: set[str] = set()
    for topic in KNOWN_TOPICS:
        topic_tokens = set(topic.split("-"))
        if topic_tokens & tokens or topic.replace("-", "") in tokens:
            candidates.add(topic)
    return candidates


def _score_pass1(
    query: str, stage: str, index: DoctrineIndex, top_k: int,
) -> list[RetrievalHit]:
    tokens = set(_tokenize(query))
    if not tokens:
        return []

    eligible = {p.id for p in index.by_applies_to.get(stage, [])}
    if not eligible:
        return []

    # Walk the keyword/synonym index. A passage's keyword may be multi-word ("never assume away");
    # the simplest match check is "every word of the keyword phrase appears in the query tokens",
    # which is order-insensitive and catches reorderings.
    keyword_hits: dict[str, Counter] = {pid: Counter() for pid in eligible}
    for kw, passages in index.by_keyword.items():
        kw_tokens = set(_tokenize(kw))
        if not kw_tokens:
            continue
        if kw_tokens.issubset(tokens):
            for p in passages:
                if p.id in eligible:
                    keyword_hits[p.id][kw] += 1

    # Topic hits: candidate topics from the query that intersect a passage's topics.
    cand_topics = _candidate_topics(tokens)
    topic_hits: dict[str, list[str]] = {pid: [] for pid in eligible}
    for topic in cand_topics:
        for p in index.by_topic.get(topic, []):
            if p.id in eligible:
                topic_hits[p.id].append(topic)

    hits: list[RetrievalHit] = []
    for pid in eligible:
        kh = keyword_hits[pid]
        th = topic_hits[pid]
        if not kh and not th:
            continue
        passage = index.by_id[pid]
        score = sum(kh.values()) + 0.5 * len(th) + passage.priority_weight()
        hits.append(RetrievalHit(
            passage=passage,
            score=score,
            matched_keywords=sorted(kh.keys()),
            matched_topics=sorted(th),
            via="keyword-topic",
        ))

    hits.sort(key=lambda h: (-h.score, h.passage.id))
    return hits[:top_k]


# ---- Pass 2: LLM router fallback ----

class _RouterResponse(BaseModel):
    """Schema for the small LLM-router call. Returns ids of up-to-top_k passages."""
    passage_ids: list[str] = Field(default_factory=list)


_ROUTER_SYSTEM = (
    "You are an index router for a wargame doctrine corpus. The user gives you a query "
    "and a list of available passages with their ids and one-line descriptions. Return "
    "ONLY a JSON object with the field `passage_ids` listing the ids most relevant to "
    "the query, in order of relevance, up to the requested limit. Do not invent ids."
)


async def _llm_router(
    query: str, stage: str, index: DoctrineIndex, top_k: int, run_id: str,
) -> list[RetrievalHit]:
    """Async LLM router fallback. Imported lazily so tests don't pull anthropic/openai."""
    from src.llm.wrapper import logged_completion  # local import to keep import graph thin

    summary_lines = index.all_summary_lines(stage)
    if not summary_lines:
        return []
    user_msg = (
        f"Query: {query}\n\n"
        f"Pipeline stage: {stage}\n\n"
        f"Limit: up to {top_k} passage ids.\n\n"
        f"Available passages:\n" + "\n".join(summary_lines)
    )
    model = os.environ.get("DOCTRINE_ROUTER_MODEL", os.environ.get("JUDGE_CLAUDE_MODEL", "claude-haiku-4-5-20251001"))
    result = await logged_completion(
        run_id=run_id,
        stage="doctrine-router",
        agent_id=None,
        model=model,
        system=_ROUTER_SYSTEM,
        user=user_msg,
        temperature=0.0,
        max_tokens=512,
        prompt_path=None,
        response_format=_RouterResponse,
    )
    parsed: _RouterResponse | None = result["parsed"]
    if parsed is None:
        return []
    hits: list[RetrievalHit] = []
    for pid in parsed.passage_ids[:top_k]:
        passage = index.by_id.get(pid)
        if passage is None or stage not in passage.applies_to:
            continue
        hits.append(RetrievalHit(
            passage=passage,
            score=0.0,
            matched_keywords=[],
            matched_topics=[],
            via="llm-router",
        ))
    return hits


# ---- Public API ----

def retrieve_sync(
    query: str, stage: str, top_k: int = 6, *,
    index: DoctrineIndex | None = None,
) -> list[dict]:
    """Synchronous, pass-1-only retrieval.

    Useful for tests, dry-run validation, and code paths that should not trigger an LLM
    call. Pass 2 (LLM router) is unavailable here — call `retrieve()` for that.
    """
    idx = index or _cached_index()
    hits = _score_pass1(query, stage, idx, top_k)
    return [h.to_dict() for h in hits]


async def retrieve(
    query: str, stage: str, top_k: int = 6, *,
    run_id: str = "doctrine-retrieve",
    index: DoctrineIndex | None = None,
) -> list[dict]:
    """Two-pass retrieval. Pass 1 is keyword/topic; pass 2 is the LLM router.

    Args:
        query: free-text query (Red move text, scenario summary, adjudication context).
        stage: one of 'modal-grounding' | 'adjudication' | 'off-distribution-flag' |
               'blue-frame-check' | 'judge-rubric'. Filters passages by frontmatter
               `applies-to`.
        top_k: max passages to return.
        run_id: opaque id used by the router fallback for audit logging. Pipeline code
                passes the active run's id; ad-hoc callers can leave the default.
        index: optional pre-loaded `DoctrineIndex`. Pipelines should pass one to avoid
               re-walking the tree per call.

    Returns:
        List of dicts (RetrievalHit.to_dict()) sorted by relevance. Each contains the
        full passage body inline; pipeline code renders these into the prompt's
        doctrine block. The list of returned `id` strings is also what
        `modal_moves.doctrine_cited` should record (unless the model trims to those it
        actually used).
    """
    idx = index or _cached_index()
    hits = _score_pass1(query, stage, idx, top_k)
    if len(hits) >= 2:
        return [h.to_dict() for h in hits]
    # Pass 2 fallback. Append router results, dedupe by id, preserve pass-1 ordering first.
    router_hits = await _llm_router(query, stage, idx, top_k, run_id)
    seen = {h.passage.id for h in hits}
    for h in router_hits:
        if h.passage.id not in seen:
            hits.append(h)
            seen.add(h.passage.id)
        if len(hits) >= top_k:
            break
    return [h.to_dict() for h in hits]
