# RA-8: Multi-Agent LLM Frameworks — Build vs Adopt

*Research agent output for SCSP wargaming red-team prototype. All sources publicly available. Compiled April 2026.*

## Recommendation

Build custom with `asyncio` + LiteLLM + a thin SQLite memory layer. Of the six frameworks evaluated, none is a good fit, and three are actively bad fits (AutoGen, CrewAI, LangGraph). The single piece worth pulling in by hand is the **memory-stream / reflection / retrieval triad** from the original Joon Sung Park *Generative Agents* paper (Park et al. 2023), reimplemented natively against our SQLite schema rather than copy-pasted; the original repo is Apache-2.0, frozen at the 2023 paper state, and its retrieval scoring formula (recency × importance × relevance) is the one durable contribution. **DSPy is the only framework worth keeping in reserve** — not for orchestration, but as an optional Tier-3 prompt-optimization pass over our hand-written prompts once we have a held-out scenario set.

## Why our use case is unusual

Most multi-agent frameworks are built around the wrong primitive for this project. They optimize for *conversational* multi-agent collaboration: agents talking to each other in turns, a manager-agent routing tasks, a group-chat abstraction, a "let the agents figure it out" execution model. AutoGen, CrewAI, and CAMEL all encode this shape at their core. LangGraph generalizes it to a state machine but inherits LangChain's heavy abstraction tax. Our pipeline is the opposite shape: **five sequential stages, each a single LLM call to a persistent role with its own memory, called once per stage per run, ~70 calls per pipeline total.** No back-and-forth. No emergent dialogue. No tool-use loops. The orchestrator is a `for stage in stages: result = await stage(prev_result)`. What we actually need is (a) async LLM calls with per-call audit logging, (b) per-agent memory keyed by role, (c) doctrine RAG hooks on some stages, and (d) a Streamlit UI that exposes the pipeline internals to judges. None of that requires a framework. All of it benefits from *not* having one — the demo posture is "show your work," and frameworks hide the work.

## Framework evaluation

### AutoGen

- **Status April 2026:** *Discontinued at Microsoft.* AutoGen v0.4 was Microsoft's late-2024/early-2025 ground-up async rewrite of the original Wu et al. 2023 codebase (Microsoft Research Blog, Jan 2025). On 1 October 2025 Microsoft announced **Microsoft Agent Framework**, a merger of AutoGen and Semantic Kernel into a single Python+.NET SDK. AutoGen and Semantic Kernel were placed in **maintenance mode** (bug fixes and security patches only, no new features). Microsoft Agent Framework reached Release Candidate on 19 February 2026 and 1.0 on or about 6 April 2026 (Visual Studio Magazine, April 2026; VentureBeat 2025). The original community split off as **AG2** (`ag2ai/ag2`) in November 2024, retained the `autogen` and `pyautogen` PyPI names, the 20k-member Discord, kept backward compatibility with v0.2, and continues independent development under Apache-2.0 (DEV.to "Microsoft Autogen Has Split"; ag2ai/ag2 README).
- **License:** AutoGen original — MIT; AG2 fork — Apache-2.0 from v0.3; Microsoft Agent Framework — MIT.
- **Fit:** Poor. The conversational/`GroupChat`/`SocietyOfMindAgent` core is exactly what we don't want. v0.4's actor model adds operational complexity (event bus, runtime) for problems we don't have at 70 calls/run. The branding chaos — original AutoGen / v0.4 rewrite / AG2 fork / Microsoft Agent Framework — is itself a fit problem: anything we build on top of "AutoGen" today will need a rewrite within twelve months whichever path we pick.
- **Verdict:** **skip.**

### CrewAI

- **Status April 2026:** Active and growing fast. ~30k+ GitHub stars early 2026 per CrewAI marketing material; a paid CrewAI Enterprise / AMP Suite layer launched 2025 over a still-MIT core (CrewAI docs; Wikipedia entry). Production deployments at named enterprise customers cited in their materials (treat with normal hype-discount).
- **License:** MIT (core framework). Compatible with our public-repo plan.
- **Fit:** Wrong primitive. CrewAI is built around `Crew` (a team) and `Task` (a goal assigned to an agent) with a manager-agent routing pattern. The framework's value-add is *delegation* and *role collaboration* — exactly what we don't need when our "agents" are pre-assigned pipeline stages. Internal prompts are customizable (per CrewAI community), but we'd be fighting the framework to disable the orchestration logic we don't want, only to keep the LLM-call abstraction we already have via LiteLLM. The Flows API (added 2025) is closer to our shape (deterministic pipelines) but is a thin wrapper over what `asyncio` already provides.
- **Verdict:** **skip.**

### LangGraph

- **Status April 2026:** Active, well-funded (LangChain, Inc.), MIT-licensed core. Used in production at Klarna, Replit, Elastic per LangChain marketing. 2026 positioning is "stateful orchestration" — graph-based agent workflows with checkpointed state, LangGraph Cloud hosted runtime, LangSmith integration (Mager 2026; LangGraph docs).
- **License:** MIT (per the repo's LICENSE file).
- **Fit:** Wrong abstraction tier and wrong demo posture. LangGraph models pipelines as `StateGraph` with nodes, edges, and immutable checkpointed state. Technically our pipeline *is* a state graph (5 nodes, linear), but representing it as one buys nothing — we don't have cycles, we don't have conditional routing beyond `if stage_failed: skip`, and the checkpoint/recovery story is overkill for a 70-call demo run. The recurring criticism in the developer literature (Pan Xinghan; Stop Confusing LangChain/LangGraph/Deep Agents 2026; Upgrad 2026) is that LangGraph "formalizes" rather than reduces LangChain's abstraction tax: 5+ layers between your code and the LLM call, leaky abstractions, ~1s per-request overhead from wrapper machinery. For a "show your work" judge demo, this is the worst possible posture: the framework actively hides the prompt and the LLM call from view.
- **Verdict:** **skip.**

### CAMEL

- **Status April 2026:** Active. Apache-2.0. CAMEL-AI is now positioned as a research collective ("100+ researchers") working on agent scaling laws, with a production-leaning multi-agent stack (`RolePlayingWorkforce`, `BabyAGI`, single-agent `ChatAgent`/`CriticAgent`/`DeductiveReasonerAgent`). Recent April 2026 production-grade write-ups describe Planner/Researcher/Writer/Critic patterns with Pydantic validation, self-consistency sampling, and critique-driven refinement loops (earezki.com 2026-04-22).
- **License:** Apache-2.0 (main `camel-ai/camel` repo). Compatible.
- **Fit:** Closer than the others — CAMEL's role-playing primitive is the closest match to "persistent role with its own memory" out of any of these — but the framework still optimizes for the two-agent "user-assistant role-play with inception prompting" loop from the original paper, not for sequential single-call stages. The Critic / RolePlayingWorkforce abstractions are interesting and overlap conceptually with what RA-? will want for the judge-stage of our pipeline, but adopting CAMEL means importing a dependency tree and a vocabulary we'd then have to translate for the judges. We can lift the *idea* (named roles with sticky personas) without taking the framework.
- **Verdict:** **skip the framework, keep the idea.**

### Generative Agents original codebase (joonspk-research)

- **Status April 2026:** *Frozen as of the 2023 paper state.* The repo (`joonspk-research/generative_agents`) has 21k+ stars, ~3k forks, ~31 commits total, no recent commits visible on the main page (per repo header), and serves primarily as the official artifact for Park et al. 2023. Issues continue to be opened in 2025 but the repo is not actively developed. There is a *separate* Stanford HCI project, `joonspk-research/genagents` (a.k.a. `StanfordHCI/genagents`), accompanying the 2024 "Generative Agent Simulations of 1,000 People" paper, MIT-licensed, also lightly maintained — different scope (survey-style agents from interviews), different code, not a successor to the Smallville simulation.
- **License:** Apache-2.0 (`generative_agents`); MIT (`genagents`). Both compatible.
- **Fit:** Don't adopt the codebase. *Do* adopt the memory architecture: **memory stream** (chronological natural-language log of all observations), **importance score** (LLM-rated 1–10 at write time), **retrieval as recency × importance × relevance with relevance via cosine similarity**, **reflection** (periodically, the agent prompts itself to summarize recent memories into higher-level "reflection" entries that are themselves stored in the stream), **planning** (translate reflections into action). For our use case we don't need planning (the orchestrator does that), and reflection only matters if we run the same agent across many runs. Memory stream + scored retrieval is ~150 lines of Python over our existing SQLite schema. The original repo is built around the Smallville Phaser game environment, has the OpenAI Chat API hardcoded, and predates async — using it would mean rewriting it.
- **Verdict:** **don't adopt; reimplement the retrieval formula natively.**

### DSPy

- **Status April 2026:** Active and mature. Stanford NLP, MIT-licensed, ~16k+ GitHub stars, ~160k monthly downloads. DSPy 3.x is the current line; 3.2.0 has been released (per PyPI / repo releases). The headline 2025–2026 development is **GEPA** (Genetic-Pareto / Reflective Prompt Evolution; Agrawal et al. 2025, arXiv:2507.19457) — a reflective optimizer that uses an LLM to read a program's execution trajectory, identify failure modes, and propose new prompts. GEPA has documented adapters for full-program optimization (signatures + modules + control flow), confidence-aware classification, and generic RAG over Chroma/Weaviate/Qdrant/Pinecone (DSPy docs; GEPA docs).
- **License:** MIT. Compatible.
- **Fit:** Different category. DSPy is not a multi-agent orchestration framework; it is a *prompt-program compiler*. You write a `Signature` (typed input/output spec) + a `Module` (strategy: `ChainOfThought`, `ReAct`, etc.); DSPy compiles that into prompts, runs them, and — given a metric and a small training set — optimizes the prompts. Adopting it for orchestration would be a category mistake. **But for our Tier-3 prompt-optimization phase, it is plausibly the right tool**: once we have a held-out set of wargaming scenarios with judge-rated outputs, GEPA can rewrite our hand-authored prompts to maximize the judge score. We'd treat DSPy as an *offline* pre-deployment step, not as a runtime dependency. The risk: DSPy's compiled prompts are machine-generated and ugly; this conflicts with the demo posture if judges look inside `src/prompts/*.md` and see optimizer artifacts. Mitigation: keep the optimized prompts in a separate `src/prompts/optimized/` directory, default the demo to the hand-authored versions, and only show optimized outputs as a "and here is what an automated prompt optimizer pushes the system toward" appendix slide.
- **Verdict:** **partial adopt — keep in reserve for Tier 3, do not put on the runtime hot path.**

## Recommended approach

**Build a thin custom orchestrator. Reuse one idea, reserve one tool.**

Concretely:

1. **Orchestrator** — a `Pipeline` class in `src/pipeline/orchestrator.py` that takes an ordered list of stage callables and runs them sequentially with `asyncio.run`. ~50 lines. No DAG library. No state-graph library. Each stage is a plain `async def stage(ctx: RunContext) -> StageResult` function. This is the "show your work" surface: judges look at this file and immediately see the five stages.

2. **LLM calls** — every stage calls `src/llm/wrapper.py::logged_completion()`, which wraps `litellm.acompletion`. The wrapper hashes the prompt-file blob with `git hash-object`, records `prompt_version`, the model name, token counts, latency, and the full request/response into the SQLite audit log. This is non-negotiable per house rules and trivial to write — ~80 lines including the SQLite insert.

3. **Memory** — each agent role gets a row in a `memory` table keyed by `(role, run_id, seq, kind)` with the natural-language entry, a timestamp, an `importance` score (LLM-rated at write time, 1–10, prompt cribbed from Park et al. 2023 §4.1), and an embedding column. Retrieval scores rows as `α·recency + β·importance + γ·relevance` with `recency = exp(-Δt/τ)`, `importance = score/10`, `relevance = cosine(query_embedding, row_embedding)`. This is the Park et al. retrieval formula, ~150 lines, no external dependency beyond `sentence-transformers` (already in our stack for Chroma).

4. **Doctrine RAG** — already pinned to ChromaDB in the spec. Stages that should retrieve doctrine call a `doctrine.retrieve(query, k=5)` helper. The off-distribution generator stage explicitly skips this call (per house rules — its job is to escape the gap, not stay in it).

5. **Reflection** — out of scope for the hackathon. The reflection-into-the-memory-stream loop only pays off across many runs of the same agent; we are doing one run per scenario in the demo. Stub the function, don't wire it.

6. **Streamlit UI** — render each stage's input, prompt, raw LLM output, parsed structured output, and which memory rows / doctrine chunks were retrieved. The demo's whole point is that this is legible. A framework would hide most of this behind its own concepts.

7. **Optional Tier 3 — DSPy/GEPA prompt optimization.** Only if we land a held-out scenario set with judge ratings before the demo. Define a `dspy.Signature` per stage matching our prompt's input/output schema, run GEPA against a metric derived from judge scores, and store the optimized prompts as siblings to the hand-authored ones. Disabled in the default demo flow.

Total custom code budget: pipeline + wrapper + memory + RAG hook ≈ 400–500 lines. That is less than the integration cost of any of the six frameworks evaluated.

## If we DID adopt one, which would it be?

Reluctantly, **CAMEL**. Apache-2.0, the role-playing primitive maps closest to "persistent role with own memory," and the recent production-grade Planner/Researcher/Writer/Critic patterns described in the April 2026 community write-ups are at least the right *shape* even if not the right *call pattern* for our pipeline.

Second choice: **AG2** (the AutoGen fork), Apache-2.0, backward-compatible with the v0.2 API that the multi-agent literature is written against, independent of Microsoft's Agent Framework rebrand. It would still be wrong-shape (conversational), but at least it isn't trapped in Microsoft's branding churn.

**Avoid LangGraph**, even as second-best. The abstraction tax compounds against the demo posture: every layer between the judge's eye and the prompt is a layer the judge can't see. AutoGen original is dead-end (maintenance mode, replaced by Microsoft Agent Framework 1.0). CrewAI's Crew/Task vocabulary is a poor narrative match for "deliberately off-distribution red team."

## Bibliography

- [microsoft/autogen — GitHub repo](https://github.com/microsoft/autogen) — AutoGen original codebase (now in maintenance mode).
- [AutoGen v0.4: Reimagining the foundation of agentic AI (Microsoft Research Blog, Jan 2025)](https://www.microsoft.com/en-us/research/blog/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/) — the v0.4 rewrite announcement.
- [Migration Guide v0.2 → v0.4 — AutoGen docs](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/migration-guide.html) — concrete API differences.
- [Microsoft retires AutoGen and debuts Agent Framework — VentureBeat](https://venturebeat.com/ai/microsoft-retires-autogen-and-debuts-agent-framework-to-unify-and-govern) — Microsoft's October 2025 consolidation announcement.
- [Microsoft Ships Production-Ready Agent Framework 1.0 — Visual Studio Magazine, April 2026](https://visualstudiomagazine.com/articles/2026/04/06/microsoft-ships-production-ready-agent-framework-1-0-for-net-and-python.aspx) — 1.0 release timing.
- [Microsoft Agent Framework Overview — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/overview/) — official docs.
- [ag2ai/ag2 — GitHub repo](https://github.com/ag2ai/ag2) — the community fork formerly AutoGen.
- ["Microsoft Autogen Has Split in 2... Wait 3... No, 4 Parts" — DEV.to (Maxim Saplin)](https://dev.to/maximsaplin/microsoft-autogen-has-split-in-2-wait-3-no-4-parts-2p58) — the clearest summary of the AutoGen / v0.4 / AG2 / Agent Framework split.
- [crewAIInc/crewAI — GitHub repo](https://github.com/crewaiinc/crewai) — main CrewAI repo.
- [crewAI/LICENSE — MIT](https://github.com/crewAIInc/crewAI/blob/main/LICENSE) — license confirmation.
- [CrewAI documentation — Introduction](https://docs.crewai.com/en/introduction) — Crew/Task/Flows abstractions.
- [CrewAI — Wikipedia](https://en.wikipedia.org/wiki/CrewAI) — adoption numbers, Enterprise launch history.
- [langchain-ai/langgraph — GitHub repo](https://github.com/langchain-ai/langgraph) — LangGraph core.
- [LangGraph LICENSE — MIT](https://github.com/langchain-ai/langgraph/blob/main/LICENSE) — license confirmation.
- [LangGraph overview — LangChain docs](https://docs.langchain.com/oss/python/langgraph/overview) — StateGraph model.
- ["Why Are Developers Quitting LangChain?" — UpGrad 2026](https://www.upgrad.com/blog/why-are-developers-quitting-langchain/) — synthesis of debugging / abstraction complaints.
- ["Stop Confusing LangChain, LangGraph, and Deep Agents" — DEV.to](https://dev.to/optyxstack/stop-confusing-langchain-langgraph-and-deep-agents-a-practical-playbook-for-building-real-ai-4f52) — abstraction-tier criticism of LangGraph specifically.
- [camel-ai/camel — GitHub repo](https://github.com/camel-ai/camel) — main CAMEL repo.
- [CAMEL LICENSE — Apache-2.0](https://github.com/camel-ai/camel/blob/master/LICENSE) — license confirmation.
- [Li et al. 2023 — CAMEL: Communicative Agents for "Mind" Exploration of LLM Society](https://arxiv.org/abs/2303.17760) — original CAMEL paper.
- ["Designing Production-Grade Multi-Agent Systems with the CAMEL Framework" — earezki.com 2026-04-22](https://earezki.com/ai-news/2026-04-22-how-to-design-a-production-grade-camel-multi-agent-system-with-planning-tool-use-self-consistency-and-critique-driven-refinement/) — current April 2026 production patterns.
- [joonspk-research/generative_agents — GitHub repo](https://github.com/joonspk-research/generative_agents) — Park et al. 2023 Smallville codebase, Apache-2.0, frozen at paper state.
- [Park et al. 2023 — Generative Agents: Interactive Simulacra of Human Behavior (UIST 2023)](https://dl.acm.org/doi/fullHtml/10.1145/3586183.3606763) — the memory-stream / retrieval / reflection / planning architecture.
- [joonspk-research/genagents — GitHub repo](https://github.com/joonspk-research/genagents) — separate StanfordHCI 2024 "1,000 People" project, MIT, distinct codebase.
- [stanfordnlp/dspy — GitHub repo](https://github.com/stanfordnlp/dspy) — DSPy main repo.
- [DSPy LICENSE — MIT](https://github.com/stanfordnlp/dspy/blob/main/LICENSE) — license confirmation.
- [DSPy Optimizers documentation](https://dspy.ai/learn/optimization/optimizers/) — MIPROv2, BetterTogether, GEPA, SIMBA.
- [DSPy GEPA Reflective Prompt Optimizer — overview](https://dspy.ai/api/optimizers/GEPA/overview/) — the 2025–2026 GEPA optimizer.
- [Agrawal et al. 2025 — GEPA: Reflective Prompt Evolution Can Outperform RL (arXiv:2507.19457)](https://arxiv.org/abs/2507.19457) — GEPA paper.
- [DSPy releases — 3.2.0](https://github.com/stanfordnlp/dspy/releases/tag/3.2.0) — current release line.
