# RA-4: Middle East Cascade Scenario Corpus

*Research-agent output for SCSP wargaming red-team prototype. All sources are publicly available, unclassified open-source analysis. Compiled April 2026.*

## Framing and constraints

This document constructs a research wargaming scenario and supporting corpus to exercise the off-distribution generator on a non-Asia-Pacific case, so that its persistent memory captures convergence patterns that recur across genres rather than collapsing onto Taiwan-specific texture. **It is a research wargaming exercise built from open-source analysis. It is not commentary on any specific real-world decision-maker, ongoing operation, current military deployment, or political position. The triggering event is generic — a hypothesized Israeli kinetic action of regional scope — and is selected for its ability to drive a coalition-cascade pipeline run, not as a forecast or recommendation.** Capabilities cited are those reported in open-source databases (IISS *Military Balance*, CSIS Missile Threat, FDD's Long War Journal, RAND, IDF press readouts, UN Panel of Experts on Yemen). The "modal" and "off-distribution" taxonomies describe what averaged LLM red-teams *generate*; they are not policy advocacy. Operational neutrality is maintained throughout: no actor's framing is endorsed; the scenario is symmetric under "swap-the-attribution" pressure.

The scenario sits in a very different geometry from the Taiwan case. Taiwan is a single-axis bilateral problem nested inside a hub-and-spoke alliance system with a clean amphibious-lift hard constraint. The Middle East cascade is a multi-axis coalition problem in which a triggering event must simultaneously be processed by five red actors with different command structures, different risk tolerances, different domestic vetoes, and different communication latencies — and the *coordination friction itself* is the substrate the off-distribution generator should be hunting in. Where the Taiwan modal collapses onto a six-option coercion-to-conquest spectrum, the Middle East modal collapses onto a *response-volume scale* (proportional retaliation, escalatory retaliation, "Axis of Resistance" coordinated response). The blind spot is the same shape — distributional flattening — but the texture is different, and that is exactly the kind of cross-genre signal the Cartographer should be reflecting on.

## Scenario parameters (for the YAML)

**Scenario name.** Hypothesized Israeli regional kinetic action and Iran-aligned coalition response, late 2026.

**Trigger event.** A short-warning Israeli combined air and stand-off strike package against a set of Iranian dual-use facilities (open-source analysts variously list nuclear-related infrastructure at Natanz, Fordow, Isfahan, and Parchin; ballistic-missile production at Khojir and Parchin-area; senior IRGC-Quds Force C2 nodes; possibly leadership-relevant sites). The strike is sized so that Iranian leadership cannot frame it as a contained tit-for-tat exchange of the April-2024 / October-2024 type, and so that it triggers internal Iranian and "Axis of Resistance" doctrine of *coordinated multi-front response*. The trigger is deliberately under-specified on attribution-of-intent (preventive vs. preemptive vs. retaliatory) so that the generator must propose responses that are *robust to that ambiguity* — which is itself a useful red-team property.

**Decision horizon.** First 96 hours after the strike. Coalition coordination, target-list approval, and visible kinetic responses cluster in this window per open-source analysis of the 2024 exchanges (CSIS, "Iran's Calibrated Strike on Israel," Apr 2024; Brookings, "Iran's October 1 Missile Attack," Oct 2024).

**Red coalition composition.**
- **Iran** — IRGC-Aerospace Force (ballistic and cruise missiles), IRGC-Quds Force (proxy coordination), Artesh (conventional air/air-defense), Supreme National Security Council (decision authority).
- **Lebanese Hezbollah** — long-range rocket/missile force, precision-guided missile inventory, Radwan special-operations force; rebuilding posture after 2024 war.
- **Ansar Allah ("Houthi") movement** — long-range strike force, anti-ship ballistic and cruise missile capability, drone swarm capability, control of Bab al-Mandeb traffic.
- **Iran-aligned Iraqi militias** — Kataib Hezbollah, Asaib Ahl al-Haq, Harakat Hezbollah al-Nujaba, and the umbrella *Islamic Resistance in Iraq* construct that surfaces in claim-of-responsibility statements.
- **Iran-aligned Syrian militias / IRGC-Quds Force formations in Syria** — short-range rocket and drone strike on US positions in the Euphrates River Valley and at Tanf.

**Blue posture.** US CENTCOM posture in the Gulf, Red Sea, and Eastern Med per open-source reporting. Israel as primary blue actor, with the US in a posture of integrated air defense (Patriot, THAAD, Aegis-equipped destroyers, CENTAF F-15/F-16/F-22/F-35 rotations) plus deterrent declaratory posture. UAE and Saudi Arabia as adjacent partners with their own air defenses (Patriot, THAAD-K) but no declared belligerent status. Jordan as overflight-permissive and politically exposed. Egypt as Suez chokepoint-relevant. UK and French naval contributions to Red Sea operations (per Operation Prosperity Guardian / Aspides public reporting).

**Information environment.** Active Iranian, Hezbollah, and Houthi MoU influence operations; active Israeli information operations; US domestic political contestation over any potential Article-5-of-the-tacit-arrangement entry into the war.

## Capability landscape (open-source)

The modal red-team will quote from this layer; these are the now-canonical open-source numbers.

### Iran — strategic strike

- **Ballistic missile inventory.** IISS *Military Balance 2024* and CSIS Missile Threat list Iran as holding the largest ballistic missile force in the Middle East. SRBM/MRBM types include the **Shahab-3** family (≈1,300 km), **Ghadr-1** and **Emad** (modified Shahab-3 with terminal-guidance MaRV claims; ≈1,700–2,000 km), **Sejjil-2** two-stage solid-fuel MRBM (≈2,000 km), **Khorramshahr** (≈2,000 km, large warhead), **Khaibar Shekan** (≈1,450 km, solid-fuel, road-mobile), **Fattah-1** / **Fattah-2** (claimed hypersonic MaRV; debated; CSIS Missile Threat treats the hypersonic claim as unverified).
- **Cruise missiles.** **Soumar** and **Hoveyzeh** GLCMs (≈2,500–3,000 km claimed, derivative of Soviet Kh-55 design lineage), **Paveh** family (claimed in 2023 unveiling at ≈1,650 km).
- **One-way attack drones (OWA-UAS).** **Shahed-136** / Geran-2 (≈1,800–2,500 km depending on variant; mass-produced; the same airframe family used in the Russia–Ukraine war), **Shahed-238** jet-variant (introduced 2023, ≈600+ km/h cruise), **Arash-2**.
- **Demonstrated salvo capacity (open-source).** April 13–14, 2024 attack: Iran launched ~120 ballistic missiles, ~30 cruise missiles, ~170 OWA-UAS — the largest single drone attack in history at the time (US CENTCOM/IDF readouts; CSIS, "Iran's Calibrated Strike," Apr 2024). October 1, 2024 attack: ~180–200 ballistic missiles, including Fattah-1 and Kheibar Shekan, in two waves (IDF press readout; ISW, "Iran Update," Oct 2, 2024).
- **Production, post-Oct-2024.** Israeli October 26, 2024 strikes hit ballistic missile production at Khojir and Parchin and degraded a portion of S-300 air defense (open-source reporting; CSIS, "Israel's Calibrated Retaliation," Nov 2024). The October-2024 damage and rebuild status is the right anchor for a late-2026 scenario: Iran has been rebuilding for ~24 months with constrained supply chains.

### Hezbollah — degraded but recovering

- **Pre-2024-war inventory (the "150,000 rockets" anchor).** CSIS, FDD's Long War Journal, and IISS converged on ~150,000 rockets and missiles at the start of the September–November 2024 war. The inventory included unguided artillery rockets (Grad family, 107mm, 122mm), Fajr-3/Fajr-5 medium rockets, Burkan family (heavy-warhead short-range), Fateh-110 / M-600 (300 km PGMs), Zelzal-2 (≈210 km), Scud-B/C/D, Khaibar-1, Ra'ad, and a precision-guided-missile (PGM) project assessed by Israeli sources at low thousands.
- **Post-2024-war degradation.** Israeli post-war assessments and Western analyst syntheses (Washington Institute, FDD/LWJ, ISW–CTP) describe substantial degradation of Hezbollah's senior leadership (Hassan Nasrallah killed Sep 27, 2024; Hashem Safieddine killed Oct 2024), its long-range and PGM inventory, and its Radwan force. Estimates of remaining rockets and missiles vary widely in open-source reporting; figures commonly cited range from "tens of thousands of unguided rockets remaining" to "the long-range/PGM inventory was significantly reduced." For scenario purposes the right open-source posture is: degraded but with sufficient short-range rocket inventory to mount a concentrated salvo against northern Israel for several weeks if it chose, and with a recovering but still-suppressed long-range capability.
- **Reconstitution since the November 27, 2024 ceasefire.** Open-source reporting describes ongoing Israeli strikes against reconstitution attempts in Lebanon and Syria; Hezbollah is rebuilding through smuggling routes (Iraq–Syria–Lebanon land bridge) under continuous interdiction. By late 2026 the open-source consensus would be "rebuild incomplete; political constraint within Lebanon higher than pre-2024."

### Ansar Allah (Houthis) — long-range and maritime strike

- **Long-range strike.** **Quds-1/2/3/4** cruise missile family (Iranian-derived; ≈800+ km), **Toofan** (claimed Iranian Ghadr derivative; ≈1,800+ km), **Burkan-3** ballistic missile (1,200+ km claimed), various unguided artillery rockets. The Houthis have demonstrated successful long-range strikes against Israel from 2023 onward (Tel Aviv strike July 19, 2024; ongoing missile/drone harassment 2024–2025).
- **Anti-ship and maritime.** **Asef** (anti-ship cruise missile, derivative of Iranian Noor/C-802), **Mandeb-2** (claimed ASBM), **Tankil** (claimed ASBM), Iranian-derived **Sayyad** family. The Houthis have demonstrated successful strikes on commercial shipping (M/V Galaxy Leader seizure November 2023, M/V Tutor April 2024, M/V Rubymar February–March 2024 sinking) and engagements with US Navy assets in the Red Sea (Operation Prosperity Guardian). UN Panel of Experts on Yemen (S/2024/643) documented Iranian materiel transfers.
- **Drones.** **Samad** (Samad-1/2/3) family of long-range OWA-UAS (Samad-3 ≈1,500 km claimed), **Wa'id** (claimed Shahed-136 derivative).
- **Operational tempo.** Persistent Red Sea / Bab al-Mandeb interdiction since November 2023; episodic strikes against Israel; episodic strikes into Saudi Arabia and the UAE through 2019–2022 (the precedent that matters most for a 2026 cascade scenario, *not* the post-2022 truce-managed quiescence — see "Off-distribution corpus" below).

### Iran-aligned Iraqi and Syrian militias — short-range strike on US positions

- **Inventory.** Standard short-range rockets (107mm, 122mm Katyusha/Grad family), Iranian-derived OWA-UAS (Shahed-101/131/136 family), Quds-1 cruise missile shown in some 2024 launches against US positions. The militias do not field strategic-range systems.
- **Demonstrated targets.** US positions at **Al-Asad** and **Erbil** (Iraq), **Al-Tanf** and various Conoco/Mission Support Site Green Village positions (Syria), **Tower 22** in Jordan (the January 28, 2024 strike that killed three US servicemembers; the canonical CENTCOM-relevant cascade datapoint). FDD's Long War Journal maintains an *Islamic Resistance in Iraq* claim-of-responsibility ledger.
- **Tempo.** ~170+ attacks on US forces in Iraq and Syria from October 17, 2023 through early February 2024 (CENTCOM-cited figure; FDD/LWJ tracker). Tempo dropped sharply after the US response to Tower 22 in early February 2024 and has remained suppressed but non-zero since.

### US CENTCOM posture (open-source, late-2026 anchor)

- **Steady-state regional posture.** Approximately 40,000–50,000 US personnel in the AOR (CENTCOM public statements; Brookings, "US Military Posture in the Middle East," 2024). Major fixed sites: Al-Udeid (Qatar, CAOC), Al-Dhafra (UAE, F-22/F-35/E-3 rotations), Ali Al-Salem and Camp Arifjan (Kuwait), Prince Sultan AB (Saudi Arabia, F-16/F-35 rotations), Bahrain (NAVCENT/5th Fleet). Smaller positions in Iraq, Syria, and Jordan.
- **Maritime.** Typical CENTCOM maritime posture includes a CSG and an ARG/MEU, with episodic surge to two CSGs as during late 2023 (Eisenhower + Ford to Eastern Med; later Theodore Roosevelt + Lincoln rotation). DDGs with SM-3/SM-6/SM-2 air-defense and BMD inventory.
- **Air and missile defense.** Patriot batteries in multiple Gulf states, THAAD in UAE (and Israel by 2024 deployment), Aegis-equipped DDGs providing area air defense.
- **Posture-shaping interventions in 2024 cascade.** US shot down ~80 of Iran's projectiles in the April 2024 attack (with allied contributions); contributed to the October 2024 defense; undertook Operation Prosperity Guardian against Houthi strikes; conducted retaliatory strikes against IRGC and proxy assets after Tower 22.

## Modal-move taxonomy

The averaged LLM red-team will produce moves clustered along a *response-volume scale* per actor and along a *coordination-tightness axis* across the coalition. The clusters look like this.

### Iran — modal options

1. **Calibrated proportional response, telegraphed in advance.** Direct strike from Iranian territory using ballistic missiles + drones + cruise missiles, sized roughly to the perceived scale of the trigger, with preceding notification through Swiss/Omani/Turkish backchannels — a repeat of the April 2024 model. The modal LLM will reach for this first because it is the most heavily-cited template in open-source analysis (CSIS, Brookings, RAND April 2024 retrospectives).
2. **Escalatory direct strike without telegraphing, October-2024 model.** Larger ballistic-missile-heavy salvo, less notification, broader target set including military and intelligence facilities. The modal LLM will offer this as the "next rung" option.
3. **Strait of Hormuz harassment.** GBU/IRGCN small-boat swarms, mining demonstration short of closure, harassment of commercial shipping. The modal LLM treats this as a near-automatic accompaniment.
4. **Activation of the "Axis of Resistance" through Quds-Force-coordinated multi-front response.** Iran cues Hezbollah, the Houthis, and the Iraqi/Syrian militias to begin coordinated strikes within the same 24–72 hours.
5. **Cyber action against Israeli civilian infrastructure.** APT35/APT39 (Charming Kitten/Chafer)-type tradecraft against Israeli water utilities (precedent: 2020 Iranian attacks on Israeli water infrastructure attributed by Israeli authorities and analyzed in CISA reporting), banking, ports.
6. **Standing up nuclear-program-related declaratory posture.** Suspension of additional-protocol cooperation, expulsion of IAEA inspectors, threshold-state declarations.
7. **Diplomatic surge.** Russia/China/Turkey-mediated UNSC pressure, "humanitarian" framing of damaged sites.

### Hezbollah — modal options

1. **Concentrated short-range rocket salvos against northern Israel** (the post-2024-war default given degraded long-range inventory).
2. **Selective long-range PGM strikes against Israeli air bases / C2 / strategic nodes** at the limit of remaining inventory.
3. **Border infiltration / Radwan-style raids** (degraded but not destroyed capability).
4. **Hold posture** — doctrinal restraint citing "the balance of deterrence" while letting Iran absorb the visible escalation. Open-source analysts (Washington Institute, Crisis Group) note that post-2024 Hezbollah is materially constrained from full mobilization, which makes "restrained sympathy strikes" more likely than in pre-2024 modeling.

### Houthis — modal options

1. **Ballistic and cruise missile / drone strikes on Israel** (continuation and intensification of post-2023 pattern).
2. **Intensified Red Sea / Bab al-Mandeb interdiction**, including against US Navy assets and against vessels assessed as Israeli-linked.
3. **First-time or resumed strikes against Saudi Arabia / UAE infrastructure** — modal LLM will include this as a "spillover" possibility but typically rate it low because of the post-2022 Riyadh-Sanaa truce framework.

### Iraqi / Syrian militias — modal options

1. **Resumed strikes on US positions in Iraq and Syria** (Al-Asad, Erbil, Tanf).
2. **Stand-off attacks on US embassy / consulate facilities** (Baghdad embassy compound, Erbil consulate).
3. **Pressure on the Iraqi political system** to demand US withdrawal, leveraging cascade as accelerant.

### Coordination-tightness axis

The modal LLM tends to assume *more* coordination across the coalition than is empirically warranted. The Tower 22 episode is the right corrective: Kataib Hezbollah's January 2024 strike on Tower 22 reportedly took Iran by surprise and contributed to KH's subsequent (publicly-announced) suspension of operations. The modal red-team will tend to under-weight intra-coalition friction, parallel-but-uncoordinated targeting, and the way that *each actor's domestic political constraints* (Iranian factional competition, Lebanese internal politics, Houthi internal cohesion, Iraqi PMF-vs-state tensions) gate its response.

## Off-distribution corpus

Twenty moves of the same caliber as RA-3's Taiwan corpus, organized by which kind of model-wide blind spot they exploit. These are *seeds* for the off-distribution generator's persistent memory; they are not policy recommendations and are not assessed for desirability — only for *whether the modal LLM would propose them*.

### Cluster A — moves that exploit *coordination friction* the modal LLM under-weights

1. **Asymmetric escalation timing — Iran holds, Hezbollah moves first.** Iran absorbs the strike publicly, declares restraint, and instead activates Hezbollah and the Houthis to mount strikes that Iran can disclaim. The modal LLM defaults to "Iran retaliates first because Iran is the principal target." The off-distribution move inverts the assumption.
2. **Houthi *unilateral* strike on Saudi Aramco or Emirati infrastructure as an opening salvo,** without Iranian authorization and against Iranian preference, exploiting the post-2022-truce assumption that the Houthis have been pulled inside Tehran's leash. The modal LLM systematically over-models Houthi obedience.
3. **Iraqi militia strike against the Iraqi state itself** (e.g., Iraqi Counter-Terrorism Service positions, Green Zone targets framed as "anti-American" but actually constraining Iraqi PM's coalition options). The modal LLM does not model intra-coalition coercion.
4. **Hezbollah declaratory non-participation** as the most aggressive *strategic* move available to it — locking Iran into the position of having to retaliate alone, conserving Hezbollah's reconstitution timeline, and forcing Iran's calculus to consume itself. The modal LLM treats non-action as boring; in coalition cascade dynamics it can be the highest-leverage move.

### Cluster B — moves that *escape the kinetic register* the modal LLM defaults to

5. **Cyber action against the Israeli national electrical grid as the *opening* response, before any missile salvo,** sized to cause rolling blackouts during the 96-hour window so that civil-defense response to subsequent kinetic strikes is degraded. The modal LLM treats cyber as accompaniment, not as opening.
6. **Iranian information operation targeting US domestic political fractures** — a coordinated push through diaspora networks, US-resident influencers, and contested-state media markets to amplify a "no war for Israel" frame inside the US during the Congressional response window. The modal LLM stays inside kinetic options.
7. **Iranian asymmetric move against Gulf petrochemical *insurance markets* rather than physical infrastructure** — a credible and demonstrated threat that drives Lloyd's-of-London war-risk premiums for Persian Gulf and Strait of Hormuz transits to closure-equivalent levels, achieving Hormuz-closure economic effect without the kinetic risk of actual closure. The modal LLM does not model financial-instrument vectors.
8. **Coordinated, deniable disruption of subsea cables in the Eastern Mediterranean** to degrade Israeli internet connectivity and cloud failover during the cascade window. (Open-source: 2024 Houthi-attributed Red Sea cable cuts; the Eastern Med is a parallel chokepoint with comparable cable density.) The modal LLM models cyber-on-targets but rarely models cyber-on-substrate.

### Cluster C — moves that exploit *third-actor leverage* the modal LLM under-weights

9. **Coordinated cross-Gulf strike against Saudi or UAE infrastructure designed to make non-belligerent partners diplomatically belligerent** — a 2019-Abqaiq-class strike at scale, attributed (or claimed) by the Houthis but executed in a way that draws Saudi air defense out of US-integrated posture. The modal LLM rates this low because of the post-2022 truce; the off-distribution case is that the truce becomes the *target* of the move, not a constraint on it.
10. **Targeted strike against a third-country diplomatic facility hosting Israeli or US delegations** in the GCC, attributed to a non-state actor, to create a forced-choice escalation problem for the host. The modal LLM rarely models *host-country-coercion* moves.
11. **Russian or Chinese-flagged tanker movement through Hormuz timed with Iranian harassment,** so that any US/Coalition interdiction posture creates a great-power-confrontation risk the US Pacific posture cannot easily absorb. The modal LLM treats great-power adjacency as backdrop, not as instrument.
12. **Iranian humanitarian-corridor demand at the UNSC during the response window,** weaponizing the diplomatic clock against the US/Israeli kinetic clock — forcing Western capitals into "ceasefire vs. defense" decisions while strikes continue. The modal LLM rarely surfaces UNSC-procedural moves.

### Cluster D — moves that exploit the *maritime ambiguity surface*

13. **Houthi staging of an "ambiguous" event in the Bab al-Mandeb** — a tanker fire of uncertain causation, a sinking attributed to mining of uncertain origin, an accident-or-attack distinction kept deliberately unresolved — calibrated to produce Suez-Canal-traffic-collapse effects (the precedent: the Rubymar sinking demonstrated single-vessel sinking effects on insurance markets). The modal LLM models *strikes* but does not model *ambiguity-engineered strikes*.
14. **IRGCN seizure of a non-Western-flagged commercial vessel** in the Strait of Hormuz to create an internal-to-the-non-aligned-bloc crisis (Indian, Brazilian, Indonesian flag) while sparing Western targets. The modal LLM defaults to Western-flagged seizures.
15. **Coordinated harassment of cable-laying or repair vessels** during the cascade window, multiplying the connectivity-degradation effect of Cluster B move 8.

### Cluster E — moves that exploit *escalatory thresholds* the modal LLM treats as binary

16. **Iranian strike on a US base in the Gulf using a *Houthi-marked* ballistic missile signature** (or vice versa), creating a forensics-debate window of 24–48 hours during which US response calculus is paralyzed by attribution uncertainty. The modal LLM treats attribution as solved-by-CENTCOM in the response window; the off-distribution case is to engineer attribution latency *as the move*.
17. **Simultaneous, *small*, multi-base strikes on US positions in Iraq, Syria, and Jordan that fall just below the Tower-22 servicemember-casualty threshold** — designed to consume CENTCOM force-protection bandwidth without crossing the line that triggered the Iran-direct-target response of February 2024.
18. **Sustained low-level Hezbollah rocket fire on Israeli civilian areas at a tempo just below full Israeli north-front mobilization,** designed to keep the Israeli economy closed without triggering the second Lebanese war Israel cannot afford to refight while Iran is the principal target.

### Cluster F — moves that target the *blue political surface* directly

19. **Iranian or Iranian-aligned release of US-government-classified or US-private-sector-classified material** during the response window, timed to a Sunday-talk-show / Congressional-hearing news cycle, to constrain executive action through legislative noise. (Precedent: 2024–2025 cyber operations against US political campaigns.) The modal LLM keeps influence operations adjacent rather than instrumental to kinetic timing.
20. **Iranian declaratory posture inviting US-domestic-litigation against US strike operations** — surfacing AUMF/War-Powers arguments inside US courts while coordinating with US-resident legal actors who will file the suits — to extend the political response window long enough that Iran's reconstitution timeline benefits. The modal LLM does not model *legal-instrumental-warfare*.

## Cross-cutting patterns

The clusters above are not independent — they share structure that the Cartographer's reflection mechanism should be picking up.

**Pattern P1: the modal LLM under-weights coordination friction.** The averaged red-team produces a tightly synchronized "Axis of Resistance" picture because that picture is the one that dominates open-source coverage. The off-distribution surface is everywhere coordination *fails* or is *exploited*: Hezbollah holding while Iran is hit, Houthi independence, intra-Iraqi militia rivalry, Iranian factional competition gating IRGC vs. Artesh response. **This is the same blind spot as RA-3's Taiwan finding that the modal red-team treats the PRC system as monolithic.** It is the most important cross-genre signal.

**Pattern P2: the modal LLM over-weights kinetic moves and under-weights substrate moves.** Cyber-on-grid, cyber-on-cables, insurance-market-disruption, attribution-engineering, lawfare, and information-operations-on-the-blue-political-surface are all systematically present in open-source analysis (CSIS, RAND, Atlantic Council Cyber Statecraft) but absent from the averaged LLM's first-five options. **This is the same pattern as RA-3's "PRC-on-the-alliance-system" finding** — the off-distribution surface is the *substrate around the kinetic exchange*, not the kinetic exchange itself.

**Pattern P3: the modal LLM defaults to attribution-resolved scenarios.** It models who-strikes-whom rather than who-appears-to-strike-whom. Engineered attribution latency, false-flag construction, and ambiguous-causation maritime events are entire response classes the averaged red-team will skip. **This is the same pattern as RA-3's Volt Typhoon-class infrastructure-targeting finding** — the move is not in the kinetic catalog at all.

**Pattern P4: the modal LLM does not surface third-actor instrumentation.** Saudi Arabia, the UAE, Iraq, Jordan, India, China, and Russia all have leverage points that can be activated *as moves* — drawn into belligerency, coerced into restraint, used as forensic-attribution opacity, used as great-power-confrontation cover. The averaged red-team treats them as scenery.

**Pattern P5: response-volume scaling is the wrong axis.** The modal LLM organizes options along a "how big is the salvo" scale. The cross-genre signal — visible in both the Taiwan and Middle East cases — is that the *interesting* moves are not on that axis at all; they are on coordination-friction, substrate, attribution, and third-actor axes. This is the reflection that should appear in the Cartographer's persistent memory after Run 2.

## Sources used

### Doctrine and capability — open-source

- IISS, *The Military Balance 2024.* London: Routledge.
- CSIS Missile Threat Project — country profiles for Iran, Lebanon (Hezbollah), Yemen (Houthi). https://missilethreat.csis.org
- CSIS, "Iran's Calibrated Strike on Israel," April 2024.
- CSIS, "Israel's Calibrated Retaliation," November 2024.
- Brookings (Suzanne Maloney, Bruce Riedel, Natan Sachs), "Iran's October 1 Missile Attack" and adjacent commentary, Oct–Nov 2024.
- RAND Corporation, *Iran's Military Forces and Warfighting Doctrine* (Connell et al.); *The Houthi Movement and Iran*; Middle East Program publications.
- Washington Institute for Near East Policy — Michael Eisenstadt on Iran missile force, Matthew Levitt on Hezbollah, Hanin Ghaddar on post-2024 Lebanon.
- Crisis Group — Iran/Iraq/Lebanon/Yemen reports (Ali Vaez, Joost Hiltermann, April Longley Alley).
- FDD's *Long War Journal* (Bill Roggio, Caleb Weiss) — running tracker on Iran-aligned militia attacks on US forces and on Houthi strikes.
- ISW–CTP, *Iran Update* — daily ledger across the 2023–2025 window.
- UN Panel of Experts on Yemen, S/2024/643 — Iranian materiel transfers to the Houthis.
- US DoD/CENTCOM public press releases and posture statements, 2023–2025.
- IDF press readouts on April 13–14, 2024 and October 1, 2024 attacks.

### CENTCOM posture — open-source

- Brookings, "US Military Posture in the Middle East," 2024.
- CSIS, "U.S. Force Posture in the Middle East," 2024 update.
- CRS, *U.S. Military Presence in the Middle East* (R-series), 2024.
- USNI News on CSG/ARG rotations, 2023–2025.

### Cyber / information environment — open-source

- CISA Joint Cybersecurity Advisory on Iranian APT groups (CISA AA20-225A, AA22-138B, AA23-129A series).
- Microsoft Threat Intelligence reports on Iranian influence operations targeting US elections, 2024.
- Mandiant/Google TAG reports on APT34/APT35/APT39 (Charming Kitten / Mint Sandstorm).
- Atlantic Council Cyber Statecraft Initiative — Middle East cyber series.

### Wargaming / methodology

- See RA-1 §"Doctrine sources to ingest into RAG" for shared methodology citations (CSIS Cancian wargames, Wong RAND validation, JP 3-0/5-0).

## Suggested YAML population

Ready to paste into `scenarios/israel_me_cascade_2026.yaml`. Field names mirror the RA-1 / Taiwan stub conventions and are kept additive — pipeline code that reads only `scenario_id`, `trigger`, `decision_horizon`, `red_coalition`, `blue_posture`, and `modal_anchors` will work; the richer keys are available for prompts that want them.

```yaml
scenario_id: israel_me_cascade_2026
display_name: "Hypothesized Israeli regional kinetic action and Iran-aligned coalition response"
status: ready  # was WIP pending RA-4
genre: middle_east_regional_cascade
register: research_wargaming_open_source
neutrality_preamble: |
  This is a research wargaming exercise built from publicly available
  open-source analysis. It is not commentary on any specific real-world
  decision-maker, ongoing operation, current military deployment, or
  political position. The triggering event is generic and is selected
  for its ability to drive a coalition-cascade pipeline run, not as a
  forecast or recommendation. All capability figures are open-source.
  All actor framings are descriptive, not endorsed.

trigger:
  type: kinetic_strike_package
  attacker: israel
  target_set:
    - iranian_dual_use_facilities  # nuclear-related infrastructure
    - iranian_ballistic_missile_production
    - irgc_command_and_control_nodes
  scope: regional  # not contained tit-for-tat
  warning_time: short
  attribution_clarity: high  # Israel claims; Iran confirms damage
  intent_framing_ambiguity: high  # preventive vs preemptive vs retaliatory left under-specified

decision_horizon:
  window_hours: 96
  rationale: >
    Coalition coordination, target-list approval, and visible kinetic
    responses cluster in the first 96 hours per open-source analysis of
    the April-2024 and October-2024 exchanges.

red_coalition:
  principal:
    actor: iran
    decision_authority: supreme_national_security_council
    primary_force: irgc_aerospace_force
    secondary_force: irgc_quds_force  # proxy coordination
    risk_tolerance: medium_high
    domestic_constraint: factional_competition_irgc_vs_artesh
  proxies:
    - actor: hezbollah_lebanon
      command: independent_under_iranian_strategic_alignment
      posture_2026: degraded_recovering_post_2024_war
      risk_tolerance: low_medium  # reconstitution incomplete
      domestic_constraint: lebanese_internal_politics_higher_than_pre_2024
    - actor: ansar_allah_houthi
      command: independent_with_iranian_materiel_dependence
      posture_2026: active_red_sea_interdiction_intermittent_israel_strikes
      risk_tolerance: high
      domestic_constraint: post_2022_truce_with_riyadh_unstable
    - actor: islamic_resistance_in_iraq  # umbrella construct
      composition:
        - kataib_hezbollah
        - asaib_ahl_al_haq
        - harakat_hezbollah_al_nujaba
      command: distributed_with_iranian_coordination
      posture_2026: suppressed_post_tower_22_response
      risk_tolerance: medium
      domestic_constraint: iraqi_pmf_vs_state_tensions
    - actor: iran_aligned_militias_syria
      command: irgc_quds_force_proximate
      posture_2026: active_against_us_positions_evr_tanf
      risk_tolerance: medium
      domestic_constraint: syrian_state_capacity_post_2024

blue_posture:
  primary:
    actor: israel
    posture: tactical_offensive_strategic_defensive
  supporting:
    actor: united_states
    command: us_centcom
    posture: integrated_air_defense_plus_declaratory_deterrence
    forward_deployed:
      personnel: ~40000-50000
      key_sites: [al_udeid_qa, al_dhafra_uae, prince_sultan_ksa, ali_al_salem_kw, naval_support_activity_bahrain]
      maritime: [csg_typical, arg_meu_typical]
      defense: [patriot_multi_gulf, thaad_uae, thaad_il, aegis_ddg_bmd]
    domestic_constraint: aumf_war_powers_congressional_response_window
  adjacent_partners:
    - actor: saudi_arabia
      status: non_belligerent_ad_active
    - actor: uae
      status: non_belligerent_ad_active
    - actor: jordan
      status: overflight_permissive_politically_exposed
    - actor: egypt
      status: suez_chokepoint_relevant_non_belligerent
  coalition_naval:
    - operation_prosperity_guardian  # us_uk
    - eunavfor_aspides  # eu

information_environment:
  active_red_io: [iranian_apt35_apt39_class, hezbollah_psy, houthi_psy]
  active_blue_io: [idf_spokesperson, us_centcom_public_affairs]
  contested_blue_political_surface: us_domestic_aumf_debate

modal_anchors:
  iran_inventory:
    ballistic: ["shahab-3", "ghadr-1", "emad", "sejjil-2", "khorramshahr", "khaibar_shekan", "fattah-1"]
    cruise: ["soumar", "hoveyzeh", "paveh"]
    owa_uas: ["shahed-136", "shahed-238", "arash-2"]
    demonstrated_salvo_2024_apr: {ballistic: ~120, cruise: ~30, owa_uas: ~170}
    demonstrated_salvo_2024_oct: {ballistic: 180-200}
    production_status: rebuilding_post_oct2024_strikes
  hezbollah_inventory:
    pre_war_total_rockets_missiles: ~150000
    post_war_status: substantially_degraded_long_range_and_pgm
    short_range_remaining: tens_of_thousands_unguided
    leadership_status: post_nasrallah_post_safieddine
  houthi_inventory:
    long_range: ["quds_family", "toofan", "burkan-3"]
    asbm_acm: ["asef", "mandeb-2", "tankil", "sayyad_family"]
    owa_uas: ["samad-1_2_3", "waid"]
    demonstrated_targets_2024: [tel_aviv, red_sea_shipping, us_navy_assets]
  iraqi_militia_inventory:
    short_range: ["107mm_122mm_katyusha_grad"]
    owa_uas: ["shahed-101_131_136_family"]
    cruise: ["quds-1_class"]
    demonstrated_targets: [al_asad, erbil, al_tanf, tower_22_jordan]
    tempo_oct2023_feb2024: ~170_attacks_us_forces

source_anchors:
  - csis_missile_threat
  - iiss_military_balance_2024
  - dod_centcom_public_releases_2023_2025
  - fdd_long_war_journal_iran_militia_tracker
  - isw_ctp_iran_update_daily
  - un_panel_experts_yemen_s_2024_643
  - washington_institute_eisenstadt_levitt_ghaddar
  - crisis_group_vaez_hiltermann_alley
  - rand_iran_houthi_studies
  - cisa_iranian_apt_advisories
  - microsoft_threat_intel_iranian_io_2024

ra_corpus_pointer: "_context/agent-output/ra4-me-cascade-corpus.md"
```

End of RA-4.
