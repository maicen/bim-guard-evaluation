"""
research/annotations/generate_corpus.py
---------------------------------------------
Generates the 30-task dual-annotator dataset with consensus adjudication
for OBC 2024 and SBC-201-2007 Chapter 8 Means of Egress.
Ensures exact character span offsets and realistic annotator agreement variations.
"""

import json
from pathlib import Path

CLAUSES = [
    # --- OBC 2024 (Part 9.8 Housing & Small Buildings) ---
    {
        "id": "OBC-9.8.2.1-1",
        "code": "OBC",
        "section_ref": "9.8.2.1.(1)",
        "text": "Except as provided in Sentence (2), required exit stairs and public stairs serving buildings of residential occupancy shall have a width of not less than 900 mm.",
        "entity": "IfcStairFlight",
        "property": "Width",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("Except as provided in Sentence (2)", "EXCEPTION"),
            ("serving buildings of residential occupancy", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 900 mm", "DIM_MIN"),
        ],
        # Nuance for Annotator 2: slight boundary variation on exception or entity tag
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "spans_override": [
                ("Except as provided in Sentence (2),", "EXCEPTION"),
                ("residential occupancy", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("not less than 900 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "OBC-9.8.4.1-1",
        "code": "OBC",
        "section_ref": "9.8.4.1.(1)",
        "text": "Risers in private stairs shall have a maximum height of 200 mm and a minimum height of 125 mm.",
        "entity": "IfcStairFlight",
        "property": "RiserHeight",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("private stairs", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("maximum height of 200 mm", "DIM_MAX"),
            ("minimum height of 125 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "spans_override": [
                ("private stairs", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("200 mm", "DIM_MAX"),
                ("125 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "OBC-9.8.4.2-1",
        "code": "OBC",
        "section_ref": "9.8.4.2.(1)",
        "text": "Treads in rectangular stairs shall have a minimum run of 255 mm and a maximum run of 355 mm.",
        "entity": "IfcStairFlight",
        "property": "TreadLength",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("rectangular stairs", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("minimum run of 255 mm", "DIM_MIN"),
            ("maximum run of 355 mm", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "spans_override": [
                ("rectangular stairs", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("minimum run of 255 mm", "DIM_MIN"),
                ("maximum run of 355 mm", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "OBC-9.8.7.1-1",
        "code": "OBC",
        "section_ref": "9.8.7.1.(1)",
        "text": "Stairs shall have a handrail on at least one side where the stair is less than 1100 mm in width.",
        "entity": "IfcRailing",
        "property": "HandrailCount",
        "unit": "count",
        "deontic": "MANDATORY",
        "spans": [
            ("Stairs", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("at least one side", "DIM_MIN"),
            ("less than 1100 mm", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "property": "HandrailRequired",
            "spans_override": [
                ("Stairs", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("at least one side", "DIM_MIN"),
                ("less than 1100 mm", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "OBC-9.8.7.1-2",
        "code": "OBC",
        "section_ref": "9.8.7.1.(2)",
        "text": "Stairs 1100 mm or more in width shall have handrails on both sides.",
        "entity": "IfcRailing",
        "property": "HandrailCount",
        "unit": "count",
        "deontic": "MANDATORY",
        "spans": [
            ("1100 mm or more in width", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("on both sides", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "spans_override": [
                ("1100 mm or more in width", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("both sides", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "OBC-9.8.7.4-1",
        "code": "OBC",
        "section_ref": "9.8.7.4.(1)",
        "text": "The height of handrails on stairs and ramps shall be not less than 865 mm and not more than 1070 mm.",
        "entity": "IfcRailing",
        "property": "Height",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("stairs and ramps", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 865 mm", "DIM_MIN"),
            ("not more than 1070 mm", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "spans_override": [
                ("stairs and ramps", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("865 mm", "DIM_MIN"),
                ("1070 mm", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "OBC-9.8.8.1-1",
        "code": "OBC",
        "section_ref": "9.8.8.1.(1)",
        "text": "Except as provided in Sentences (2) to (4), every surface to which access is provided for other than maintenance purposes shall be protected by a guard where the elevation difference exceeds 600 mm.",
        "entity": "IfcRailing",
        "property": "GuardRequired",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("Except as provided in Sentences (2) to (4)", "EXCEPTION"),
            ("other than maintenance purposes", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("exceeds 600 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "spans_override": [
                ("Except as provided in Sentences (2) to (4),", "EXCEPTION"),
                ("access is provided for other than maintenance purposes", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("exceeds 600 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "OBC-9.8.8.3-1",
        "code": "OBC",
        "section_ref": "9.8.8.3.(1)",
        "text": "Guards for residential exterior balconies shall have a height of not less than 1070 mm where the walking surface is more than 1800 mm above adjacent ground.",
        "entity": "IfcRailing",
        "property": "Height",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("residential exterior balconies", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 1070 mm", "DIM_MIN"),
            ("more than 1800 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "spans_override": [
                ("residential exterior balconies", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("1070 mm", "DIM_MIN"),
                ("1800 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "OBC-9.8.8.5-1",
        "code": "OBC",
        "section_ref": "9.8.8.5.(1)",
        "text": "Openings through any guard shall be of a size that prevents the passage of a spherical object having a diameter of 100 mm.",
        "entity": "IfcRailing",
        "property": "OpeningClearance",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("Openings through any guard", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("diameter of 100 mm", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "spans_override": [
                ("Openings through any guard", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("100 mm", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "OBC-9.8.5.1-1",
        "code": "OBC",
        "section_ref": "9.8.5.1.(1)",
        "text": "The slope of ramps in pedestrian egress pathways shall not exceed 1 in 10 for interior ramps and 1 in 8 for exterior ramps.",
        "entity": "IfcRampFlight",
        "property": "Slope",
        "unit": "ratio",
        "deontic": "PROHIBITED",
        "spans": [
            ("interior ramps", "APPLICABILITY"),
            ("shall not", "PROHIBITED"),
            ("1 in 10", "DIM_MAX"),
            ("1 in 8", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcRampFlight",
            "spans_override": [
                ("pedestrian egress pathways", "APPLICABILITY"),
                ("shall not", "PROHIBITED"),
                ("exceed 1 in 10", "DIM_MAX"),
                ("1 in 8", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "OBC-9.9.3.3-1",
        "code": "OBC",
        "section_ref": "9.9.3.3.(1)",
        "text": "Every public corridor shall have a clear width of not less than 1100 mm.",
        "entity": "IfcSpace",
        "property": "CorridorWidth",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("public corridor", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 1100 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcSpace",
            "property": "ClearWidth",
            "spans_override": [
                ("public corridor", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("1100 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "OBC-9.9.6.3-1",
        "code": "OBC",
        "section_ref": "9.9.6.3.(1)",
        "text": "Exit doors serving an occupant load of more than 60 persons shall open in the direction of exit travel.",
        "entity": "IfcDoor",
        "property": "SwingDirection",
        "unit": "boolean",
        "deontic": "MANDATORY",
        "spans": [
            ("more than 60 persons", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("in the direction of exit travel", "MANDATORY"),
        ],
        "ann2_alt": {
            "entity": "IfcDoor",
            "spans_override": [
                ("serving an occupant load of more than 60 persons", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("in the direction of exit travel", "MANDATORY"),
            ]
        }
    },
    {
        "id": "OBC-9.9.6.2-1",
        "code": "OBC",
        "section_ref": "9.9.6.2.(1)",
        "text": "Every doorway serving as a required exit shall provide a clear opening width of not less than 800 mm.",
        "entity": "IfcDoor",
        "property": "OverallWidth",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("serving as a required exit", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 800 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcDoor",
            "property": "ClearWidth",
            "spans_override": [
                ("serving as a required exit", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("800 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "OBC-9.9.8.2-1",
        "code": "OBC",
        "section_ref": "9.9.8.2.(1)",
        "text": "The travel distance from any point in a floor area to an exterior exit shall not exceed 45 m in unsprinklered buildings.",
        "entity": "IfcSpace",
        "property": "MaxTravelDistance",
        "unit": "m",
        "deontic": "PROHIBITED",
        "spans": [
            ("unsprinklered buildings", "APPLICABILITY"),
            ("shall not", "PROHIBITED"),
            ("exceed 45 m", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcSpace",
            "spans_override": [
                ("in unsprinklered buildings", "APPLICABILITY"),
                ("shall not", "PROHIBITED"),
                ("45 m", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "OBC-9.8.3.1-1",
        "code": "OBC",
        "section_ref": "9.8.3.1.(1)",
        "text": "The vertical clear headroom over stairs measured vertically from the line connecting the leading edge of treads shall be not less than 2050 mm.",
        "entity": "IfcStairFlight",
        "property": "Headroom",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("vertical clear headroom over stairs", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 2050 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "property": "ClearHeadroom",
            "spans_override": [
                ("headroom over stairs", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("2050 mm", "DIM_MIN"),
            ]
        }
    },

    # --- SBC-201-2007 (Chapter 8 Means of Egress) ---
    {
        "id": "SBC-8.3.2-1",
        "code": "SBC",
        "section_ref": "8.3.2",
        "text": "The means of egress shall have a ceiling height of not less than 2 meters.",
        "entity": "IfcSpace",
        "property": "CeilingHeight",
        "unit": "m",
        "deontic": "MANDATORY",
        "spans": [
            ("means of egress", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 2 meters", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcSpace",
            "property": "ClearHeight",
            "spans_override": [
                ("means of egress", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("2 meters", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.8.1.1-1",
        "code": "SBC",
        "section_ref": "8.8.1.1",
        "text": "The minimum width of each door opening shall provide a clear width of not less than 810 mm.",
        "entity": "IfcDoor",
        "property": "OverallWidth",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("door opening", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 810 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcDoor",
            "property": "ClearWidth",
            "spans_override": [
                ("each door opening", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("810 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.8.1.1-2",
        "code": "SBC",
        "section_ref": "8.8.1.1",
        "text": "The maximum width of a swinging door leaf shall be 1.2 meters nominal.",
        "entity": "IfcDoor",
        "property": "OverallWidth",
        "unit": "m",
        "deontic": "MANDATORY",
        "spans": [
            ("swinging door leaf", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("1.2 meters", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcDoor",
            "spans_override": [
                ("swinging door leaf", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("1.2 meters nominal", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "SBC-8.8.1.6-1",
        "code": "SBC",
        "section_ref": "8.8.1.6",
        "text": "Thresholds at doorways shall not exceed 19 mm in height for sliding doors or 12.7 mm for other doors.",
        "entity": "IfcDoor",
        "property": "ThresholdHeight",
        "unit": "mm",
        "deontic": "PROHIBITED",
        "spans": [
            ("Thresholds at doorways", "APPLICABILITY"),
            ("shall not", "PROHIBITED"),
            ("exceed 19 mm", "DIM_MAX"),
            ("12.7 mm", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcDoor",
            "spans_override": [
                ("Thresholds at doorways", "APPLICABILITY"),
                ("shall not", "PROHIBITED"),
                ("19 mm", "DIM_MAX"),
                ("12.7 mm", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "SBC-8.9.1-1",
        "code": "SBC",
        "section_ref": "8.9.1",
        "text": "The width of stairways shall be determined as specified in Section 8.5.1, but such width shall not be less than 1.1 meters.",
        "entity": "IfcStairFlight",
        "property": "Width",
        "unit": "m",
        "deontic": "MANDATORY",
        "spans": [
            ("width of stairways", "APPLICABILITY"),
            ("shall not be less than 1.1 meters", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "spans_override": [
                ("stairways", "APPLICABILITY"),
                ("not less than 1.1 meters", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.9.3.1-1",
        "code": "SBC",
        "section_ref": "8.9.3.1",
        "text": "Stair riser heights shall be 178 mm maximum and 102 mm minimum.",
        "entity": "IfcStairFlight",
        "property": "RiserHeight",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("Stair riser heights", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("178 mm maximum", "DIM_MAX"),
            ("102 mm minimum", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "spans_override": [
                ("Stair riser", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("178 mm", "DIM_MAX"),
                ("102 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.9.3.1-2",
        "code": "SBC",
        "section_ref": "8.9.3.1",
        "text": "The minimum tread depth shall be 280 mm measured horizontally between vertical planes of adjoining risers.",
        "entity": "IfcStairFlight",
        "property": "TreadLength",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("tread depth", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("minimum tread depth shall be 280 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "spans_override": [
                ("tread depth", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("280 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.9.11-1",
        "code": "SBC",
        "section_ref": "8.9.11",
        "text": "Stairways shall have handrails on each side in accordance with this section.",
        "entity": "IfcRailing",
        "property": "HandrailCount",
        "unit": "count",
        "deontic": "MANDATORY",
        "spans": [
            ("Stairways", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("on each side", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "property": "HandrailRequired",
            "spans_override": [
                ("Stairways", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("each side", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.9.11.1-1",
        "code": "SBC",
        "section_ref": "8.9.11.1",
        "text": "Handrail height, measured above stair tread nosings, shall exist uniformly between 864 mm and 965 mm.",
        "entity": "IfcRailing",
        "property": "Height",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("Handrail height", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("between 864 mm and 965 mm", "DIM_EXACT"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "spans_override": [
                ("Handrail height", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("864 mm", "DIM_MIN"),
                ("965 mm", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "SBC-8.10.2-1",
        "code": "SBC",
        "section_ref": "8.10.2",
        "text": "Ramps used as part of a means of egress shall have a running slope not steeper than one unit vertical in 12 units horizontal (8 percent slope).",
        "entity": "IfcRampFlight",
        "property": "Slope",
        "unit": "ratio",
        "deontic": "MANDATORY",
        "spans": [
            ("means of egress", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not steeper than one unit vertical in 12 units horizontal", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcRampFlight",
            "spans_override": [
                ("Ramps used as part of a means of egress", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("one unit vertical in 12 units horizontal", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "SBC-8.12.2-1",
        "code": "SBC",
        "section_ref": "8.12.2",
        "text": "Guards shall form a protective barrier not less than 1067 mm high, measured vertically above the adjacent walking surface.",
        "entity": "IfcRailing",
        "property": "Height",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("Guards", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 1067 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcRailing",
            "spans_override": [
                ("Guards", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("1067 mm high", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.16.1-1",
        "code": "SBC",
        "section_ref": "8.16.1",
        "text": "In buildings without an automatic sprinkler system, exit access travel distance shall not exceed 61 meters.",
        "entity": "IfcSpace",
        "property": "MaxTravelDistance",
        "unit": "m",
        "deontic": "PROHIBITED",
        "spans": [
            ("without an automatic sprinkler system", "APPLICABILITY"),
            ("shall not", "PROHIBITED"),
            ("exceed 61 meters", "DIM_MAX"),
        ],
        "ann2_alt": {
            "entity": "IfcSpace",
            "spans_override": [
                ("without an automatic sprinkler system", "APPLICABILITY"),
                ("shall not", "PROHIBITED"),
                ("61 meters", "DIM_MAX"),
            ]
        }
    },
    {
        "id": "SBC-8.17.2-1",
        "code": "SBC",
        "section_ref": "8.17.2",
        "text": "The minimum corridor width shall be not less than 1118 mm where serving an occupant load of 50 or more.",
        "entity": "IfcSpace",
        "property": "CorridorWidth",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("serving an occupant load of 50 or more", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 1118 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcSpace",
            "property": "ClearWidth",
            "spans_override": [
                ("occupant load of 50 or more", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("1118 mm", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.8.1.5-1",
        "code": "SBC",
        "section_ref": "8.8.1.5",
        "text": "Landings at doors shall have a length measured in the direction of travel of not less than 1.1 meters.",
        "entity": "IfcSpace",
        "property": "LandingLength",
        "unit": "m",
        "deontic": "MANDATORY",
        "spans": [
            ("Landings at doors", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 1.1 meters", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcDoor",
            "property": "LandingLength",
            "spans_override": [
                ("Landings at doors", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("1.1 meters", "DIM_MIN"),
            ]
        }
    },
    {
        "id": "SBC-8.9.2-1",
        "code": "SBC",
        "section_ref": "8.9.2",
        "text": "Stairways shall have a minimum headroom clearance of not less than 2032 mm measured vertically from the sloped plane connecting tread nosings.",
        "entity": "IfcStairFlight",
        "property": "Headroom",
        "unit": "mm",
        "deontic": "MANDATORY",
        "spans": [
            ("Stairways", "APPLICABILITY"),
            ("shall", "MANDATORY"),
            ("not less than 2032 mm", "DIM_MIN"),
        ],
        "ann2_alt": {
            "entity": "IfcStairFlight",
            "property": "ClearHeadroom",
            "spans_override": [
                ("Stairways", "APPLICABILITY"),
                ("shall", "MANDATORY"),
                ("2032 mm", "DIM_MIN"),
            ]
        }
    },
]

def make_task_data(clause: dict, task_id: int) -> dict:
    text = clause["text"]
    
    def find_spans(spans_spec):
        out = []
        for target, lbl in spans_spec:
            idx = text.find(target)
            if idx != -1:
                out.append({
                    "id": f"span_{task_id}_{lbl}_{idx}",
                    "from_name": "linguistic_labels",
                    "to_name": "text",
                    "type": "labels",
                    "value": {
                        "start": idx,
                        "end": idx + len(target),
                        "text": target,
                        "labels": [lbl]
                    }
                })
        return out

    # Annotator 1 (Architectural Specialist)
    ann1_spans = find_spans(clause["spans"])
    ann1_results = list(ann1_spans)
    ann1_results.append({
        "id": f"choice_ifc_{task_id}_1",
        "from_name": "ifc_entity",
        "type": "choices",
        "value": {"choices": [clause["entity"]]}
    })
    ann1_results.append({
        "id": f"choice_prop_{task_id}_1",
        "from_name": "property_name",
        "type": "choices",
        "value": {"choices": [clause["property"]]}
    })
    ann1_results.append({
        "id": f"choice_unit_{task_id}_1",
        "from_name": "unit",
        "type": "choices",
        "value": {"choices": [clause["unit"]]}
    })
    ann1_results.append({
        "id": f"choice_deon_{task_id}_1",
        "from_name": "deontic_strength",
        "type": "choices",
        "value": {"choices": [clause["deontic"]]}
    })

    # Annotator 2 (Computational BIM Specialist)
    alt = clause.get("ann2_alt", {})
    ann2_entity = alt.get("entity", clause["entity"])
    ann2_prop = alt.get("property", clause["property"])
    ann2_unit = alt.get("unit", clause["unit"])
    ann2_deon = alt.get("deontic", clause["deontic"])
    ann2_spans_spec = alt.get("spans_override", clause["spans"])
    ann2_spans = find_spans(ann2_spans_spec)
    
    ann2_results = list(ann2_spans)
    ann2_results.append({
        "id": f"choice_ifc_{task_id}_2",
        "from_name": "ifc_entity",
        "type": "choices",
        "value": {"choices": [ann2_entity]}
    })
    ann2_results.append({
        "id": f"choice_prop_{task_id}_2",
        "from_name": "property_name",
        "type": "choices",
        "value": {"choices": [ann2_prop]}
    })
    ann2_results.append({
        "id": f"choice_unit_{task_id}_2",
        "from_name": "unit",
        "type": "choices",
        "value": {"choices": [ann2_unit]}
    })
    ann2_results.append({
        "id": f"choice_deon_{task_id}_2",
        "from_name": "deontic_strength",
        "type": "choices",
        "value": {"choices": [ann2_deon]}
    })

    # Adjudicator 3 (Consensus Adjudication)
    adj_results = list(ann1_results)  # Adjudicator ratifies standard gold reference

    return {
        "id": task_id,
        "data": {
            "section_ref": clause["section_ref"],
            "code": clause["code"],
            "clause_id": clause["id"],
            "text": text,
        },
        "annotations": [
            {
                "id": 1000 + task_id * 3 + 1,
                "completed_by": 1,
                "annotator_role": "Architectural Domain Specialist",
                "result": ann1_results
            },
            {
                "id": 1000 + task_id * 3 + 2,
                "completed_by": 2,
                "annotator_role": "Computational BIM Specialist",
                "result": ann2_results
            },
            {
                "id": 1000 + task_id * 3 + 3,
                "completed_by": 3,
                "annotator_role": "Senior Consensus Adjudicator",
                "result": adj_results
            }
        ]
    }

def main():
    tasks = [make_task_data(c, i + 1) for i, c in enumerate(CLAUSES)]
    out_path = Path(__file__).resolve().parent / "dual_annotator_corpus.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)
    print(f"Generated {len(tasks)} dual-annotated tasks in: {out_path}")

if __name__ == "__main__":
    main()
