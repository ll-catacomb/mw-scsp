---
prompt_id: importance_score
stage: memory_creation
agent: any_persistent
intended_temperature: 0.0
notes: >
  Asked at memory-creation time; the integer is stored alongside the memory and used in
  retrieval scoring. Adapted from Park et al. (2023) §4.1 for our adversary-planning domain.
---

# System

You are rating the significance of a single memory item to an analyst working on adversary-planning red-team analysis. Use the scale below.

- 1 — A routine observation (e.g., standard ISR posture, scheduled exercise, generic doctrine restatement).
- 5 — A meaningful but expected observation (e.g., a new modal cluster, a judge consensus that confirms expectations).
- 10 — A doctrine-violating off-distribution move that fundamentally changes the strategic calculus, OR a reflection that names a recurring model-wide blind spot.

Return strictly JSON. No prose preamble.

# User

## Memory

{{ memory_text }}

## Task

Return a JSON object:

- `rating` (integer, 1–10): your importance score.
