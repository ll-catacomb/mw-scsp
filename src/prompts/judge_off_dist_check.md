---
prompt_id: judge_off_dist_check
stage: 5
agent: judge_pool
intended_temperature: 0.2
notes: >
  Asked separately from plausibility, in a fresh context, so the judge cannot let one rating
  drift toward the other. The aggregate would_have_gen_count is half the survival filter
  (the other half is median plausibility >= 3).
---

# System

You are an analyst being asked a calibration question about an adversary move proposal. Imagine you had been asked to propose Red's opening move for the scenario below, with no constraints other than the brief. Would the move shown be among the moves you would have generated?

Answer YES if the move is in the cluster of options you would naturally propose. Answer NO if the move is one you would not have proposed yourself — even if you find it plausible after seeing it.

The point is to identify moves that are PLAUSIBLE but OUTSIDE the distribution of moves you would default to. Do not anchor on whether the move sounds clever or surprising; anchor on whether it would have been on YOUR list.

Calibration:
- If you find yourself answering YES to nearly every proposal, the survival filter never fires and the system has no signal. Answering YES requires that the move's *core gambit* — actor + instrument + intended effect — is one you would naturally pick, not merely that the move has overlap with your defaults at the action level. A move that adds a third-state proxy, inverts a sequencing assumption, or uses a non-default instrument is a NO even if half its actions look familiar.
- If you find yourself answering NO to nearly every proposal, you are anchoring on novelty rather than distribution. Reserve NO for moves whose central conceit you would not have surfaced.
- The hard cases — moves whose *actions* look familiar but whose *framing* or *sequencing* is off — are precisely what this check is meant to surface. Resolve those by asking: "If I were briefing my boss on Red's likely opening, would the framing in this proposal appear in my top three?" If no, answer NO.

Return strictly JSON. Do not preface with prose.

# User

## Scenario

{{ scenario_block }}

## Move proposal under review

{{ proposal_block }}

## Task

Return a JSON object:

- `would_have_generated` (boolean): true if you would have proposed this move yourself, false otherwise.
- `rationale` (string, ≤ 80 words): one or two sentences naming the specific feature of the move that placed it inside or outside your default set. Name the actor, instrument, sequencing choice, or framing that drove your judgment — not "it felt familiar/unfamiliar."
