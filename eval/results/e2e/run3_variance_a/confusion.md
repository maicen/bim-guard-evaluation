# BIM-Guard rule extraction vs. human annotation — OBC 2023 Section 9.8

Human gold rules: **89** · Extracted dimensional rules: **23** (of 53 drafts) · Annotated clauses: **117**

## 1. Clause-level confusion matrix
Positive = clause yields at least one checkable rule.

| | Extracted: rule | Extracted: none |
|---|---|---|
| **Human: rule** | TP 13 | FN 37 |
| **Human: none** | FP 4 | TN 63 |

- accuracy: 65.0% [95% CI: 56.0% – 73.0%]
- precision: 76.5% [95% CI: 52.7% – 90.4%]
- recall_sensitivity: 26.0% [95% CI: 15.9% – 39.6%]
- specificity: 94.0% [95% CI: 85.6% – 97.7%]
- f1_score: 38.8% [95% CI: 24.4% – 55.0%]
- balanced_accuracy: 60.0% [95% CI: 50.7% – 68.6%]

## 2. Rule-level matching
TN is undefined for open-ended extraction.

| Mode | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| lenient | 15 | 8 | 74 | 65.2% | 16.9% | 26.8% |
| normalized | 5 | 18 | 84 | 21.7% | 5.6% | 8.9% |
| strict | 5 | 18 | 84 | 21.7% | 5.6% | 8.9% |

Lenient = same clause + operator + value. Normalized additionally requires IFC target and property to agree up to a small synonym table (IfcRamp~IfcRampFlight, ClearHeight~RequiredHeadroom, ...; see _PROPERTY_EQUIV). Strict requires exact target and property (bim-guard alias table only).

## 3. Operator confusion (pairs agreeing on clause and value)

| Human \ Extracted | >= | <= | == | between |
|---|---|---|---|---|
| **>=** | 11 | 0 | 0 | 0 |
| **<=** | 0 | 0 | 0 | 0 |
| **==** | 0 | 0 | 0 | 0 |
| **between** | 0 | 0 | 0 | 1 |

## Missed human rules (lenient FN)

- 9.8.2.1.(1) IfcStairFlight.Width >= 900.0 (base units)
- 9.8.2.1.(2) IfcStairFlight.Width >= 860.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.Width >= 900.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.Width >= 8.0 (base units)
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
- 9.8.6.2.(2) IfcSlab.LandingDimension >= 1100.0 (base units)
- 9.8.6.2.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(6) IfcSlab.Other <= 0.02 (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 1950.0 (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 2050.0 (base units)
- 9.8.7.1.(2) IfcRailing.Other <= 825.0 (base units)
- 9.8.7.1.(4) IfcRailing.HandrailCount >= 1.0 (base units)
- 9.8.7.3.(2) IfcRailing.Other >= 300.0 (base units)
- 9.8.7.1.(5) IfcRailing.HandrailCount >= 1.0 (base units)
- 9.8.7.5.(1) IfcRailing.HandrailClearance >= 60.0 (base units)
- 9.8.7.5.(1) IfcRailing.HandrailClearance >= 50.0 (base units)
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
- 9.8.8.4.(1) IfcRailing.CurbHeight >= 140.0 (base units)
- 9.8.8.4.(1) IfcRailing.GuardHeight >= 1070.0 (base units)
- 9.8.8.5.(1) IfcRailing.GuardOpeningSize <= 100.0 (base units)
- 9.8.8.5.(2) IfcRailing.GuardOpeningSize <= 535.0 (base units)
- 9.8.8.5.(3) IfcRailing.GuardOpeningSize <= 100.0 (base units)
- 9.8.8.5.(3) IfcRailing.GuardOpeningSize >= 200.0 (base units)
- 9.8.9.2.(1) IfcStairFlight.Other >= 150.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerDepth >= 90.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerDepth >= 235.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerThickness >= 25.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerThickness >= 38.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerSpacing <= 900.0 (base units)
- 9.8.9.4.(1) IfcStairFlight.StringerSpacing <= 600.0 (base units)
- 9.8.9.4.(2) IfcStairFlight.StringerSpacing <= 1200.0 (base units)
- 9.8.9.5.(1) IfcStairFlight.TreadThickness >= 25.0 (base units)
- 9.8.9.5.(1) IfcStairFlight.TreadThickness >= 38.0 (base units)
- 9.8.10.2.(1) IfcWall.Other >= 200.0 (base units)
- 9.8.9.6.(5) IfcCovering.Other <= 1.0 (base units)
- 9.8.4.4.(5) IfcStairFlight.Other <= 0.02 (base units)

## Unmatched extracted rules (lenient FP)

- 9.8.9.1.(1) IfcStairFlight.DesignUniformLoad >= 4.8 (base units)
- 9.8.9.1.(1) IfcStairFlight.DesignUniformLoad >= 1.9 (base units)
- 9.8.7.1.(3) IfcRailing.HandrailCount >= 1.0 (base units)
- 9.8.4.1.(4) IfcStairFlight.RunLength <= 355.0 (base units)
- 9.8.4.1.(4) IfcStairFlight.RiserHeight >= 125.0 (base units)
- 9.8.4.1.(2) IfcStairFlight.RunLength <= 355.0 (base units)
- 9.8.4.1.(1) IfcStairFlight.RiserHeight >= 125.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.ClearWidth >= ('rel', 0.0, None) (base units)

## Non-dimensional extracted rules (outside the human gold's scope, not scored)

- 9.8.9.6 IfcStairFlight.FinishMaterial matches mat_finish_ceramic_tile|concrete|plywood_for_unfinished_basement_or_garage_stairs
- 9.8.9.6.(5) IfcStairFlight.SlipResistanceProvision matches slip_resistant_finish|slip_resistant_strips_projection_max_1mm
- 9.8.9.6.(4) IfcStairFlight.TactileAttentionIndicator matches article_3_8_3_18_compliant
- 9.8.9.6.(3) IfcStairFlight.VisualDemarcation matches colour_contrast_or_distinctive_visual_pattern_at_tread_edges_landing_edges_and_ramp_begin_end
- 9.8.9.6.(2) IfcStairFlight.FinishMaterial matches hardwood|vertical_grain_softwood|resilient_flooring|low_pile_carpet
- 9.8.9.6.(1) IfcRampFlight.FinishPerformance matches wear_resistant;slip_resistant;smooth;even;free_from_open_defects
- 9.8.9.6.(1) IfcSlab.FinishPerformance matches wear_resistant;slip_resistant;smooth;even;free_from_open_defects
- 9.8.9.6.(1) IfcStairFlight.FinishPerformance matches wear_resistant;slip_resistant;smooth;even;free_from_open_defects
- 9.8.8.5.(3) IfcRailing.SpherePassageTest matches permits_passage_of_200_mm_sphere
- 9.8.8.5.(3) IfcRailing.SpherePassageTest matches prevents_passage_of_100_mm_sphere
- 9.8.8.5.(2) IfcRailing.SpherePassageTest matches prevents_passage_of_535_mm_sphere
- 9.8.8.5.(1) IfcRailing.SpherePassageTest matches prevents_passage_of_100_mm_sphere
- 9.8.8.2.(5) IfcRailing.ConstructionStandard matches MMAH_SB7_Guards_for_Housing_and_Small_Buildings
- 9.8.8.2.(4) IfcRailing.DemonstratedEffectivePerformance matches true
- 9.8.8.2.(3) IfcRailing.DesignLoadCombination matches specified_guard_loads_not_simultaneous
- 9.8.8.2.(2) IfcRailing.LoadEngagedPickets matches three_pickets_over_300_mm
- 9.8.8.2.(1) IfcRailing.GuardDesignLoadCapacity matches horizontal_line_0.75_kN_per_m_or_point_1.0_kN;element_load_0.5_kN_over_100x100_mm;top_vertical_1.5_kN_per_m
- 9.8.8.2.(2) IfcRailing.GuardDesignLoadCapacity matches horizontal_point_1.0_kN;element_load_0.5_kN_over_100x100_mm;top_vertical_1.5_kN_per_m
- 9.8.8.2.(2) IfcRailing.GuardDesignLoadCapacity matches horizontal_line_0.5_kN_per_m_or_point_1.0_kN;element_load_0.5_kN_over_300x300_mm;top_vertical_1.5_kN_per_m
- 9.8.8.1.(1) IfcRailing.IsGuard exists true
- 9.8.7.1.(1) IfcRailing.HandrailCount >= table_9_8_7_1
- 9.8.7.1.(2) IfcRailing.HandrailCount >= 1_or_2_by_width
- 9.8.6.2.(4) IfcSlab.Width >= adjoining_flight_ramp_width_rule
- 9.8.6.2.(3a) IfcDoor.LandingOmissionPermitted matches true
- 9.8.6.2.(3) IfcSlab.LengthMeasurementMethod matches perpendicular_to_adjacent_nosings_or_ramp_end_at_half_required_length_from_narrow_edge
- 9.8.6.2.(3a) IfcDoor.LandingOmissionPermitted matches true
- 9.8.4.1.(2) IfcStairFlight.StairClassification matches public
- note:9.8.4.1.(1) IfcStairFlight.StairClassification matches private
- 9.8.4.1.(2) IfcStairFlight.RiserHeight between None
- 9.8.4.1.(3) IfcStairFlight.RiserHeight between None
