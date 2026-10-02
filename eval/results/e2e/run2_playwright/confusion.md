# BIM-Guard rule extraction vs. human annotation — OBC 2023 Section 9.8

Human gold rules: **89** · Extracted dimensional rules: **29** (of 48 drafts) · Annotated clauses: **117**

## 1. Clause-level confusion matrix
Positive = clause yields at least one checkable rule.

| | Extracted: rule | Extracted: none |
|---|---|---|
| **Human: rule** | TP 11 | FN 39 |
| **Human: none** | FP 3 | TN 64 |

- accuracy: 64.1% [95% CI: 55.1% – 72.2%]
- precision: 78.6% [95% CI: 52.4% – 92.4%]
- recall_sensitivity: 22.0% [95% CI: 12.8% – 35.2%]
- specificity: 95.5% [95% CI: 87.6% – 98.5%]
- f1_score: 34.4% [95% CI: 20.5% – 51.0%]
- balanced_accuracy: 58.8% [95% CI: 50.2% – 66.9%]

## 2. Rule-level matching
TN is undefined for open-ended extraction.

| Mode | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| lenient | 19 | 10 | 70 | 65.5% | 21.3% | 32.2% |
| normalized | 12 | 17 | 77 | 41.4% | 13.5% | 20.3% |
| strict | 7 | 22 | 82 | 24.1% | 7.9% | 11.9% |

Lenient = same clause + operator + value. Normalized additionally requires IFC target and property to agree up to a small synonym table (IfcRamp~IfcRampFlight, ClearHeight~RequiredHeadroom, ...; see _PROPERTY_EQUIV). Strict requires exact target and property (bim-guard alias table only).

## 3. Operator confusion (pairs agreeing on clause and value)

| Human \ Extracted | >= | <= | == | between |
|---|---|---|---|---|
| **>=** | 12 | 1 | 0 | 0 |
| **<=** | 0 | 6 | 0 | 0 |
| **==** | 0 | 0 | 0 | 0 |
| **between** | 0 | 0 | 0 | 0 |

## Missed human rules (lenient FN)

- 9.8.2.1.(1) IfcStairFlight.Width >= 900.0 (base units)
- 9.8.2.1.(2) IfcStairFlight.Width >= 860.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.Width >= 900.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.Width >= 8.0 (base units)
- 9.8.2.1.(4) IfcStairFlight.Width >= 860.0 (base units)
- 9.8.2.2.(3) IfcStairFlight.RequiredHeadroom >= 1950.0 (base units)
- 9.8.2.2.(2) IfcStairFlight.RequiredHeadroom >= 2050.0 (base units)
- 9.8.3.3.(1) IfcStairFlight.FlightHeight <= 3700.0 (base units)
- 9.8.3.2.(1) IfcStairFlight.NumberOfRiser >= 3.0 (base units)
- 9.8.4.3.(3) IfcStairFlight.TreadLength between ('rel', 0.0, 25.0) (base units)
- 9.8.4.5A.(1) IfcStairFlight.HandrailCount >= 2.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.HandrailHeight >= 1070.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.ClearWidth >= 660.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.RiserHeight <= 240.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.TreadLength >= 190.0 (base units)
- 9.8.4.5A.(1) IfcStairFlight.RequiredHeadroom >= 1980.0 (base units)
- 9.8.4.2.(2) IfcStairFlight.TreadLength between ('rel', 0.0, 25.0) (base units)
- 9.8.4.6.(1) IfcStairFlight.Other <= 15.0 (base units)
- 9.8.4.6.(1) IfcStairFlight.Other <= 25.0 (base units)
- 9.8.5.3.(1) IfcRampFlight.RequiredHeadroom >= 1950.0 (base units)
- 9.8.5.3.(1) IfcRampFlight.RequiredHeadroom >= 2050.0 (base units)
- 9.8.5.2.(2) IfcRampFlight.Width >= 860.0 (base units)
- 9.8.5.2.(1) IfcRampFlight.Width >= 1100.0 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.1 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.1 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.166667 (base units)
- 9.8.5.4.(1) IfcRampFlight.RampSlope <= 0.125 (base units)
- 9.8.6.2.(1) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(1) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(6) IfcSlab.Other <= 0.02 (base units)
- 9.8.6.2.(7) IfcSlab.LandingDimension >= 300.0 (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 1950.0 (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 2050.0 (base units)
- 9.8.7.1.(2) IfcRailing.Other <= 825.0 (base units)
- 9.8.7.3.(2) IfcRailing.Other >= 300.0 (base units)
- 9.8.7.1.(5) IfcRailing.HandrailCount >= 1.0 (base units)
- 9.8.7.5.(1) IfcRailing.HandrailClearance >= 60.0 (base units)
- 9.8.7.5.(1) IfcRailing.HandrailClearance >= 50.0 (base units)
- 9.8.7.4.(2) IfcRailing.HandrailHeight between (865.0, 1070.0) (base units)
- 9.8.7.7.(2) IfcRailing.Other <= 1200.0 (base units)
- 9.8.7.7.(2) IfcRailing.Other <= 300.0 (base units)
- 9.8.7.7.(2) IfcRailing.Other >= 2.0 (base units)
- 9.8.7.7.(2) IfcRailing.Other >= 32.0 (base units)
- 9.8.8.1.(4) IfcDoor.Other <= 100.0 (base units)
- 9.8.8.1.(5) IfcWindow.Other <= 100.0 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 0.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.0 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 0.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.0 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 0.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 0.75 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.0 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 0.5 (base units)
- table:9.8.8.2 IfcRailing.GuardLoad >= 1.5 (base units)
- 9.8.8.3.(1) IfcRailing.GuardHeight >= 1070.0 (base units)
- 9.8.8.3.(2) IfcRailing.GuardHeight >= 900.0 (base units)
- 9.8.8.3.(3) IfcRailing.GuardHeight >= 900.0 (base units)
- 9.8.8.4.(1) IfcRailing.CurbHeight >= 140.0 (base units)
- 9.8.8.4.(1) IfcRailing.GuardHeight >= 1070.0 (base units)
- 9.8.8.3.(4) IfcRailing.GuardHeight >= 900.0 (base units)
- 9.8.8.3.(6) IfcRailing.GuardHeight >= 1500.0 (base units)
- 9.8.8.5.(3) IfcRailing.GuardOpeningSize >= 200.0 (base units)
- 9.8.9.2.(1) IfcStairFlight.Other >= 150.0 (base units)
- 9.8.10.2.(1) IfcWall.Other >= 200.0 (base units)
- 9.8.9.6.(5) IfcCovering.Other <= 1.0 (base units)
- 9.8.4.4.(5) IfcStairFlight.Other <= 0.02 (base units)

## Unmatched extracted rules (lenient FP)

- 9.8.9.1.(1) IfcStairFlight.DesignUniformLoad >= 4.8 (base units)
- 9.8.9.1.(1) IfcStairFlight.DesignUniformLoad >= 1.9 (base units)
- 9.8.8.5.(3) IfcRailing.MaximumOpening <= 200.0 (base units)
- 9.8.8.2.(1) IfcRailing.VerticalDesignLoad >= 1.5 (base units)
- 9.8.8.2.(2) IfcRailing.HorizontalDesignLoad >= 1.0 (base units)
- 9.8.7.1.(2) IfcRailing.RailingRole >= 2.0 (base units)
- 9.8.7.1.(2) IfcRailing.RailingRole >= 2.0 (base units)
- 9.8.7.1.(1) IfcRailing.RailingRole >= 1.0 (base units)
- 9.8.7.1.(1) IfcRailing.RailingRole >= 1.0 (base units)
- 9.8.7.1.(4) IfcRailing.RailingRole >= 1.0 (base units)

## Non-dimensional extracted rules (outside the human gold's scope, not scored)

- 9.8.9.6.(5) IfcRamp.SlipResistanceFinish matches slip_resistant_finish|slip_resistant_strips_projection_max_1mm
- 9.8.9.6.(5) IfcStairFlight.SlipResistanceFinish matches slip_resistant_finish|slip_resistant_strips_projection_max_1mm
- 9.8.9.6.(1) IfcRamp.FinishPerformance matches wear_resistant_and_slip_resistant_and_smooth_even_defect_free
- 9.8.9.6.(1) IfcStairFlight.FinishPerformance matches wear_resistant_and_slip_resistant_and_smooth_even_defect_free
- 9.8.8.2.(5) IfcRailing.ComplianceStandard matches MMAH_SB7_Guards_for_Housing_and_Small_Buildings
- 9.8.8.2.(4) IfcRailing.EffectivePerformanceDemonstrated matches true
- 9.8.8.2.(3) IfcRailing.LoadsActSimultaneously matches false
- 9.8.8.2.(2) IfcRailing.PicketLoadEngagement matches three_pickets_engaged_over_300mm_width
- 9.8.8.2.(1) IfcRailing.OutwardElementDesignLoad matches 0.5_kN_over_100mm_by_100mm_area
- 9.8.8.2.(1) IfcRailing.OutwardElementDesignLoad matches 0.5_kN_over_100mm_by_100mm_area
- 9.8.8.2.(2) IfcRailing.OutwardElementDesignLoad matches 0.5_kN_over_max_300mm_by_300mm_area
- 9.8.8.2.(1) IfcRailing.HorizontalDesignLoad matches distributed_0.75_kN_per_m_or_concentrated_1.0_kN
- 9.8.8.2.(2) IfcRailing.HorizontalDesignLoad matches distributed_0.5_kN_per_m_or_concentrated_1.0_kN
- 9.8.8.1.(1) IfcRailing.RailingRole exists true
- 9.8.8.1.(1) IfcRailing.RailingRole exists true
- 9.8.7.7.(2) IfcRailing.AttachmentCompliance matches wood_stud_or_blocking_attachment_1200mm_spacing_300mm_end_offset_two_no8_screws_32mm_penetration
- 9.8.7.5.(2) IfcRailing.Graspability matches continually_graspable_full_length_without_obstruction
- 9.8.7.3.(1) IfcRailing.TerminationCondition matches does_not_obstruct_pedestrian_travel_or_create_hazard
- 9.8.7.2.(2) IfcRailing.IsContinuous matches continuous_except_doorways_landings_and_newel_posts_at_changes_in_direction
