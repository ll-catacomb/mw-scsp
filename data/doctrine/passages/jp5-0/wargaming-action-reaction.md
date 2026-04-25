---
id: jp5-0-wargaming-action-reaction
source: JP 5-0
edition: "2020"
section: "Ch. III — Course of Action Analysis and Wargaming, Step 4"
page: III-30 to III-32
type: procedure
priority: high
topics:
  - wargaming
  - coa-development
  - red-cell
  - adversary-modeling
  - off-distribution
keywords:
  - wargaming
  - action reaction counteraction
  - most probable
  - most dangerous
  - red cell
  - role-play
  - role play the adversary
  - critical event
synonyms:
  - templated adversary
  - jipoe coa
  - red team cell
  - adversary coa
applies-to:
  - adjudication
  - off-distribution-flag
related:
  - jp5-0-never-assume-away
  - jp5-0-coa-screening
notes: |
  This is the doctrinal bedrock of templated adversary modeling. Retrieve when
  classifying a Red move as "in the JIPOE-derived COA set" vs. "outside it" —
  off-distribution Red moves are by definition outside, and the audit log should
  record that fact.
---

# COA Analysis and Wargaming (Step 4) — JP 5-0, III-30 to III-32

> "...the commander should wargame each tentative COA against the **most probable and the most dangerous adversary COAs**... identified through the JIPOE process."
>
> *(JP 5-0, III-30 to III-31)*

> "Each critical event within a proposed COA should be wargamed based upon time available using the **action, reaction, counteraction** method of friendly and/or opposition force interaction."
>
> *(JP 5-0, III-31)*

> "A robust cell that can aggressively pursue the adversary's point of view when considering adversary counteraction is essential. This **'red cell' role-plays the adversary commander and staff**... **By trying to win the wargame for the adversary**, the red cell helps the staff fully address friendly responses for each adversary COA."
>
> *(JP 5-0, III-31)*

## Why this is in the corpus

This passage is the thing the project is reacting against. Wargaming Step 4 reduces the adversary COA space to a binary — *most probable* / *most dangerous* — and proceeds in a fixed action → reaction → counteraction cadence with the red cell trying to win inside the COA set already produced by JIPOE. Off-distribution Red moves are, by definition, *not* in that set and *not* counteractions in a Blue-initiated cadence. An opening fait-accompli or a non-kinetic legal-fiction move escapes the action-reaction-counteraction grammar entirely.

The Blue adjudicator should retrieve this passage to flag when a Red move has slipped the doctrinal frame, and the audit log should record the gap as `would_have_required_revising_jipoe_coa_set`. This is the single most useful passage in the corpus for the off-distribution-flag stage.
