# BIM-Guard rule extraction vs. human annotation — OBC 2023 Section 9.8

Human gold rules: **116** · Extracted dimensional rules: **28** (of 42 drafts) · Annotated clauses: **129**

## 1. Clause-level confusion matrix
Positive = clause yields at least one checkable rule.

| | Extracted: rule | Extracted: none |
|---|---|---|
| **Human: rule** | TP 11 | FN 48 |
| **Human: none** | FP 1 | TN 69 |

- accuracy: 62.0% [95% CI: 53.4% – 69.9%]
- precision: 91.7% [95% CI: 64.6% – 98.5%]
- recall_sensitivity: 18.6% [95% CI: 10.7% – 30.4%]
- specificity: 98.6% [95% CI: 92.3% – 99.8%]
- f1_score: 31.0% [95% CI: 18.4% – 46.4%]
- balanced_accuracy: 58.6% [95% CI: 51.5% – 65.1%]

## 2. Rule-level matching
TN is undefined for open-ended extraction.

| Mode | TP | FP | FN | Redundant | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| lenient | 22 | 4 | 94 | 2 | 84.6% | 19.0% | 31.0% |
| normalized | 10 | 18 | 106 | 0 | 35.7% | 8.6% | 13.9% |
| strict | 9 | 19 | 107 | 0 | 32.1% | 7.8% | 12.5% |

Redundant = extracted rules restating an already-matched human rule (e.g. one rule per element for 'stairs and ramps'); neither TP nor FP.

Lenient = same clause + operator + value. Normalized additionally requires IFC target and property to agree up to a small synonym table (IfcRamp~IfcRampFlight, ClearHeight~RequiredHeadroom, ...; see _PROPERTY_EQUIV). Strict requires exact target and property (bim-guard alias table only).

## 3. Operator confusion (pairs agreeing on clause and value)

| Human \ Extracted | >= | <= | == | between |
|---|---|---|---|---|
| **>=** | 28 | 0 | 0 | 0 |
| **<=** | 0 | 7 | 0 | 0 |
| **==** | 0 | 0 | 0 | 0 |
| **between** | 0 | 0 | 0 | 0 |

## Missed human rules (lenient FN)

- 9.8.4.4.(5) IfcStairFlight.Other <= 0.02 (base units)
- 9.8.2.1.(2) IfcStairFlight.Width >= 860.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.Width >= 900.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.Width >= 8.0 (base units)
- 9.8.2.1.(4) IfcStairFlight.Width >= 860.0 (base units)
- 9.8.3.2.(1) IfcStairFlight.NumberOfRiser >= 3.0 (base units)
- 9.8.3.3.(1) IfcStairFlight.FlightHeight <= 3700.0 (base units)
- table:9.8.4.1 IfcStairFlight.RiserHeight <= 200.0 (base units)
- table:9.8.4.1 IfcStairFlight.TreadLength >= 255.0 (base units)
- table:9.8.4.1 IfcStairFlight.RiserHeight <= 180.0 (base units)
- table:9.8.4.1 IfcStairFlight.RiserHeight >= 125.0 (base units)
- table:9.8.4.1 IfcStairFlight.TreadLength >= 280.0 (base units)
- table:9.8.4.1 IfcStairFlight.RiserHeight >= 125.0 (base units)
- table:9.8.4.1 IfcStairFlight.TreadLength <= 355.0 (base units)
- table:9.8.4.1 IfcStairFlight.RiserHeight >= 125.0 (base units)
- table:9.8.4.1 IfcStairFlight.TreadLength <= 355.0 (base units)
- table:9.8.4.1 IfcStairFlight.RiserHeight >= 125.0 (base units)
- table:9.8.4.1 IfcStairFlight.TreadLength <= 355.0 (base units)
- table:9.8.4.1 IfcStairFlight.RiserHeight >= 125.0 (base units)
- table:9.8.4.1 IfcStairFlight.TreadLength <= 355.0 (base units)
- 9.8.4.2.(2) IfcStairFlight.TreadLength between ('rel', 0.0, 25.0) (base units)
- 9.8.4.3.(3) IfcStairFlight.TreadLength between ('rel', 0.0, 25.0) (base units)
- 9.8.4.5A.(1) IfcStairFlight.HandrailCount >= 2.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.HandrailHeight >= 1070.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.ClearWidth >= 660.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.RiserHeight <= 240.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.TreadLength >= 190.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.RequiredHeadroom >= 1980.0 (base units)
- 9.8.4.6.(1) IfcStairFlight.Other <= 15.0 (base units)
- 9.8.4.6.(1) IfcStairFlight.Other <= 25.0 (base units)
- 9.8.5.2.(1) IfcRampFlight.Width >= 1100.0 (base units)
- 9.8.5.2.(2) IfcRampFlight.Width >= 860.0 (base units)
- 9.8.5.3.(1) IfcRampFlight.RequiredHeadroom >= 1950.0 (base units)
- 9.8.5.3.(1) IfcRampFlight.RequiredHeadroom >= 2050.0 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.1 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.1 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.166667 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.125 (base units)
- 9.8.6.3.(1) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.3.(1) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.3.(2) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.3.(2) IfcSlab.LandingDimension >= 1100.0 (base units)
- 9.8.6.3.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.3.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.3.(6) IfcSlab.Other <= 0.02 (base units)
- 9.8.6.3.(7) IfcSlab.LandingDimension >= 300.0 (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 1950.0 (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 2050.0 (base units)
- 9.8.7.1.(2) IfcRailing.Other <= 825.0 (base units)
- 9.8.7.1.(4) IfcRailing.HandrailCount >= 1.0 (base units)
- 9.8.7.1.(5) IfcRailing.HandrailCount >= 1.0 (base units)
- 9.8.7.3.(2) IfcRailing.Other >= 300.0 (base units)
- 9.8.7.4.(2) IfcRailing.HandrailHeight between (865.0, 1070.0) (base units)
- 9.8.7.5.(1) IfcRailing.HandrailClearance >= 60.0 (base units)
- 9.8.7.5.(1) IfcRailing.HandrailClearance >= 50.0 (base units)
- 9.8.7.7.(2) IfcRailing.Other <= 1200.0 (base units)
- 9.8.7.7.(2) IfcRailing.Other <= 300.0 (base units)
- 9.8.7.7.(2) IfcRailing.Other >= 2.0 (base units)
- 9.8.7.7.(2) IfcRailing.Other >= 32.0 (base units)
- 9.8.8.1.(4) IfcDoor.Other <= 100.0 (base units)
- 9.8.8.1.(5) IfcWindow.Other <= 100.0 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.0 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 0.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.5 (base units)
- 9.8.8.3.(1) IfcRailing.GuardHeight >= 1070.0 (base units)
- 9.8.8.3.(2) IfcRailing.GuardHeight >= 900.0 (base units)
- 9.8.8.3.(3) IfcRailing.GuardHeight >= 900.0 (base units)
- 9.8.8.3.(4) IfcRailing.GuardHeight >= 900.0 (base units)
- 9.8.8.3.(6) IfcRailing.GuardHeight >= 1500.0 (base units)
- 9.8.8.5.(1) IfcRailing.GuardOpeningSize <= 100.0 (base units)
- 9.8.8.5.(2) IfcRailing.GuardOpeningSize <= 535.0 (base units)
- 9.8.8.5.(3) IfcRailing.GuardOpeningSize <= 100.0 (base units)
- 9.8.8.5.(3) IfcRailing.GuardOpeningSize >= 200.0 (base units)
- 9.8.9.2.(1) IfcStairFlight.Other >= 150.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerDepth >= 90.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerDepth >= 235.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerThickness >= 25.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerThickness >= 38.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerSpacing <= 600.0 (base units)
- 9.8.9.6.(5) IfcCovering.Other <= 1.0 (base units)
- 9.8.10.2.(1) IfcWall.Other >= 200.0 (base units)
- 9.8.4.3.(1) IfcStairFlight.TreadLength >= 150.0 (base units)
- 9.8.4.4.(1) IfcStairFlight.Other <= 5.0 (base units)
- 9.8.4.4.(1) IfcStairFlight.Other <= 10.0 (base units)
- 9.8.4.4.(2) IfcStairFlight.Other <= 0.083333 (base units)
- 9.8.4.4.(3) IfcStairFlight.Other <= 5.0 (base units)
- 9.8.4.4.(3) IfcStairFlight.Other <= 10.0 (base units)
- 9.8.4.5.(1) IfcStairFlight.Other <= 90.0 (base units)
- 9.8.4.5.(1) IfcStairFlight.Other >= 30.0 (base units)
- 9.8.4.5.(1) IfcStairFlight.Other <= 45.0 (base units)
- 9.8.4.5.(2) IfcStairFlight.Other >= 1200.0 (base units)
- 9.8.5.5.(1) IfcRampFlight.Other <= 1500.0 (base units)
- 9.8.7.6.(1) IfcRailing.Other <= 100.0 (base units)

## Unmatched extracted rules (lenient FP)

- table:9.8.7.1 IfcRailing.HandrailSideCount == 2.0 (base units)
- table:9.8.7.1 IfcRailing.HandrailSideCount == 1.0 (base units)
- table:9.8.7.1 IfcRailing.HandrailSideCount == 2.0 (base units)
- table:9.8.7.1 IfcRailing.HandrailSideCount == 1.0 (base units)

## Non-dimensional extracted rules (outside the human gold's scope, not scored)

- 9.8.8.4.(2) IfcRailing.VehicleGuardrailLoadCompliance matches Sentence_4_1_5_15_1
- 9.8.8.1.(8) IfcWindow.GlazingProtection matches guard_OR_non_openable_load_resistant_glazing
- 9.8.8.1.(7) IfcWindow.GlazingProtection matches guard_OR_non_openable_load_resistant_glazing
- 9.8.8.1.(5) IfcWindow.OpeningProtection matches guard_OR_sphere_restricting_mechanism
- 9.8.8.1.(4) IfcDoor.GuardOrOpeningControl matches guard_OR_opening_control_100mm
- 9.8.4.3.(1) IfcStairFlight.TaperedTreadRunAt300mm matches applicable_Table_9_8_4_1_rectangular_tread_dimensions
- table:9.8.4.1 IfcStairFlight.TreadLength matches no_table_minimum
- table:9.8.4.1 IfcStairFlight.RiserHeight matches no_table_maximum
- 9.8.3.1.(4) IfcStair.SpiralStairCompliance matches Article_9_8_4_5A
- 9.8.3.1.(3) IfcStairFlight.ExitCurvedFlightCompliance matches Sentence_3_4_6_9_2
- 9.8.1.4.(1) IfcTransportElement.Part3Compliance matches Part_3_requirements
- 9.8.1.3.(1) IfcStair.ExitRequirementsReference matches Sections_9_9_and_9_10
- 9.8.1.2.(1) IfcStair.GarageDwellingUnitRequirement matches dwelling_unit_requirements
- 9.8.1.1.(1) IfcStair.SectionScope matches interior_or_exterior_stairs_steps_ramps_landings_handrails_guards
