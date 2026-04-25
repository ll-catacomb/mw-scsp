---
id: pla-volt-typhoon-class
source: CISA/FBI/NSA Volt Typhoon advisories; Unit 42; Air & Space Forces Magazine; Neuberger remarks
edition: "CISA AA-2024-038A (Feb 2024); Unit 42 threat brief 2024; A&SF Mag 2024–2025"
section: "Volt Typhoon-class civilian-infrastructure pre-positioning"
page: n/a
type: definition
priority: high
topics:
  - volt-typhoon-class
  - substrate-targeting
  - off-distribution
  - cognitive-warfare
keywords:
  - volt typhoon
  - voltzite
  - typhoon cluster
  - flax typhoon
  - salt typhoon
  - civilian infrastructure
  - critical infrastructure
  - pre-positioning
  - ot environment
  - ics scada
  - rail switching
  - port operating system
  - water utility ics
  - electric utility
  - conus rear
  - homeland degradation
synonyms:
  - civilian-infrastructure pre-positioning
  - homeland cyber pre-positioning
  - non-espionage cyber pre-positioning
  - ics pre-positioning
  - sub-attribution cyber
applies-to:
  - off-distribution-flag
  - adjudication
  - blue-frame-check
related:
  - pla-active-defense
  - pla-joint-island-landing-campaign
  - jp3-0-systems-perspective
notes: |
  This is the canonical "civilian-infrastructure pre-positioning as the actual weapon"
  passage. Adjudicators should retrieve when a Red move proposes acting against US/allied
  civilian critical infrastructure rather than against military targets — the move
  escapes the kinetic adversary-COA frame entirely.
---

# Volt Typhoon-class civilian-infrastructure pre-positioning — CISA; Unit 42; A&SF Mag

PRC cyber pre-positioning in US (and allied) civilian critical infrastructure documented in successive CISA / FBI / NSA Joint Cybersecurity Advisories (Volt Typhoon AA-2024-038A and successors), Unit 42 threat briefs, MITRE ATT&CK G1017 entry, and follow-on coverage of related "Typhoon" clusters (Flax Typhoon, Salt Typhoon, Voltzite). Documented footholds and target-class set:

- **US Class I railroads** — IT/OT environments at BNSF and Union Pacific corridors feeding the WESTPAC ports of Tacoma and Long Beach.
- **West Coast and Gulf port operating systems** — crane and gate-management systems at the WESTPAC POEs.
- **Pipeline SCADA** — Colonial-class fuel pipeline control systems.
- **Regional water utilities** — utilities serving large Army installations.
- **Electric utilities** — Pacific Northwest and California utilities feeding the port complexes; Salt Typhoon at US telcos and ISPs.
- **Telecommunications infrastructure** — Salt Typhoon disclosures (2024–2025) on US telecom backbone access.

Anne Neuberger's Munich remarks (Recorded Future, Feb 2024) explicitly framed Volt Typhoon as **pre-positioning for disruption rather than espionage**. The CYBERCOM FY26 budget request sharply increased Indo-Pacific defensive cyber funding (DefenseScoop, July 2025), validating the threat frame.

The off-distribution operational logic (RA-3 Move 2): execute a rolling, sub-attribution campaign in the 72 hours *before* any kinetic act in theater. Effects: rail switching system intermittent failures across the WESTPAC supply corridors; port crane outages at three of six WESTPAC POEs; intermittent water-pressure failures at two large Army installations; voluntary load-shedding requests across the WECC. Each individual incident plausibly looks like equipment failure or ransomware; the aggregate degrades the 96-hour deployment flow before the first cargo aircraft loads.

## Why this is in the corpus

The averaged LLM ensemble parses cyber as a *supporting fire* inside theater. The off-distribution insight is that civilian-infrastructure cyber, executed before any signature in the strait and with deliberate attribution latency, can deliver substantial coercive effect with no kinetic signature at all. The Blue adjudicator should retrieve this passage when (a) a Red move is best read as Volt-Typhoon-class infrastructure pre-positioning rather than kinetic action, or (b) the modal ensemble has produced a kinetic-only cluster and the off-distribution proposals attack the civilian substrate. Pair with `pla-active-defense` (the doctrinal framing that lets PRC characterize the pre-positioning as defensive deterrence) and `jp3-0-systems-perspective` for the cross-PMESII reading.
