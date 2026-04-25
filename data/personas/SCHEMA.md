# Red-planner persona corpus — schema

A persona is a small markdown file with YAML frontmatter and a structured body. It defines a single Red-side planner whose POV the off-distribution generator adopts. Multiple personas, run in parallel, produce structurally diverse proposals **grounded in their own ethnographic biases** rather than in a self-aware "be different" instruction.

The architecture follows Park et al. (2023) *Generative Agents* §A.1 — each agent carries a one-paragraph identity seed that gets prepended to every prompt the agent generates from. The body of each persona file IS that seed plus the structured tags the selector uses.

## Directory layout

```
data/personas/
├── SCHEMA.md                             ← this file
├── pla/
│   ├── rocket-force-doctrinaire.md
│   ├── post-2015-joint-planner.md
│   └── political-officer.md
└── me/
    ├── irgc-quds-operations-officer.md
    ├── hezbollah-veteran.md
    └── houthi-independent-commander.md
```

One persona per file. The loader walks the tree and validates every `*.md` against the pydantic model below.

## Frontmatter schema

```yaml
---
id: persona-pla-rocket-force-doctrinaire   # REQUIRED. Unique slug. Citation key in audit log.
name: anonymized handle                     # REQUIRED. Short label for the menu UI.
actor: pla                                  # REQUIRED. One of: pla | iran | hezbollah | houthi | iraqi-militia | syrian-militia
formation: doctrinal                        # REQUIRED. One of: doctrinal | improvisational | political | technocratic
generation: cold-war                        # REQUIRED. One of: cold-war | post-2001 | post-2014 | post-2024
temperament: cautious                       # REQUIRED. One of: cautious | aggressive | patient | risk-tolerant | factional
applies-to:                                 # REQUIRED. Scenarios this persona is selected for.
  - taiwan_strait_spring_2028
priority: high                              # REQUIRED. high | medium | low. Drives selection bias when the scenario has more eligible personas than slots.
tags:                                       # OPTIONAL. Free-form. Surface-able in the audit panel.
  - rocket-force
  - second-artillery
  - 1995-96-veteran
notes: |                                    # OPTIONAL. Authoring notes; not surfaced to the model.
  Source citations / RA-corpus pointers go here.
---
```

Body sections (all required):

```markdown
# Identity seed (Park et al. §A.1)
A 4-8 sentence first-person-pleading paragraph: career arc, doctrinal formation,
key institutional affiliations, two or three operational scars or formative
events, current role. Specific, not generic. The reader should be able to
imagine this person holding a coffee.

# Ethnographic exterior
2-4 sentences of "soft" detail that doesn't appear in any doctrine: what they
read, eat, listen to; family ties; a quirk; a personal grievance. NOT a
psychological profile — concrete behaviors and visible signals. This is the
material that produces *plausible but surprising* proposals because the model
has to imagine a planner shaped by these specific exposures rather than a
generic "Red planner."

# Doctrinal priors
3-6 bullets naming the doctrines, doctrinal debates, or operational concepts
this persona privileges or distrusts. Cite passage IDs from
`data/doctrine/passages/` where relevant — the persona's "what they
actually believe" is a subset of the corpus filtered by their formation.

# Blind spots and ergonomics
2-4 bullets naming what this persona systematically *under*-considers — the
reverse of doctrinal priors. The off-distribution surface for THIS persona is
adjacent to but distinct from the modal-LLM's surface. A persona-pool
ensemble's combined blind spots should be much smaller than any one persona's,
which is the architectural reason for the pool.
```

## Controlled vocabulary

`actor` (closed set):
- `pla` — People's Liberation Army (any service)
- `iran` — IRGC, Artesh, MOIS, Supreme National Security Council
- `hezbollah` — Lebanese Hezbollah
- `houthi` — Ansar Allah movement
- `iraqi-militia` — Kataib Hezbollah, Asaib Ahl al-Haq, Harakat Hezbollah al-Nujaba, umbrella IRI construct
- `syrian-militia` — Iran-aligned formations in Syria

`formation` (closed set):
- `doctrinal` — career inside a single service / formation, deferential to written doctrine
- `improvisational` — career across irregular operations, doctrinally agnostic
- `political` — career inside a political-military commissar / clerical / party structure
- `technocratic` — engineer / OR / planning-staff career, doctrinally indifferent if it works

`generation` (closed set, formative-period anchor):
- `cold-war` — formative experiences pre-2001
- `post-2001` — formative experiences in the post-9/11 / GWOT decade
- `post-2014` — formative experiences in the post-Crimea / Syria / ISIS era
- `post-2024` — formative experiences in the most-recent regional reset (post-Ukraine, post-October-2024 strikes, post-Gaza)

`temperament` (closed set):
- `cautious` — high reluctance to escalate; weights political costs heavily
- `aggressive` — actively pushes for kinetic moves over reformatory ones
- `patient` — willing to wait for advantageous timing; long horizon
- `risk-tolerant` — accepts higher operational risk for higher upside
- `factional` — primary loyalty is internal-political, not operational; calculus runs through coalition or internal-rival lens

`priority`: `high` (always selected when applicable) | `medium` (selected when slots available) | `low` (background; rotated in for variety).

## Selection contract

`src/personas/select.py::select_for_scenario(scenario_id, k=6)` returns up to `k` personas whose `applies-to` includes the scenario. Selection biases toward `priority: high`, then fills by tag-coverage so the pool spans `formation` and `generation` axes (avoid 6 personas all with `formation: doctrinal`).

## Loader contract

`src/personas/index.py::load_index() -> PersonaIndex` walks the tree, parses frontmatter, validates against the pydantic model, builds:
- `by_id: dict[str, Persona]`
- `by_actor: dict[str, list[Persona]]`
- `by_scenario: dict[str, list[Persona]]`
- `by_formation: dict[str, list[Persona]]`

CLI: `python -m src.personas.index --validate` exits non-zero on schema errors. Strict by default — unknown enum values fail.

## Authoring rules

1. **Specific, not generic.** "Senior Rocket Force planner" is too generic. "32-year career, came up through Second Artillery before the 2015 reform, watched the 1995-96 crisis from inside the brigade fires cell" is the right level.
2. **No real names.** Anonymized handles only. The point is a *type* of planner, not an individual.
3. **Ethnographic exterior must be specific.** "Reads PLA Daily" is too generic. "Reads PLA Daily morning, Lin Yutang in the evening" gives the model something to project from.
4. **Persona's doctrinal priors must cite passage IDs from `data/doctrine/passages/`** wherever possible. This is what couples the persona to the rest of the system.
5. **Blind spots are doctrinal, not psychological.** Avoid "is overly self-confident." Use "systematically under-models the alliance system as having internal coalition friction."
6. **No prescription.** Don't write "this persona will propose X." Write the formation and let the model derive the proposal.

The point: when the off-distribution generator runs from this persona's POV, it should produce moves that a generic Red-planner LLM wouldn't surface — not because the prompt says "be different," but because *this specific planner* would naturally see the situation differently.
