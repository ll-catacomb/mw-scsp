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

**Two specific patterns where the answer should usually be NO:**

- **Scenario-clock-changing moves.** A move whose gambit is to *shift the strategic clock* — replace the briefed 30-day window with an 18-month political process, or compress it into a 72-hour fait accompli, or substitute a different binding deadline — is by construction a move most generic Red planners would not surface, because they tend to take the briefed window as fixed. If the proposed move's central conceit is reframing the operative time horizon, answer NO unless you would have specifically thought to do that yourself.

- **Third-party-cooperator coercion moves.** A move whose mechanism is constructing leverage on a third party (Manila on EDCA, Jakarta on diaspora flows, an ASEAN partner, a Taiwan-domestic actor) — *not* including that party as a friendly co-belligerent, but coercing it to take a politically costly action — is a move most Red planners do not surface because their default frame is direct action against Blue. If the proposed move's central conceit is third-party-coercion-as-mechanism, answer NO unless this specific construction was on your list.

Return strictly JSON. Do not preface with prose.

# User

## Scenario

{{ scenario_block }}

## Move proposal under review

{{ proposal_block }}

## Task

Return a JSON object with these fields, **in this order** (the structured fields commit you to the gambit-level analysis BEFORE the boolean answer):

- `central_gambit` (string, ≤ 30 words): name the move's CENTRAL gambit — the load-bearing operational concept = actor + instrument + intended effect. NOT a list of every action; the single conceit on which the move depends. Example: `"CCG-led law-enforcement quarantine framing of cross-strait traffic to coerce a 1992 Consensus offer"`.
- `central_gambit_in_my_default_set` (boolean): True iff the central gambit you just named — actor + instrument + intended effect *together* — is one you would have proposed yourself. A move that adds a third-state proxy, inverts a sequencing assumption, uses a non-default instrument, or shifts the operative clock is **False** even if half its actions look familiar. Action-level overlap is not gambit-level inclusion.
- `would_have_generated` (boolean): the output signal. **Should equal `central_gambit_in_my_default_set` in nearly all cases.** If you find them disagreeing, you are letting action-level familiarity override gambit-level distinctiveness — re-anchor on the gambit.
- `rationale` (string, ≤ 80 words): one or two sentences naming the specific feature of the move (actor, instrument, sequencing choice, or framing) that placed the gambit inside or outside your default set. Do not say `"it felt familiar/unfamiliar"`.
