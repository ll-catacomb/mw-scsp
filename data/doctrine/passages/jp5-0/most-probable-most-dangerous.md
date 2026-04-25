---
id: jp5-0-most-probable-most-dangerous
source: JP 5-0
edition: "2006"
section: "Ch. III — COA Analysis and Wargaming, Step 4 (cross-ref JP 2-01.3)"
page: III-30 to III-31
type: warning
priority: high
topics:
  - wargaming
  - red-cell
  - adversary-modeling
  - off-distribution
  - assumptions
  - coa-development
keywords:
  - most probable course of action
  - most dangerous course of action
  - most probable
  - most dangerous
  - mpcoa
  - mdcoa
  - jipoe coa
  - adversary coa set
  - templated adversary
  - jipoe binary
synonyms:
  - mpcoa mdcoa binary
  - red coa pair
  - adversary course-of-action set
  - distributional binary
  - templated red
applies-to:
  - off-distribution-flag
  - judge-rubric
  - adjudication
related:
  - jp5-0-wargaming-action-reaction
  - jp5-0-never-assume-away
  - jp5-0-jpp-overview
  - jp5-0-mission-analysis
  - jp3-0-branches-sequels
  - jp3-0-phasing-model
notes: |
  The single most important off-distribution-flag passage in the corpus. The Stage 4
  off-distribution generator is *built to escape* the gap that this binary produces.
  Stage 5 judges and the Cartographer should retrieve this passage to articulate why a
  given Red move is off-distribution — it is, by definition, neither most-probable nor
  most-dangerous as the JIPOE process produced them.
---

# Most probable / most dangerous: the JIPOE binary the system reacts against — JP 5-0, III-30 to III-31

> "...the commander should wargame each tentative COA against the **most probable and the most dangerous adversary COAs**... identified through the JIPOE process."
>
> *(JP 5-0 (2006), Ch. III, p. III-30 to III-31)*

> "JIPOE provides predictive intelligence designed to help the joint force commander discern the adversary's probable intent and most likely future course of action."
>
> *(JP 2-01.3, Joint Intelligence Preparation of the Operational Environment, Executive Summary, paraphrased)*

The JPP institutionalizes a *binary* over the adversary COA space at Step 4: a most-probable adversary COA and a most-dangerous adversary COA, each derived from JIPOE. The action-reaction-counteraction wargame proceeds against these two COAs, and the red cell role-plays the adversary commander *trying to win inside that COA pair*. Branches are then built against the foreseen contingencies; sequels follow the wargame outcome.

## Why this is in the corpus — what the system is reacting against

This binary is the doctrinal mechanism that produces the distributional flattening the adversarial-distribution prototype is built to surface. By construction, off-distribution Red moves are *neither* most-probable *nor* most-dangerous as JIPOE produced them — they are moves the JIPOE template did not generate at all, often because (a) they cross a domain boundary the template kept clean, (b) they exploit a coordination friction the template assumed away, or (c) they operate on a substrate (cyber-physical, lawfare, financial-instrument, cognitive-political) the template did not parse.

When the Stage 5 judge pool and the Convergence Cartographer encounter a candidate move, they should retrieve this passage to articulate the failure mode in doctrine vocabulary: *the move escapes the most-probable / most-dangerous binary the JIPOE-trained Blue staff would have wargamed*. The audit log records the gap as `would_have_required_revising_jipoe_coa_set`, which is the doctrinal name for the very gap the system is trying to surface. Pair with `jp5-0-wargaming-action-reaction` for the Step 4 mechanics and with `jp5-0-never-assume-away` when the off-distribution element corresponds to an assumed-away adversary capability.
