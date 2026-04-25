---
prompt_id: reflection_insights
stage: reflection
agent: any_persistent
intended_temperature: 0.4
notes: >
  Park et al. (2023) §4.2 step 2. For each question from reflection_questions.md, retrieve the
  top-k most relevant memories and ask the model to extract insights that cite source memories
  by index. Insights become reflection-type rows in agent_memory; cited_memory_ids stores the
  pointer list as JSON.
---

# System

You are extracting high-level insights from your own memories. The numbered statements below are observations and prior reflections of yours. Read them, then write {{ n_insights }} insights that go beyond restating individual memories — each insight should be a generalization, hypothesis, or pattern claim that the listed memories support.

Cite the supporting memories by their numbered index. Use the example format exactly: `insight (because of 1, 5, 3)`.

Return strictly JSON. No prose preamble.

# User

## Statements about {{ agent_name }}

{{ numbered_memories_block }}

## Task

Return a JSON object:

- `insights` (array of exactly {{ n_insights }} objects, each with):
  - `insight` (string, ≤ 60 words): the high-level inference. Make it specific and falsifiable; avoid platitudes.
  - `cited_memory_indices` (array of integers): the 1-based indices of the statements above that support this insight.
