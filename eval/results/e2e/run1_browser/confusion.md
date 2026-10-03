# BIM-Guard rule extraction vs. human annotation — OBC 2023 Section 9.8

Human gold rules: **89** · Extracted dimensional rules: **58** (of 104 drafts) · Annotated clauses: **117**

## 1. Clause-level confusion matrix
Positive = clause yields at least one checkable rule.

| | Extracted: rule | Extracted: none |
|---|---|---|
| **Human: rule** | TP 37 | FN 13 |
| **Human: none** | FP 0 | TN 67 |

- accuracy: 88.9% [95% CI: 81.9% – 93.4%]
- precision: 100.0% [95% CI: 90.6% – 100.0%]
- recall_sensitivity: 74.0% [95% CI: 60.5% – 84.1%]
- specificity: 100.0% [95% CI: 94.6% – 100.0%]
- f1_score: 85.1% [95% CI: 72.5% – 91.4%]
- balanced_accuracy: 87.0% [95% CI: 77.5% – 92.1%]

## 2. Rule-level matching
TN is undefined for open-ended extraction.

| Mode | TP | FP | FN | Redundant | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| lenient | 57 | 1 | 32 | 0 | 98.3% | 64.0% | 77.6% |
| normalized | 42 | 16 | 47 | 0 | 72.4% | 47.2% | 57.1% |
| strict | 17 | 41 | 72 | 0 | 29.3% | 19.1% | 23.1% |

Redundant = extracted rules restating an already-matched human rule (e.g. one rule per element for 'stairs and ramps'); neither TP nor FP.

Lenient = same clause + operator + value. Normalized additionally requires IFC target and property to agree up to a small synonym table (IfcRamp~IfcRampFlight, ClearHeight~RequiredHeadroom, ...; see _PROPERTY_EQUIV). Strict requires exact target and property (bim-guard alias table only).

## 3. Operator confusion (pairs agreeing on clause and value)

| Human \ Extracted | >= | <= | == | between |
|---|---|---|---|---|
| **>=** | 37 | 0 | 1 | 0 |
| **<=** | 0 | 16 | 0 | 0 |
| **==** | 0 | 0 | 0 | 0 |
| **between** | 0 | 0 | 0 | 1 |

## Missed human rules (lenient FN)

- 9.8.2.1.(3) IfcStairFlight.Width >= 900.0 (base units)
- 9.8.2.1.(3) IfcStairFlight.Width >= 8.0 (base units)
- 9.8.3.3.(1) IfcStairFlight.FlightHeight <= 3700.0 (base units)
- 9.8.3.2.(1) IfcStairFlight.NumberOfRiser >= 3.0 (base units)
- 9.8.4.2.(2) IfcStairFlight.TreadLength between ('rel', 0.0, 25.0) (base units)
- 9.8.6.2.(2) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(2) IfcSlab.LandingDimension >= 1100.0 (base units)
- 9.8.6.2.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.2.(4) IfcSlab.LandingDimension >= ('rel', 0.0, None) (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 1950.0 (base units)
- 9.8.6.4.(1) IfcSlab.RequiredHeadroom >= 2050.0 (base units)
- 9.8.7.1.(4) IfcRailing.HandrailCount >= 1.0 (base units)
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
- 9.8.8.5.(3) IfcRailing.GuardOpeningSize >= 200.0 (base units)
- 9.8.9.2.(1) IfcStairFlight.Other >= 150.0 (base units)
- 9.8.4.4.(5) IfcStairFlight.Other <= 0.02 (base units)

## Unmatched extracted rules (lenient FP)

- 9.8.7.1.(4) IfcRailing.HandrailCount == 1.0 (base units)

## Non-dimensional extracted rules (outside the human gold's scope, not scored)

- 9.8.1.1.(1) IfcStair.SectionApplicability matches interior_or_exterior_stair_step_ramp_landing_handrail_guard
- 9.8.1.2.(1) IfcStair.DwellingUnitGarageCompliance matches dwelling_unit_requirements
- 9.8.1.3.(1) IfcStair.ExitSectionCompliance exists Sections_9_9_and_9_10_compliant
- 9.8.1.4.(1) IfcTransportElement.Part3Compliance exists true
- 9.8.2.1.(3) IfcStairFlight.ClearWidth >= max(900,8*OccupantLoad)
- 9.8.3.1.(1) IfcStair.StairType matches straight|curved|spiral
- 9.8.3.1.(2) IfcStairFlight.TreadConfiguration matches rectangular_with_permitted_winders|rectangular_and_tapered_same_turn_direction
- 9.8.3.1.(3) IfcStairFlight.CurvedExitCompliance exists 3.4.6.9.2_compliant
- 9.8.3.1.(4) IfcStair.SpiralStairCompliance exists 9.8.4.5A_compliant
- 9.8.4.5A.(1) IfcStairFlight.TreadUniformity matches consistent_angle_uniform_dimension_same_turn_direction
- 9.8.4.5A.(2) IfcStair.OnlyMeansOfEgress matches permitted
- 9.8.4.5A.(3) IfcStair.ServesAsExit == false
- 9.8.4.2.(1) IfcStairFlight.TreadRun matches Table_9.8.4.1_rectangular_tread_run
- 9.8.4.3 IfcStairFlight.TaperedTreadExitCompliance exists 3.4.6.9_compliant_at_any_point
- 9.8.6.2.(2) IfcSlab.Length >= min(RequiredStairOrRampWidth,1100)
- 9.8.6.2.(2a) IfcDoor.LandingOmissionQualification matches permitted
- 9.8.6.2.(3a) IfcDoor.LandingOmissionQualification matches permitted
- 9.8.6.2.(3) IfcSlab.LandingLengthMeasurement matches perpendicular_from_narrow_edge_at_half_required_length
- 9.8.6.2.(4) IfcSlab.Width matches adjacent_width_rule_compliant
- 9.8.6.2.(5) IfcDoor.SwingClearanceOverLanding exists true
- 9.8.7.1.(1) IfcRailing.HandrailCount >= table_9.8.7.1_required_sides
- 9.8.7.1.(3) IfcStairFlight.HandrailRequired == false
- 9.8.7.2.(1) IfcRailing.IsContinuous exists true
- 9.8.7.2.(2) IfcRailing.IsContinuous exists true
- 9.8.7.3.(1) IfcRailing.SafeTermination exists true
- 9.8.7.5.(2) IfcRailing.ContinuouslyGraspable exists true
- 9.8.8.1.(1) IfcSlab.UnprotectedEdgeGuardCount >= UnprotectedSideCount
- 9.8.8.1.(4) IfcDoor.GuardOrOpeningControl matches guard_or_controlled_opening_<=100mm
- table:9.8.8.2 IfcRailing.GuardDesignLoad matches horizontal_0.5_kN_per_m_or_1.0_kN_concentrated;outward_0.5_kN_over_300x300_mm;vertical_1.5_kN_per_m
- table:9.8.8.2 IfcRailing.GuardDesignLoad matches horizontal_concentrated_1.0_kN;outward_0.5_kN_over_100x100_mm;vertical_1.5_kN_per_m
- table:9.8.8.2 IfcRailing.GuardDesignLoad matches horizontal_0.75_kN_per_m_or_1.0_kN_concentrated;outward_0.5_kN_over_100x100_mm;vertical_1.5_kN_per_m
- 9.8.8.4.(2) IfcRailing.VehicleGuardrailDesignLoad matches 4.1.5.15.1
- 9.8.8.5.(3) IfcRailing.MaximumOpening matches permits_200_mm_sphere
- 9.8.8.7.(1) IfcRailing.GlassType matches laminated_safety_glass|tempered_safety_glass|wired_safety_glass
- 9.8.9.2.(1) IfcStair.SupportSystem matches masonry_or_concrete_support_>=150mm|cantilevered_from_main_foundation_wall
- 9.8.9.2.(3) IfcStair.FoundationDepthCompliance exists Section_9.12_compliant
- 9.8.9.3.(1) IfcStair.WoodPreservativeTreatment exists true
- 9.8.9.4.(1) IfcStairFlight.StringerEndSupport exists top_and_bottom_secured
- 9.8.9.5.(2) IfcStairFlight.TreadFaceOrientation matches perpendicular_to_stringers
- 9.8.9.6.(1) IfcStairFlight.FinishPerformance matches wear_resistant;slip_resistant;smooth_even;free_from_open_defects
- 9.8.9.6.(2) IfcStairFlight.FinishMaterial matches hardwood|vertical_grain_softwood|resilient_flooring|low_pile_carpet|mat_finish_ceramic_tile|concrete|plywood_for_unfinished_basement_or_garage
- 9.8.9.6.(3) IfcStairFlight.VisualDemarcation matches colour_contrast_or_distinctive_visual_pattern_at_tread_edges_landing_edges_ramp_ends
- 9.8.9.6.(4) IfcBuildingElementProxy.TactileAttentionIndicatorCompliance exists Article_3.8.3.18_compliant
- 9.8.9.6.(5) IfcStairFlight.SlipResistantFinish exists true
- 9.8.10.1.(1) IfcStair.CantileverStepLoadDesign exists true
- 9.8.10.3.(1) IfcStair.FreezeUpliftProtection exists true
