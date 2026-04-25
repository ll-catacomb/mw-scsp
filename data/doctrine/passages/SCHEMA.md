# Doctrine passage corpus — schema

The doctrine corpus is a directory of small markdown files, one passage per file, with YAML frontmatter the loader parses into a pydantic model. There is no embedding store, no Chroma, no chunking. Retrieval is keyword + topic match against frontmatter, with an optional LLM-routed second pass when the first pass returns zero hits.

## Directory layout

```
data/doctrine/passages/
├── SCHEMA.md                       ← this file
├── jp3-0/
│   ├── cog.md
│   ├── phasing-model.md
│   └── decisive-points.md
├── jp5-0/
│   ├── coa-screening.md
│   ├── never-assume-away.md
│   └── wargaming-action-reaction.md
├── pla/
│   └── ...                         ← from RA-1, RA-3
└── csis/
    └── ...                         ← from RA-1
```

One passage per file. Every file under `passages/` (except `SCHEMA.md` itself) MUST validate. The loader walks the tree at startup, parses frontmatter, and builds an in-memory index keyed on `id`.

## Frontmatter schema

```yaml
---
id: jp5-0-never-assume-away          # REQUIRED. Unique slug. Citation key. Stable across edits.
source: JP 5-0                       # REQUIRED. Human-readable source name.
edition: "2006"                      # REQUIRED. String (years collide if numeric). e.g. "2006", "2020", "2008-CH1", "2022".
section: "Ch. III — Assumptions"     # REQUIRED. Where in the source.
page: III-13                         # REQUIRED. Page or paragraph reference, as printed in the source.
type: warning                        # REQUIRED. One of:
                                     #   definition | principle | procedure
                                     #   screening-criterion | framework
                                     #   vocabulary | warning | example
priority: high                       # REQUIRED. high | medium | low. Adjudicator retrieval bias.
topics:                              # REQUIRED. List of topic tags. Free-form but reuse existing tags;
  - assumptions                      # see CONTROLLED_VOCAB section below.
  - adversary-modeling
  - off-distribution
keywords:                            # REQUIRED. Phrases that, if present in a query, should match this passage.
  - never assume away
  - adversary capabilities
  - valid assumption
synonyms:                            # OPTIONAL. Alt phrasings the query may use that don't appear verbatim.
  - assumed away
  - templated adversary
  - distributional assumption
applies-to:                          # REQUIRED. Pipeline stages that should retrieve this:
  - adjudication                     #   modal-grounding | adjudication | off-distribution-flag |
  - off-distribution-flag            #   blue-frame-check | judge-rubric
related:                             # OPTIONAL. Other passage `id`s that should often be retrieved together.
  - jp5-0-coa-screening
  - jp3-0-systems-perspective
---
```

Body: a short verbatim quote (under ~150 words; quote multiple if they belong together), then an optional **Why this is in the corpus** annotation explaining how the adjudicator should use the passage. Keep the body small — the loader returns the whole file as the retrieval result.

## Controlled vocabulary

`type` (closed set):
- **definition** — defines a doctrinal term (COG, decisive point, FDO).
- **principle** — a doctrinal "should" / "must" statement.
- **procedure** — a step or sequence (JPP step, wargaming method).
- **screening-criterion** — a validity test (suitable / feasible / acceptable / distinguishable / complete).
- **framework** — a multi-element structure (PMESII, the seventeen design elements, six-phase model).
- **vocabulary** — a term-definition pair without normative force.
- **warning** — explicit caution about a failure mode (e.g., "never assume away adversary capabilities").
- **example** — historical or illustrative case (Desert Storm COG analysis).

`priority` (closed set): `high` | `medium` | `low`. The adjudicator's retrieval routine biases toward `high`-priority passages when ties occur. Use `high` for passages that should be cited in most adjudications (COG definition, COA screening, "never assume away"); `medium` for situational; `low` for background.

`applies-to` (closed set):
- **modal-grounding** — modal ensemble retrieves this when generating Red moves.
- **adjudication** — Blue adjudicator retrieves this when scoring a Red move.
- **off-distribution-flag** — adjudicator uses this passage when explaining *why* a Red move is off-distribution.
- **blue-frame-check** — used to decide whether a Red move re-frames the problem vs. is a branch within it.
- **judge-rubric** — used by the Stage 5 judge pool when scoring plausibility.

`topics` is open but reuse existing tags. Current set: `cog`, `decisive-points`, `lines-of-operations`, `phasing`, `transitions`, `branches-sequels`, `operational-design`, `operational-approach`, `assumptions`, `adversary-modeling`, `off-distribution`, `coa-development`, `coa-screening`, `wargaming`, `risk`, `termination`, `systems-perspective`, `pmesii`, `clausewitz`, `red-cell`.

## Loader contract

`src/doctrine/index.py::load_index() -> DoctrineIndex` walks `data/doctrine/passages/`, parses every `*.md`, validates frontmatter against the pydantic model, and returns an index with:

- `by_id: dict[str, Passage]`
- `by_topic: dict[str, list[Passage]]`
- `by_keyword: dict[str, list[Passage]]` (lowercase, includes synonyms)
- `by_applies_to: dict[str, list[Passage]]`

Duplicate `id` values are a hard error. Missing required fields are a hard error. Unknown `type`, `priority`, or `applies-to` values are a hard error. Unknown `topics` values are a warning (encourages controlled-vocab use without blocking ingestion).

## Retrieval contract

`src/doctrine/retrieve.py::retrieve(query, stage, top_k=6) -> list[Passage]`:

1. **Pass 1 — keyword/topic match.** Tokenize `query`, intersect with `by_keyword` and `by_topic`, filter by `applies-to == stage`, score each passage by (keyword hits + 0.5 * topic hits + priority weight), take top-k.
2. **Pass 2 — LLM router (only if pass 1 returns < 2 hits).** Pass the index summary (id + section + one-line description from frontmatter) to a small Claude/GPT call that returns up to top-k passage ids. Useful for queries that use vocabulary the corpus doesn't lexically contain.
3. Return full passage objects; `modal_moves.doctrine_cited` stores the list of `id` strings.

The loader should be cheap enough to call at the start of every pipeline run (corpus is < 100 files; load + validate < 200ms). No persistent index needed.

## Authoring rules

- One passage per file. If two passages co-cite, link via `related:` rather than concatenating.
- Verbatim quotes: cite source/edition/page exactly. Use blockquote markdown.
- Do not edit a passage's `id` once it ships — it's the citation key in audit logs across runs.
- When the underlying doctrine is revised (e.g., JP 5-0 2020 replaces "adequate" with "suitable"), add a new passage with a new id (`jp5-0-coa-screening-2020`) rather than overwriting.
- Synonyms exist to catch off-distribution Red vocabulary that doesn't lexically appear in the doctrine. Be generous with synonyms but not promiscuous — every synonym you add becomes a retrieval magnet.
