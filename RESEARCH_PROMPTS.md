# Research-agent prompts

Eight parallel research agents. Each runs in its own Claude.ai chat or `claude-code` subagent. Each writes its output to `_context/agent-output/raN-{slug}.md` in this repo. They are designed to run independently — no coordination needed.

The main Claude Code instance reads these outputs when iterating on prompts and YAMLs in Tier 1+. Quality > completeness; partial output that is well-cited beats exhaustive output that isn't.

---

## RA-1 — PLA Taiwan operational concepts (CSIS open-access selection)

**Output file:** `_context/agent-output/ra1-pla-doctrine.md`

You are doing source curation for a wargame red-team system focused on a Taiwan Strait crisis scenario in spring 2028 (PLA vs ROC + US INDOPACOM). The system uses a doctrine RAG corpus to ground its modal-ensemble Red moves. We need a curated reading list of CSIS open-access publications (and similar — RAND, IISS, USNI, war on the rocks) that bear directly on PLA operational concepts for cross-strait operations.

For each source you select:
1. Full title and author(s).
2. Direct URL to a publicly available copy (PDF preferred).
3. 2–3 sentence summary of why it matters for Red-side reasoning specifically (not Blue-side).
4. The 1–3 specific sections most relevant to "what would Red do in the opening 7 days of a Taiwan crisis."
5. A flag if the source is paywalled / behind a soft paywall / open-access.

Aim for 8–15 sources. Quality > quantity. Prioritize:
- PLA Joint Operations / Joint Logistics doctrine (open-source translations or analyses).
- Recent (2022+) operational analysis of PLA exercises around Taiwan.
- Analyses of PLA Rocket Force counter-intervention concepts.
- Analyses of cognitive / political warfare against Taiwan that an opening-move Red planner would consider.

Avoid: introductory PRC-rise overviews, US-perspective deterrence theory, anything pre-2020 unless it's foundational doctrine.

Format the output as a markdown table or numbered list — easy to scan. Save to `_context/agent-output/ra1-pla-doctrine.md`.

---

## RA-2 — Joint Publication 3-0 and 5-0, adversary-planning sections

**Output file:** `_context/agent-output/ra2-jp-3-0-5-0.md`

You are extracting a section-level reading guide from US Joint Publication 3-0 (*Joint Operations*) and Joint Publication 5-0 (*Joint Planning*) for an adversary-planning red-team system. The system will use these as part of its doctrine RAG. We need to know which sections to emphasize.

For each JP:
1. The current edition's URL (Joint Chiefs of Staff Doctrine Library).
2. Table of contents at chapter level.
3. The 5–10 most relevant sections for "Red planner reasoning about an opening move." Include section number, heading, and 2–3 sentence justification.
4. Concrete page ranges if the document is paginated.
5. A short note on whether any sections are explicitly Blue-perspective and should be filtered out of Red prompts.

The point is not to summarize the JPs — the RAG can do that — but to identify which slices of them belong in a Red-planner's reading queue. Save to `_context/agent-output/ra2-jp-3-0-5-0.md`.

---

## RA-3 — Off-distribution corpus for the PLA Taiwan scenario

**Output file:** `_context/agent-output/ra3-pla-off-dist-corpus.md`

You are doing reading for the off-distribution generation stage of a wargame red-team system. The system will identify the *modal* PLA opening moves the LLM ensemble converges on (likely: amphibious assault, missile saturation, blockade, gray-zone escalation), and then generate moves that are PLAUSIBLE BUT OFF-DISTRIBUTION.

We need a curated set of sources that surface PLA operational concepts likely to be UNDERREPRESENTED in mainstream open-source analysis but that a careful adversary planner could justify. Examples of the kind of concept we want:
- Cognitive / cyber / financial warfare as the opening lever rather than kinetic.
- Operations on the "third front" — disrupting US logistics in CONUS, SLOC interdiction far from Taiwan, attack on space assets.
- Domestic-political warfare against Taiwan that bypasses kinetic conflict entirely.
- Coalition fragmentation moves aimed at Japan / Australia / Philippines specifically.
- Unconventional uses of civilian / paramilitary / commercial assets.
- Concepts drawn from PLA historical doctrine (e.g., Active Defense, Local War under Informationization Conditions) that don't map cleanly to a Pacific kinetic frame.

For each source: title, author(s), URL, 2–3 sentences on the off-distribution concept it surfaces, and a flag if you think the concept is plausible OR fringe.

Aim for 8–12 sources. Save to `_context/agent-output/ra3-pla-off-dist-corpus.md`.

---

## RA-4 — Middle East cascade scenario population

**Output file:** `_context/agent-output/ra4-me-cascade-corpus.md`

You are populating the second wargame scenario for the system: a Middle East regional cascade triggered by an Israeli kinetic action, with a Red coalition of Iran + Hezbollah + Houthi + Iraqi/Syrian militias. The scenario stub is at `scenarios/israel_me_cascade_2026.yaml` (currently `status: WIP`).

Produce:
1. A specific triggering action that is plausible, drawn from open-source reporting on the period 2024–2026, and operationally useful for the wargame (something that would compel multi-actor response without making the response trivially predictable). Avoid commentary on any specific real-world decision-maker.
2. A short capability summary block per actor (Iran, Hezbollah, Houthi, Iraqi/Syrian militias) suitable to drop into the YAML.
3. 6–10 open-access sources that should go into the doctrine RAG corpus for this scenario. CSIS, RAND, FDD, ISW, and similar are all fair game; flag bias when relevant.
4. A list of 4–6 historical analogies the modal ensemble is likely to over-cite (these go into `historical_analogies_to_flag`), and 2–3 that are genre-incorrect (these go into `historical_analogies_to_exclude`).

Format as drop-in YAML where possible. Save to `_context/agent-output/ra4-me-cascade-corpus.md`.

---

## RA-5 — Wargaming validation register (for the demo's epistemic posture)

**Output file:** `_context/agent-output/ra5-yuna-wong-register.md`

You are calibrating the rhetorical register of a wargame red-team demo for an audience that includes professional wargame validation researchers (RAND, NDU, CSIS). The demo's core claim is *modest*: it surfaces hypotheses, it does not predict. We need to make sure the framing language is right.

Produce:
1. A 1-page reading list of the most important open-access work on wargame validation (Yuna Wong's RAND papers; Perla; Sabin; Caffrey; Bartels) — author, title, URL, 2 sentences on what it argues.
2. A list of 5–10 phrases that this audience finds *clarifying* (e.g., "this is a discovery game, not a forecast game") and 5–10 phrases that this audience finds *over-claiming* (e.g., "AI-driven prediction," "decision-quality output"). Each phrase with a 1-sentence justification.
3. A short list of recurring failure modes in LLM-driven wargaming work that this audience has flagged in print (or that the literature implies). 3–6 items.
4. A short "do not do this in the demo" list — concrete things that would lose this audience instantly.

The goal is to land in front of someone who has read this literature without flattering them. Save to `_context/agent-output/ra5-yuna-wong-register.md`.

---

## RA-6 — Cross-family API: current model ids + pricing + structured-output

**Output file:** `_context/agent-output/ra6-cross-family-api.md`

You are confirming current operational details for `litellm`-based cross-family API access (Claude + GPT) for a hackathon project. As of the date you run this prompt, produce:

1. Anthropic — current production model ids and per-million-token pricing for: Claude Opus (latest), Claude Sonnet (latest), Claude Haiku (latest). Cite the Anthropic docs page directly.
2. OpenAI — current production model ids and per-million-token pricing for the GPT-4-class flagship and the cheaper sibling. Cite the OpenAI docs page directly.
3. Recommended ids to plug into `.env.example` (`MODAL_CLAUDE_MODEL`, `MODAL_GPT_MODEL`, `HEAVY_CLAUDE_MODEL`, `JUDGE_CLAUDE_MODEL`, `JUDGE_GPT_MODEL`).
4. Notes on `litellm`'s structured-output support for each provider — the current name of the parameter, whether `response_format=PydanticModel` works on both, and any gotchas.
5. A budget estimate for one full pipeline run (~70 calls, ~75K tokens mixed) at current pricing. Order-of-magnitude is fine; cite which model you assumed for which slot.

Save to `_context/agent-output/ra6-cross-family-api.md`.

---

## RA-7 — ChromaDB + sentence-transformers RAG configuration  *(SUPERSEDED)*

> **Architecture changed.** The doctrine layer is now a curated markdown corpus
> with YAML frontmatter and two-pass keyword/topic retrieval (PROJECT_SPEC.md §5,
> `data/doctrine/passages/SCHEMA.md`). RA-7's existing output is retained for
> historical reference but should NOT guide implementation. Skip running this
> research prompt if it hasn't been run yet.

**Output file:** `_context/agent-output/ra7-chroma-rag.md`

You are confirming the current best-practice configuration for a small persistent ChromaDB collection used as a doctrine RAG for an LLM-grounded wargame system. Produce:

1. Current ChromaDB Python client API (as of 2026) — the persistent-client constructor, collection create/get pattern, batched-insert pattern, and query pattern. Cite the ChromaDB docs.
2. The recommended sentence-transformers embedding model for technical / military prose. Default candidate is `BAAI/bge-base-en-v1.5`; confirm or recommend an alternative with rationale.
3. A working chunking recipe: PDF → text → `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)` → list of `(text, metadata)` ready to embed. Note any current `langchain-text-splitters` quirks.
4. Sample retrieval call returning `[{passage_id, doc_title, page, chunk_index, text, score}]`.
5. A note on disk size expectations (rough).

Save runnable code snippets where helpful. Save to `_context/agent-output/ra7-chroma-rag.md`.

---

## RA-8 — Multi-agent / generative-agent frameworks (optional, low-priority)

**Output file:** `_context/agent-output/ra8-multi-agent-frameworks.md`

You are doing a lightweight survey of current Python frameworks for multi-agent / generative-agent systems (LangGraph, CrewAI, AutoGen, etc.) for a project that is *probably* going to roll its own minimal generative-agent layer per Park et al. (2023) but should briefly compare against the off-the-shelf options.

For each of the 4–6 most relevant frameworks:
1. Repo URL, current version, license.
2. 1-paragraph summary of what it does well.
3. 1-paragraph summary of what it does badly (or where it doesn't fit our use case — persistent memory across discrete pipeline runs, not continuous agent loops).
4. A "would I use this for our project?" call with a 1-sentence reason.

We are not looking for an answer; we are looking for evidence that we considered the alternatives and consciously chose to roll our own. Save to `_context/agent-output/ra8-multi-agent-frameworks.md`.

---

## How to run these

Each prompt is self-contained. Pick a Claude.ai chat or a `claude-code` subagent (web/CLI), paste the entire prompt for one RA, let it run, then drop the output file in `_context/agent-output/`. The main Claude Code instance reads from that directory when iterating on prompts and YAMLs. There is no coordination required between RAs.
