---
prompt_id: reflection_questions
stage: reflection
agent: any_persistent
intended_temperature: 0.4
notes: >
  Park et al. (2023) §4.2 step 1 — generate questions from the recent memory window. Step 2 is
  reflection_insights.md. Run at end-of-pipeline-run when sum of unreflected importance crosses
  the threshold (start at 50; tune from there).
---

# System

You are reasoning over your own recent memories to identify high-level patterns. The memories below are observations and prior reflections from your work as a {{ agent_role }}. Your task is to surface the most salient questions whose answers would deepen your understanding of those patterns.

Do not summarize. Do not narrate. Generate questions that, if answered well, would expose a structural feature of the memories.

Return strictly JSON. No prose preamble.

# User

## Recent memories ({{ n_memories }} most recent)

{{ memories_block }}

## Task

Return a JSON object:

- `questions` (array of exactly 3 strings): the three most salient high-level questions you can answer about the patterns in these memories. Each question should be specific enough that two thoughtful analysts looking at the same memories would converge on a similar answer.
