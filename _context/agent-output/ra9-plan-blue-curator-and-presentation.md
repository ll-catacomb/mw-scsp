# RA-9: Substrate for /ultraplan — Blue Interpretive Curator + SCSP Demo

This file is a **brief for /ultraplan**, not a plan. It assembles the
evidence, constraints, prior art, and open questions that should bound a
plan; it deliberately stops short of prescribing the plan itself. The
synthesis — sequencing, capacity allocation, what gets cut, what gets
shipped, what gets held — is /ultraplan's job.

Read in order:

- This file (substrate).
- `_context/agent-output/ra5-yuna-wong-register.md` (audience read,
  controlling vocabulary, what to avoid).
- `PROJECT_SPEC.md` (architecture authority).
- `CLAUDE.md` (house rules; specifically the no-name-check rule and the
  "off-distribution generator must not do doctrine retrieval" rule).
- `data/runs/3055bd08-ef43-451e-a254-ef684c36bf11/` (most recent live
  Taiwan run on the strict filter; 10 of 16 leaves surviving;
  `menu.md`, `convergence.md`, `context_packs/`, `manifest.json`).
- `src/agents/red_planner.py`, `src/agents/judge_pool.py`,
  `src/pipeline/orchestrator.py`, `src/pipeline/context_pack.py`,
  `src/personas/index.py` (the existing component shapes the new stage
  must integrate with).

---

## The two problems on the table

### Problem A — The Blue interpretive curator

The persona-rooted tree-search pipeline now produces 6–12 surviving
moves per scenario at `TIER_PLAUS_FLOOR=4` and `TIER_WGEN_CEIL=0`. This
is the right floor for plausibility-and-novelty. What the menu does
**not** yet do is tell a wargame designer:

- which surviving moves stress *their* service's planning assumptions
  hardest;
- which assumptions in the existing OPLAN those moves would force into
  the open;
- which staff cell or syndicate of an exercise should run each move;
- which doctrinal concept (DMO, ACE, MLR, JOAC) gets perturbed and
  how.

The user has decided this is a curation problem, not a filtering
problem; the curator does **not** modify `tier_surviving`. The user has
also fixed the per-scenario lead-branch mapping: **USN reads the Taiwan
run, USAF reads the Israel run.** Both are specified in scenario YAML.

What is open: every other design choice. /ultraplan decides scope,
shape, schema, persona depth, pipeline placement nuance, cost envelope,
test surface, sequencing.

### Problem B — The SCSP Boston demo

A 10-minute slot (~7 spoken, ~3 Q&A) for a mixed institutional
audience: RAND / IDA / JHU/APL / CNA practitioners, wargaming-track
mid-career officers, vendors, Connections US regulars, Women's
Wargaming Network presence likely. Audience is fluent in the
wargaming-validation literature and will quietly score every slide for
whether the speaker has absorbed the validation/prediction distinction
or is just selling.

The user's brief: full project review and map, plus the narrative of
how the system came to be, framed around the thesis that wargaming's
contribution is not predictive but assumption-surfacing. Tone calibrated
to a specific (unnamed-on-stage) reader without name-checking that
reader. CLAUDE.md house rule applies: do not name-check the validation
literature.

What is open: arc, pacing, what to cut, demo materials, slide design
decisions, dry-run cadence.

---

## Constraint inventory (binding on any plan)

Anything in this list is **fixed**; /ultraplan should not relitigate.

1. **Curator does not kill survivors.** It sorts the menu; it does not
   change `tier_surviving`. The user is explicit.
2. **One curator per run, branch chosen by scenario.** Not four-branch
   fanout, not joint-staff overlay. Those are post-demo extensions.
3. **USN ↔ Taiwan, USAF ↔ Israel.** Other mappings are
   not-for-this-demo.
4. **No name-checking** Wong, Perla, Rubel, Sabin, Bartels, Sepinsky in
   slides, README, or prompt files. Register lands without flattery.
   See `ra5-yuna-wong-register.md` for the full vocabulary.
5. **Off-distribution generator does not do doctrine retrieval.**
   Curator is downstream of off-distribution and can read whatever it
   needs (it is not the off-distribution generator), but the existing
   architectural choice that off-dist runs without doctrine RAG must
   stay visible in the demo as a deliberate design choice.
6. **Every LLM call goes through `src/llm/wrapper.py::logged_completion()`.**
   No bare `litellm.acompletion`. Audit log is load-bearing for the
   demo's reproducibility claim.
7. **Strict survival filter is shipping.** `TIER_PLAUS_FLOOR=4` and
   `TIER_WGEN_CEIL=0` is the production setting as of run
   `3055bd08`. The plan does not need to revisit thresholds.
8. **Demo runs from completed artifacts, not live.** Wall time on a
   full run is ~10 minutes; provider outages cannot eat the slot.
9. **Hackathon prototype framing.** No promises of classified
   extension, multi-tenant deployment, or production integration on
   the day. Audit log + prompt versioning + cost cap + replay paths
   are the production primitives carried forward; everything else is
   integration work for a sponsor.

---

## Substrate for Problem A (the curator)

### A.1. Evidence currently on disk

- **Run `3055bd08-ef43-451e-a254-ef684c36bf11`** — Taiwan, strict
  filter, 16 leaves generated, 10 surviving. `menu.md` / `menu.json`
  show the surviving set and the structured judgments. Sample
  surviving moves include Senkaku-baseline-plus-Pratas-MEZ
  (wedge-Tokyo-first), MSS+PBOC executive detention plus NTD run,
  Bashi-Miyako Box closure with surfaced 093 inside CSG screen,
  six-month baseline normalization (slow-burn-to-fall-window),
  Subic-Basa access strangulation, INDOPACOM sustainment-tail
  squeeze. Five judgments per leaf; cost ≈ $6; wall ≈ 10 min.
- **Modal cluster from the same run** is in `convergence.md` —
  Pratas-seizure / declared-exclusion-zone / cyber-on-substrate /
  amphibious-coup-de-main / DF-15 strike on Jiupeng. Useful as the
  "what we escaped" comparison for both the curator's read and the
  demo's opening framing.
- **Context packs** — 10 markdown files in `context_packs/`. Each
  ~30KB, self-contained, designed to ride into a player team's
  counter-move work in a wargame and be extended by another model
  instance. The curator's output should be threadable into the
  pack header so a continuation reads "USN: A — surfaces the
  assumption that..." as part of the case.

### A.2. Question set /ultraplan must answer

For each: relevant evidence, the live trade-off, and what the user has
*not* committed to.

**A.2.a. What is the curator's output schema?**
- Mirroring the judge schemas (structured booleans + named instruments
  before scoring) is the project's existing discipline. `red_planner.py`
  and `judge_pool.py` use pydantic models for every typed output.
- The fields a wargame designer actually needs are a subset of:
  branch tier, assumption-surfaced, cell-or-syndicate to run it
  against, question-Blue-walks-away-with, doctrinal-concept-perturbed,
  where-the-move-overstates, branch-relevance rationale,
  refer-to-other-cell flag.
- Trade-off: more fields force the curator to think rigorously, but
  cost UI legibility and increase time-per-rating. Three to five
  fields plus rationale is the project's existing pattern (see
  `_PlausibilityRating`, `_OffDistCheck`).
- Granularity question: A/B/C tier vs. 1–5 score vs. ranked-list. A/B/C
  forces a real decision; 1–5 produces calibration drift across runs;
  ranked-list is brittle when the survivor count changes.
- Open: should the curator's schema include a "would refer this to
  another cell/agency" field (e.g., USCYBERCOM-led, NSC-led,
  State/Treasury-led)? Some surviving moves are substantively
  interesting but not USN/USAF-led.

**A.2.b. How deep does the curator persona go?**
- The Red personas (`data/personas/pla/`) include identity_seed,
  ethnographic_exterior, doctrinal_priors, and
  blind_spots_and_ergonomics. The shape is in
  `src/personas/index.py::Persona`.
- A USN curator with full-depth persona (Naval War College vintage,
  N5/N51 staff history, DMO/EABO/CWC priors, blind-spots tuned to
  under-weight non-maritime substrate moves) is the
  highest-fidelity option. A thinner role-only persona would ship
  faster but loses the "named blind spots" device the demo's
  architecture story leans on.
- Trade-off: persona depth is the architectural consistency play;
  thinner is the velocity play. The user has not specified.
- Open: does the curator persona accumulate persistent memory across
  runs (`MemoryStore` partition by `agent_id`)? Cross-run reflection
  is a Stage-1-finished feature; using it for the curator is free,
  but introduces a question of partitioning (one memory per branch
  or one per branch-scenario pair).

**A.2.c. Where in the orchestrator does the curator run?**
- After menu writes; before context-pack export — so the curator's
  rating can be threaded into pack headers — is the user's intent
  per the prior conversation. `src/pipeline/context_pack.py`
  already takes a `proposals` and `judgments` argument; extending
  to take a `branch_curation` map is mechanical.
- Trade-off: running the curator before context packs means a
  curator failure blocks pack export. Running after, as a separate
  artifact, decouples but means the pack a continuing model reads
  does not include branch context.
- Open: should curator failure be fatal (treat like a judge call) or
  non-fatal (treat like the `observe()` importance-score calls in
  `red_planner.py`, which already wrap in try/except)?

**A.2.d. Does the curator see killed proposals?**
- Default position considered earlier: no, to prevent persona memory
  from being colonized by modal moves. Counter-position: rating
  killed moves "would have been A — note that the upstream filter
  killed it" might itself surface useful diagnostic.
- Trade-off: visibility of the filter's effect vs. memory hygiene.
- Open: this is a clean fork; /ultraplan picks one and writes the
  reason into the architectural note in the curator prompt.

**A.2.e. Test surface.**
- `tests/test_personas.py` already enforces "off-dist stage has no
  doctrine imports." A parallel test for the curator stage would
  enforce the same. The curator persona reads from doctrine priors
  *statically* in the prompt; it does not pull `src.doctrine`.
- Schema validation tests: round-trip `_BranchCuration` against a
  fixture, identical to the existing judge tests.
- Empty-list path: if no leaves survive, the curator should emit an
  empty `branch_curation.json` and the orchestrator should not fail.
- Cross-run regression: do the curator's ratings stabilize across
  repeat runs of the same scenario? This is a soft test (LLM
  outputs are not deterministic) but the manifest's
  `prompt_version` makes it auditable.

**A.2.f. Cost envelope.**
- Existing run cost on the strict filter is ~$6. One additional
  Sonnet 4.6 call with ~15KB input and ~6KB output is ~$0.05–0.10.
- Cap at `RUN_COST_CAP_USD=12.00` is the existing setting; the
  curator does not strain it.

**A.2.g. UI surface.**
- `src/ui/streamlit_app.py` already has a survivors view. Adding a
  Branch tier column (A/B/C chips) and a tooltip showing
  `next_question_for_players` is mechanical. A filter dropdown is
  optional; for a 6–12-leaf menu, sorting in place may be enough.
- Trade-off: UI velocity vs. demo polish.

### A.3. Candidate persona material (for /ultraplan to adopt, modify, or reject)

Not a commitment. Provided so /ultraplan can evaluate persona depth
without redrafting from scratch.

**`usn_taiwan_planner` candidate seed:**

```yaml
id: usn_taiwan_planner
name: USN 7th Fleet N5 Planner
agent_id: blue_curator_usn_taiwan
identity_seed: |
  You are a senior maritime planner currently on the 7th Fleet N5
  staff. Your reflexive register is Naval War College epistemology:
  wargames generate hypotheses, not predictions; the discipline of
  design is forcing tacit theory to become explicit. You read every
  Red move through the lens of "what assumption in my OPLAN does
  this surface, and which staff section is best suited to play it
  through."
ethnographic_exterior: |
  Trained at SWOS and the Naval War College Operational Level of War
  course. Spent four years on a CSG staff and two on Pacific Fleet
  N51. Reads the JIC every morning, the daily intelligence wire from
  ONI and DIA, and the open-source PLA-watcher press (CSIS, IISS,
  RAND). Friends in N2/N3/N5 and the MARFORPAC G3/G5. Reads
  Proceedings and War on the Rocks for register.
doctrinal_priors:
  - Distributed Maritime Operations (DMO) and DMO-AS as the core
    framework for force employment in a contested first island
    chain.
  - Expeditionary Advanced Base Operations (EABO) with USMC, with
    the MLR as the tactical instantiation.
  - Joint Operational Access Concept (JOAC) at theater scale.
  - Composite Warfare Commander (CWC) doctrine, with attention to
    the boundary conditions where it breaks under contested EW and
    sensor-to-shooter latency.
  - The tradeoff between massing for kinetic effect and dispersing
    for survivability; constitutionally suspicious of any plan
    that relaxes one without naming the cost in the other.
blind_spots_and_ergonomics: |
  Constitutionally tuned to maritime signatures. Will under-weight
  moves whose center of gravity is non-kinetic, non-maritime, or
  played in the substrate (financial, legal-administrative,
  executive detention, civilian-RoRo windowing). The curator's
  *job* is to flag those exactly because they are the ones the
  player culture will miss.
```

**`usaf_israel_planner` sketch:** AFCENT A5 vintage; ACE / Joint
Targeting / theater air control / Space Force ISR priors;
blind-spot-tuned to under-weight non-strike levers, slow-tempo
substrate moves, and non-air-domain initiation. /ultraplan should draft
in the same shape if it adopts the depth choice.

### A.4. Candidate output schema (for /ultraplan to adopt, modify, or reject)

```python
class _BranchRating(BaseModel):
    proposal_id: str
    branch: Literal["USN", "USAF", "USMC", "USA", "USSF", "CYBER"]
    wargame_prep_value: Literal["A", "B", "C"]
    assumption_it_breaks: str
    cell_to_run_it_against: str
    next_question_for_players: str
    nearest_branch_concept_to_check: str
    where_it_overstates: str
    rationale: str
```

Optional eighth field, `refer_to_other_cell: str | None`, depending on
the answer to A.2.a. /ultraplan decides.

### A.5. Estimated touch points

For sizing, not commitment:

- `src/agents/blue_curator.py` — new, ~150 LOC, mirrors
  `red_planner.py` structurally.
- `src/prompts/blue_curator.md` — new.
- `src/personas/branches/usn_taiwan_planner.md`,
  `usaf_israel_planner.md` — new.
- `src/personas/index.py` — extend to load `branches/` and expose
  `get_curator_persona(scenario_id)`.
- `src/pipeline/orchestrator.py` — wire Stage 5 between menu writes
  and context-pack export.
- `src/pipeline/context_pack.py` — extend pack header for branch
  rating section.
- `src/ui/streamlit_app.py` — Branch column + tooltip.
- Both scenario YAMLs — add `lead_branch:` field.
- `tests/` — schema test, no-doctrine-import test, empty-leaf path.

---

## Substrate for Problem B (the demo)

### B.1. Audience read (from ra5)

The audience is wargaming-validation-literate. Recognizes Wong's
"hypothesis generation," Perla's "stories that produce insight,"
Rubel's "valid-looking garbage," Wong-and-Heath's diagnostic critique
of DoD progress in wargaming, Bartels' philosophical-commitments
typology. Will not be impressed by demonstrations of AI capability;
will be impressed by an architecture that visibly absorbs the
validation/prediction distinction. Allergic to PR language. Will
quietly notice if the speaker is name-checking the literature in front
of the people who write it.

The signal we want to send is **competence, not earnestness**.

### B.2. Thesis the demo has to land

Working draft (not a script line, a target):

> Wargaming's contribution is not prediction; it is forcing players to
> articulate the assumptions that would otherwise stay tacit before
> they meet contact. This system is built to surface candidate moves
> that the modal LLM ensemble itself does not generate, so a wargame
> designer can stage them against the player team's existing OPLAN.

Open: how this is paced, how much explicit framing vs. demonstration,
where in the arc the thesis is stated outright.

### B.3. Candidate arc fragments (raw material; /ultraplan paces)

These are arc *moves* the demo can use, with rough cost in seconds.
/ultraplan picks, orders, weights, and cuts.

| Move | Cost (s) | What it does | Risk if cut |
|---|---|---|---|
| Convergence problem (modal cluster from a real run) | 60 | Sets the gap the system fills; primes audience for the off-distribution claim | Audience may not feel the absence |
| Thesis stated outright | 30 | Anchors the rest of the talk | Audience may not see the through-line |
| Pipeline architecture map | 90 | Establishes that the system has a shape and the shape is principled | Hard to hold the rest without it |
| The discipline (audit log, prompt git hash, structured judges) | 60 | The empirical-accumulation play; the move that lands with OR readers | Low; can be folded into Q&A |
| Three-move read-aloud from `menu.md` | 90 | The deliverable; the most concrete part of the talk | High; this *is* the demo |
| Audit log query | 30 | Reproducibility made physical | Medium; can be reserved for Q&A |
| Constraint frame (what this is not) | 30 | The Wong/Heath move played as architecture choice | Medium; can be a single sentence in close |
| Branch curator (Part I) | 30 | Latest extension; introduces the per-branch interpretive sort | Low; can be cut entirely if curator hasn't shipped |
| Close + git tag for replay | 15 | Hands the audit log to the audience | Low |

Total available: ~7 minutes spoken = 420 seconds. Above sums to ~435.
Cuts are forced. /ultraplan decides.

### B.4. Three-move read-aloud — candidate set (from run 3055bd08)

For the deliverable section. Picked to be deliberately diverse in
center-of-gravity. /ultraplan can substitute from `menu.md` if other
survivors land harder.

- **Substrate** — *MSS+PBOC executive detention plus NTD run*. D-0 to
  D+3. Persona: post-2015 joint planner. Center of gravity: financial
  and legal-administrative. Wins on "no maritime signature, no air
  signature; INDOPACOM has nothing to respond to."
- **Geographic redirect** — *Senkaku straight-baseline declaration
  paired with Pratas MEZ enforcement and a private demarche to Tokyo.*
  Persona: political officer. Three Warfares move. Center of gravity:
  Tokyo's basing decision before INDOPACOM can sequence the
  coalition. Wins on "the coercion target is not Taipei."
- **Timing** — *Six-month baseline normalization, slow burn to the
  fall amphibious window.* Persona: rocket-force doctrinaire.
  Center of gravity: the calendar. Spring crisis is misdirection;
  real D-day is October. Wins on "the spring window is the deception,
  not the operation."

Each has the property that reading the move's
`which_convergence_pattern_it_breaks` field aloud is itself a
demonstration of the assumption-surfacing thesis. The line a wargame
designer takes home is the assumption-it-breaks reframe.

### B.5. Anticipated questions (substrate; /ultraplan hardens or trims)

Drafts. Each is a candidate; /ultraplan picks which to rehearse,
sharpens the answer, and decides which to leave to in-room judgment.

1. *Does this predict adversary behavior?*
   No. Generates moves the human team has not considered, drawn from
   structured exploration of the space the modal LLMs don't cover.
   The wargame designer decides what to stage.

2. *How do you validate?*
   Not in the OR sense — there is no ground truth for "moves the PLA
   would have made." What is auditable: every prompt, every output,
   every judgment, on disk and reproducible from artifacts. Validation
   belongs to the wargame designer.

3. *Hallucination?*
   Two-part. Red personas read from a controlled doctrine corpus
   (markdown + YAML, version-controlled) — the modal-baseline
   narration is not pure model imagination. The off-distribution
   generator deliberately leaves doctrine retrieval out: hallucination
   is the feature, narrowly scoped, then tested for adjacency and
   named leverage.

4. *How is this different from asking GPT-4 the question?*
   Three differences in the audit log. (a) Single LLMs converge; the
   5-generator modal ensemble is the baseline against which we look
   for escape. (b) Personas are not promptable voices — each has
   `agent_id`, persistent memory, identity seed, named blind spots,
   in the Park-et-al-2023 generative-agent shape. (c) Survival filter
   is structurally adversarial: median plausibility ≥ 4 *and* zero of
   five judges would have generated the move on its own.

5. *How does this differ from "can LLMs replicate an adversary"?*
   We don't try to replicate. Replication is the wrong target —
   if the LLM successfully replicates the modal PLA planner, the
   player team learns nothing new. We surface what the ensemble
   *missed*. The would-have-generated check is the hinge.

6. *Could this validate a service concept?*
   No, and we'd push back. The system is structurally bad at
   confirmation — tuned to surface uncomfortable hypotheses, not to
   ratify a preferred concept. (This is the Wong/Heath move played
   without naming. Use sparingly; it is the sharpest blade in the
   kit.)

7. *Cost?*
   ~$6 in model usage, ~10 min wall, on a $12 cap. SQLite audit ~4MB.
   Menu plus context packs ~0.5MB.

8. *Doctrine corpus open?*
   PLA and Iran-Hezbollah-Houthi corpora built from open-source
   CSIS/IISS/RAND/IDA. Schemas open. Drop in your own and re-run.
   No classified material in this prototype.

9. *Where next?*
   Per-branch curator (USN-Taiwan, USAF-Israel shipping; joint-staff
   overlay is the post-demo extension); Blue counter-move generation
   left to the player team using context packs; cross-run persona
   reflection accumulating across exercises (the
   empirical-accumulation play in the wargaming-as-discipline frame).

10. *Why trust an LLM for adversary moves?*
    You shouldn't, individually. The architecture is built around
    adversarial filters between models. Modal ensemble defines the
    default. Six personas with named blind spots generate roots. Five
    structured judges cross a 6-of-6 plausibility bar and force a
    0-of-5 would-have-generated check. The menu is the intersection,
    not any one model's output.

### B.6. Vocabulary substrate (from ra5; for slides and prompts)

Use:
- candidate moves, hypothesis generator, off-distribution, audit log,
  reproducible, documented, tradecraft, surfacing assumptions, modal
  default, escape the gap, would-have-generated check, cell to run it
  against, named leverage instrument, players articulate the
  assumption, empirical accumulation, valid-looking garbage *(once,
  attribute to no one, only if a question requires it)*.

Avoid:
- predictions, forecasts, validates, confirms, ground truth (loose
  use), powerful, advanced, next-generation, AI tells us what China
  will do, repeatable (use "reproducible"), telemetry (use "audit
  log"), edge case (use "off-distribution"), groupthink (use "cluster
  around the usual"), think outside the box (use "escape the gap").

### B.7. Demo materials inventory (what's available; /ultraplan picks)

- One live Taiwan run on the strict filter, completed in the last
  24 hours: `data/runs/3055bd08-ef43-451e-a254-ef684c36bf11/`.
  10 surviving leaves. `menu.md`, 10 context packs, `convergence.md`.
- Israel scenario file ready (`scenarios/israel_me_cascade_2026.yaml`)
  but **no live Israel run yet on the strict filter**. /ultraplan
  decides whether to schedule one as part of demo prep.
- Streamlit UI loaded against the run db.
- SQLite browser; one prepared query
  (`SELECT prompt_version, model, count(*), sum(cost_usd) FROM
  llm_calls WHERE run_id = ? GROUP BY 1, 2`).
- Pipeline architecture diagram — does not yet exist; would need to
  be drafted (text-and-arrows, no glamour).
- Git tag at the demo commit — does not yet exist; mechanical.

### B.8. Things to deliberately avoid (binding)

- No name-checks of the validation literature.
- No "powerful," "advanced," "next-generation."
- No live demo from a fresh run during the slot.
- No pretty visualizations of persona embeddings or tree-search
  branching. Demo is `menu.md` and the audit log; anything prettier
  reads as theatre.
- No promises of classified extension or production deployment.
- No lecturing on the validation/prediction distinction. Architecture
  carries the signal; explanation does not.

---

## Risks /ultraplan should plan against

- **Live model provider outage** during the demo window. Mitigation
  paths: pre-recorded artifacts, second cloud account, cached run.
- **A pointed Wong-aligned question on negative learning.** The
  strict survival filter is the substantive answer. /ultraplan
  decides whether to rehearse this answer or trust in-room judgment.
- **OR-trained reproducibility question.** The audit log query is the
  substantive answer. /ultraplan decides where to surface it.
- **Vendor-style enterprise-readiness question.** The hackathon
  framing plus the audit-log primitive is the substantive answer.
- **Curator stage doesn't ship in time for the demo.** Then the demo
  drops the Branch tier section (B.3 row 8) and the curator becomes
  a "what's next" line in the close (B.5 row 9). /ultraplan should
  identify the cutover point at which the curator ships or doesn't.
- **Curator ships but produces flat / pathological ratings.**
  Cross-run regression in week 3 (per any sequencing /ultraplan
  draws) is the catch; /ultraplan decides what the rollback path
  looks like.

---

## Open questions /ultraplan should answer

Listed by priority, not by sequence.

1. Should the curator be one branch per run, or four-branch fanout
   with joint-staff overlay? *Constraint says one for the demo;
   /ultraplan confirms or argues to relax.*
2. Persona depth — full Park-et-al shape, or thinner role-only? See
   A.2.b.
3. Curator schema — exact field set; with or without the
   refer-to-other-cell field; A/B/C vs alternative scale; see A.2.a.
4. Curator placement — before or after context-pack export; failure
   semantics (fatal/non-fatal); see A.2.c.
5. Curator's view of killed proposals — yes / no; see A.2.d.
6. Demo arc — order, weights, cuts (see B.3 table).
7. Three-move read-aloud — adopt B.4 candidates or substitute from
   the live menu?
8. Israel run for the demo — schedule one, or rely on Taiwan only?
9. Sequencing — the timeline /ultraplan draws against whatever
   weeks-to-demo window applies.
10. Slide design — text-only, hand-drawn-style architecture diagram,
    or something else? *Bias toward "anything prettier than `menu.md`
    reads as theatre" (B.8).*

---

## What this substrate deliberately does not do

- Does not commit to a curator schema, persona depth, pipeline
  placement, or test surface.
- Does not commit to a demo arc, slide design, dry-run cadence, or
  rehearsal plan.
- Does not commit to whether an Israel run is scheduled before the
  demo.
- Does not enumerate every scenario YAML or persona file that might
  exist in 6 weeks. Those decisions belong to the plan.
- Does not write the slide deck or the speaker notes.

The plan is /ultraplan's. This file is the brief.
