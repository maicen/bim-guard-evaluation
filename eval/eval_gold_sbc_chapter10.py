"""
eval_gold_sbc_chapter10.py
------------------------------------------------
Hand-annotated ground truth for the Saudi Building Code (SBC-201-2007),
Chapter 8 ("Means of Egress", transposing IBC Chapter 10 provisions into metric standards).

Provenance
----------
Annotator:    Osama Ata & Adjudicated Domain Consensus
Source doc:   Saudi Building Code: Architectural Requirements (SBC-201-2007),
              Chapter 8 ("Means of Egress"), Sections 8.3 through 8.17.
Source file:  sources/SBC-201-2007.md (committed in-repo; 10,334 lines, Chapter 8 lines 4789-5600)
Schema:       RuleExtractionProvider dict shape matching LlamaIndexRuleGenerator and RuleConverter.
"""

from __future__ import annotations

SOURCE_TEXT = """\
8.3.2 Ceiling height. The means of egress shall have a ceiling height of not less than 2 meters.

8.3.3.3 Horizontal projections. Structural elements, fixtures or furnishings shall not project horizontally from either side more than 100 mm over any walking surface between the heights of 685 mm and 2.1 meters above the walking surface.

8.3.5 Elevation change. Where changes in elevation of less than 300 mm exist in the means of egress, sloped surfaces shall be used. Where the slope is greater than one unit vertical in 20 units horizontal (5 percent slope), ramps complying with Section 8.10 shall be used.

8.5.2 Door encroachment. Doors opening into the path of egress travel shall not reduce the required width to less than one-half during the course of the swing. When fully open, the door shall not project more than 180 mm into the required width.

8.8.1.1 Size of doors. The minimum width of each door opening shall be sufficient for the occupant load thereof and shall provide a clear width of not less than 810 mm. The maximum width of a swinging door leaf shall be 1.2 meters nominal. The height of doors shall not be less than 2.1 meters.

8.8.1.5 Landings at doors. Landings shall have a width not less than the width of the stairway or the door, whichever is the greater. Landings shall have a length measured in the direction of travel of not less than 1.1 meters.

8.8.1.6 Thresholds. Thresholds at doorways shall not exceed 19 mm in height for sliding doors serving dwelling units or 12.7 mm for other doors.

8.8.1.7 Door arrangement. Space between two doors in series shall be 1.2 meters minimum plus the width of a door swinging into the space.

8.9.1 Stairway width. The width of stairways shall be determined as specified in Section 8.5.1, but such width shall not be less than 1.1 meters.

8.9.2 Headroom. Stairways shall have a minimum headroom clearance of not less than 2032 mm measured vertically from the sloped plane connecting tread nosings.

8.9.3.1 Dimension reference. Stair riser heights shall be 178 mm maximum and 102 mm minimum. The minimum tread depth shall be 280 mm.

8.9.3.2 Profile. The radius of curvature at the leading edge of the tread shall be not greater than 12.7 mm. The leading edge (nosings) of treads shall project not more than 30 mm beyond the tread below.

8.9.7 Circular stairways. The minimum tread depth measured 300 mm from the narrower end of the tread shall not be less than 280 mm.

8.9.10.2 Treads of alternating tread devices. Alternating tread devices shall have a minimum tread depth of 215 mm and a maximum riser height of 240 mm.

8.9.11 Handrails. Stairways shall have handrails on each side in accordance with this section.

8.9.11.1 Height. Handrail height, measured above stair tread nosings, shall exist uniformly between 864 mm and 965 mm.

8.10.2 Slope. Ramps used as part of a means of egress shall have a running slope not steeper than one unit vertical in 12 units horizontal (8 percent slope).

8.10.8 Handrails. Ramps with a rise greater than 150 mm shall have handrails on both sides.

8.12.2 Height. Guards shall form a protective barrier not less than 1067 mm high, measured vertically above the adjacent walking surface.

8.12.3 Opening limitations. Open guards shall have balusters or ornamental patterns such that a 102 mm diameter sphere cannot pass through any opening.

8.16.1 Travel distance. In buildings without an automatic sprinkler system, exit access travel distance shall not exceed 61 meters.

8.17.2 Width. The minimum corridor width shall be not less than 1118 mm where serving an occupant load of 50 or more.
"""

GOLD_RULES = [
    {
        "clause_ref": "8.3.2",
        "description": "Egress ceiling height minimum 2.0 m",
        "target_entity": "IfcSpace",
        "property_name": "ClearHeight",
        "operator": ">=",
        "reference_value": 2.0,
        "unit": "m",
        "applicability": "means of egress",
    },
    {
        "clause_ref": "8.3.3.3",
        "description": "Horizontal protrusion maximum 100 mm",
        "target_entity": "IfcBuildingElement",
        "property_name": "HorizontalProtrusion",
        "operator": "<=",
        "reference_value": 100.0,
        "unit": "mm",
        "applicability": "walking surface 685mm to 2100mm",
    },
    {
        "clause_ref": "8.3.5",
        "description": "Egress elevation change ramp threshold 300 mm",
        "target_entity": "IfcRampFlight",
        "property_name": "ElevationChangeThreshold",
        "operator": "<=",
        "reference_value": 300.0,
        "unit": "mm",
        "applicability": "elevation change",
    },
    {
        "clause_ref": "8.5.2",
        "description": "Door open encroachment maximum 180 mm",
        "target_entity": "IfcDoor",
        "property_name": "OpenProjection",
        "operator": "<=",
        "reference_value": 180.0,
        "unit": "mm",
        "applicability": "fully open door into egress",
    },
    {
        "clause_ref": "8.8.1.1",
        "description": "Door clear opening width minimum 810 mm",
        "target_entity": "IfcDoor",
        "property_name": "ClearWidth",
        "operator": ">=",
        "reference_value": 810.0,
        "unit": "mm",
        "applicability": "means of egress door",
    },
    {
        "clause_ref": "8.8.1.1",
        "description": "Swinging door leaf maximum width 1.2 m",
        "target_entity": "IfcDoor",
        "property_name": "OverallWidth",
        "operator": "<=",
        "reference_value": 1.2,
        "unit": "m",
        "applicability": "swinging door leaf",
    },
    {
        "clause_ref": "8.8.1.1",
        "description": "Door height minimum 2.1 m",
        "target_entity": "IfcDoor",
        "property_name": "OverallHeight",
        "operator": ">=",
        "reference_value": 2.1,
        "unit": "m",
        "applicability": "means of egress door",
    },
    {
        "clause_ref": "8.8.1.5",
        "description": "Door landing length minimum 1.1 m",
        "target_entity": "IfcSpace",
        "property_name": "LandingLength",
        "operator": ">=",
        "reference_value": 1.1,
        "unit": "m",
        "applicability": "landings at doors",
    },
    {
        "clause_ref": "8.8.1.6",
        "description": "Sliding door threshold maximum height 19 mm",
        "target_entity": "IfcDoor",
        "property_name": "ThresholdHeight",
        "operator": "<=",
        "reference_value": 19.0,
        "unit": "mm",
        "applicability": "sliding doors",
    },
    {
        "clause_ref": "8.8.1.6",
        "description": "Standard door threshold maximum height 12.7 mm",
        "target_entity": "IfcDoor",
        "property_name": "ThresholdHeight",
        "operator": "<=",
        "reference_value": 12.7,
        "unit": "mm",
        "applicability": "other than sliding doors",
    },
    {
        "clause_ref": "8.8.1.7",
        "description": "Door series minimum spacing 1.2 m",
        "target_entity": "IfcSpace",
        "property_name": "DoorSeriesClearance",
        "operator": ">=",
        "reference_value": 1.2,
        "unit": "m",
        "applicability": "doors in series",
    },
    {
        "clause_ref": "8.9.1",
        "description": "Stairway width minimum 1.1 m",
        "target_entity": "IfcStairFlight",
        "property_name": "Width",
        "operator": ">=",
        "reference_value": 1.1,
        "unit": "m",
        "applicability": "stairways",
    },
    {
        "clause_ref": "8.9.2",
        "description": "Stairway minimum headroom 2032 mm",
        "target_entity": "IfcStairFlight",
        "property_name": "Headroom",
        "operator": ">=",
        "reference_value": 2032.0,
        "unit": "mm",
        "applicability": "stairways",
    },
    {
        "clause_ref": "8.9.3.1",
        "description": "Stair riser maximum height 178 mm",
        "target_entity": "IfcStairFlight",
        "property_name": "RiserHeight",
        "operator": "<=",
        "reference_value": 178.0,
        "unit": "mm",
        "applicability": "stairways",
    },
    {
        "clause_ref": "8.9.3.1",
        "description": "Stair riser minimum height 102 mm",
        "target_entity": "IfcStairFlight",
        "property_name": "RiserHeight",
        "operator": ">=",
        "reference_value": 102.0,
        "unit": "mm",
        "applicability": "stairways",
    },
    {
        "clause_ref": "8.9.3.1",
        "description": "Stair tread minimum depth 280 mm",
        "target_entity": "IfcStairFlight",
        "property_name": "TreadLength",
        "operator": ">=",
        "reference_value": 280.0,
        "unit": "mm",
        "applicability": "stairways",
    },
    {
        "clause_ref": "8.9.3.2",
        "description": "Tread leading edge nosing projection maximum 30 mm",
        "target_entity": "IfcStairFlight",
        "property_name": "NosingProjection",
        "operator": "<=",
        "reference_value": 30.0,
        "unit": "mm",
        "applicability": "stairways",
    },
    {
        "clause_ref": "8.9.7",
        "description": "Circular stairway tread depth minimum 280 mm",
        "target_entity": "IfcStairFlight",
        "property_name": "TreadLength",
        "operator": ">=",
        "reference_value": 280.0,
        "unit": "mm",
        "applicability": "circular stairways",
    },
    {
        "clause_ref": "8.9.10.2",
        "description": "Alternating tread device maximum riser 240 mm",
        "target_entity": "IfcStairFlight",
        "property_name": "RiserHeight",
        "operator": "<=",
        "reference_value": 240.0,
        "unit": "mm",
        "applicability": "alternating tread devices",
    },
    {
        "clause_ref": "8.9.11",
        "description": "Stairway handrails required on each side",
        "target_entity": "IfcRailing",
        "property_name": "HandrailCount",
        "operator": ">=",
        "reference_value": 2.0,
        "unit": "count",
        "applicability": "stairways",
    },
    {
        "clause_ref": "8.9.11.1",
        "description": "Handrail height minimum 864 mm",
        "target_entity": "IfcRailing",
        "property_name": "Height",
        "operator": ">=",
        "reference_value": 864.0,
        "unit": "mm",
        "applicability": "handrails",
    },
    {
        "clause_ref": "8.9.11.1",
        "description": "Handrail height maximum 965 mm",
        "target_entity": "IfcRailing",
        "property_name": "Height",
        "operator": "<=",
        "reference_value": 965.0,
        "unit": "mm",
        "applicability": "handrails",
    },
    {
        "clause_ref": "8.10.2",
        "description": "Ramp running slope maximum 1 in 12",
        "target_entity": "IfcRampFlight",
        "property_name": "Slope",
        "operator": "<=",
        "reference_value": 0.0833,
        "unit": "ratio",
        "applicability": "means of egress ramps",
    },
    {
        "clause_ref": "8.10.8",
        "description": "Ramp handrails required for rise > 150 mm",
        "target_entity": "IfcRailing",
        "property_name": "RiseThreshold",
        "operator": ">",
        "reference_value": 150.0,
        "unit": "mm",
        "applicability": "ramps",
    },
    {
        "clause_ref": "8.12.2",
        "description": "Guard barrier height minimum 1067 mm",
        "target_entity": "IfcRailing",
        "property_name": "Height",
        "operator": ">=",
        "reference_value": 1067.0,
        "unit": "mm",
        "applicability": "guards",
    },
    {
        "clause_ref": "8.12.3",
        "description": "Guard opening diameter maximum 102 mm",
        "target_entity": "IfcRailing",
        "property_name": "OpeningClearance",
        "operator": "<=",
        "reference_value": 102.0,
        "unit": "mm",
        "applicability": "guards",
    },
    {
        "clause_ref": "8.16.1",
        "description": "Exit access travel distance unsprinklered maximum 61 m",
        "target_entity": "IfcSpace",
        "property_name": "MaxTravelDistance",
        "operator": "<=",
        "reference_value": 61.0,
        "unit": "m",
        "applicability": "unsprinklered egress",
    },
    {
        "clause_ref": "8.17.2",
        "description": "Corridor width minimum 1118 mm for occupant load 50+",
        "target_entity": "IfcSpace",
        "property_name": "CorridorWidth",
        "operator": ">=",
        "reference_value": 1118.0,
        "unit": "mm",
        "applicability": "corridors serving >= 50",
    },
]

EXCLUDED_CLAUSES = [
    {
        "clause_ref": "8.1.1",
        "reason": "Administrative scope statement (no discrete checkable property)",
    },
    {
        "clause_ref": "8.1.2",
        "reason": "General legal prohibition against reducing capacity (unquantified)",
    },
    {
        "clause_ref": "8.1.3",
        "reason": "Maintenance reference to SBC 801 (cross-code pointer, non-geometric)",
    },
    {
        "clause_ref": "8.4.1.2",
        "reason": "Occupant load factor table lookup (requires Table 8.4.1.2 area formula)",
    },
]
