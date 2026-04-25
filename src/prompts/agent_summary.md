---
prompt_id: agent_summary
stage: agent_summary_cache
agent: any_persistent
intended_temperature: 0.3
notes: >
  Park et al. (2023) Appendix A. Three queries are run separately (core disposition / recent
  focus / observed blind spots), retrieved memories are pulled for each, and the three answers
  are concatenated into the cached summary stored in agent_summary. The summary is prepended
  to many of the agent's prompts. Regenerate every 3 runs or whenever a new reflection lands.
---

# System

You are writing one paragraph that summarizes the analytical character of a persistent agent in a red-team system. The agent is `{{ agent_name }}`. Its role is `{{ agent_role }}`. The memories below are its most relevant prior observations and reflections for the query at the bottom.

Write a tight paragraph (≤ 80 words) that answers the query directly, drawing on the memories. Do not invent attributes the memories do not support. If the memories are too sparse to answer, say so.

Return strictly JSON. No prose preamble.

# User

## Memories (top-k retrieved for this query)

{{ memories_block }}

## Query

{{ query }}

## Task

Return a JSON object:

- `paragraph` (string, ≤ 80 words): the answer. Direct, specific, citation-free.
