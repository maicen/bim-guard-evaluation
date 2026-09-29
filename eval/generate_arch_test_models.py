"""
generate_arch_test_models.py
------------------------------------------------
Procedural architectural test case generator for BIM-Guard compliance engines
(ARCH-EGRESS-001, ARCH-SPATIAL-001).

Generates grounded test scenarios with known mathematical ground truth:
- Compliant scenarios (expected: PASS)
- Non-compliant boundary and failure scenarios (expected: FAIL)
- Unassessed/missing metadata edge cases (expected: NOT_ASSESSED / FAIL)

Can also assemble minimal schema-valid IFC4 synthetic models using ifcopenshell.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any


def make_guid() -> str:
    """Generate a clean synthetic element GUID."""
    return str(uuid.uuid4())[:8]


# ══════════════════════════════════════════════════════════════════════════
# Ground Truth Test Cases for Architecture Engines
# ══════════════════════════════════════════════════════════════════════════

def get_architectural_test_cases() -> list[dict[str, Any]]:
    """Return an extensive collection of architectural test scenarios paired with
    their ground-truth compliance expectation.

    Conventions:
      expected_violation: True if the element represents a code defect (Positive),
                          False if the element is compliant (Negative).
      expected_status: "PASS" | "FAIL" | "NOT_ASSESSED"
    """
    cases: list[dict[str, Any]] = [
        # ── 1. ARCH-EGRESS-001: Travel Distance (Threshold: 25.0 m) ──────
        {
            "id": "egress_travel_short",
            "engine": "ARCH-EGRESS-001",
            "check_type": "travel_distance",
            "element": {
                "guid": "SP-001",
                "space_name": "Office 101",
                "storey": "Storey 1",
                "travel_distance_m": 14.2,
                "nearest_exit": "Exit Door D-101",
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "Short travel distance well within 25.0 m limit",
        },
        {
            "id": "egress_travel_boundary_pass",
            "engine": "ARCH-EGRESS-001",
            "check_type": "travel_distance",
            "element": {
                "guid": "SP-002",
                "space_name": "Conference Room",
                "storey": "Storey 1",
                "travel_distance_m": 24.8,
                "nearest_exit": "Exit Stair S-1",
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "Boundary travel distance below 25.0 m",
        },
        {
            "id": "egress_travel_boundary_fail",
            "engine": "ARCH-EGRESS-001",
            "check_type": "travel_distance",
            "element": {
                "guid": "SP-003",
                "space_name": "Server Lab",
                "storey": "Storey 2",
                "travel_distance_m": 25.4,
                "nearest_exit": "Exit Stair S-2",
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Boundary travel distance exceeding 25.0 m",
        },
        {
            "id": "egress_travel_excessive",
            "engine": "ARCH-EGRESS-001",
            "check_type": "travel_distance",
            "element": {
                "guid": "SP-004",
                "space_name": "Warehouse Storage",
                "storey": "Storey 1",
                "travel_distance_m": 38.6,
                "nearest_exit": "Main Entry",
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Excessive travel distance severely exceeding 25.0 m limit",
        },
        {
            "id": "egress_travel_isolated_room",
            "engine": "ARCH-EGRESS-001",
            "check_type": "travel_distance",
            "element": {
                "guid": "SP-005",
                "space_name": "Dead-end Vault",
                "storey": "Basement",
                "travel_distance_m": None,
                "nearest_exit": None,
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Isolated space with no accessible path to any exit",
        },

        # ── 2. ARCH-EGRESS-001: Storey Exit Counts (Threshold: >= 2) ─────
        {
            "id": "egress_exits_adequate_two",
            "engine": "ARCH-EGRESS-001",
            "check_type": "exit_count",
            "element": {
                "guid": "ST-001",
                "storey": "Ground Floor",
                "exit_count": 2,
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "Storey with exactly 2 required exits",
        },
        {
            "id": "egress_exits_adequate_three",
            "engine": "ARCH-EGRESS-001",
            "check_type": "exit_count",
            "element": {
                "guid": "ST-002",
                "storey": "Second Floor",
                "exit_count": 3,
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "Storey with 3 exits exceeding minimum",
        },
        {
            "id": "egress_exits_insufficient_single",
            "engine": "ARCH-EGRESS-001",
            "check_type": "exit_count",
            "element": {
                "guid": "ST-003",
                "storey": "Third Floor",
                "exit_count": 1,
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Storey with only 1 exit violating 2-exit requirement",
        },
        {
            "id": "egress_exits_zero",
            "engine": "ARCH-EGRESS-001",
            "check_type": "exit_count",
            "element": {
                "guid": "ST-004",
                "storey": "Mezzanine",
                "exit_count": 0,
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Storey with 0 declared exits",
        },

        # ── 3. ARCH-EGRESS-001: Egress Windows (Area >= 0.35, Dim >= 380, Sill <= 1000) ──
        {
            "id": "egress_window_fully_compliant",
            "engine": "ARCH-EGRESS-001",
            "check_type": "egress_window",
            "element": {
                "guid": "WND-001",
                "space_name": "Master Bedroom",
                "storey": "Level 2",
                "window_count": 1,
                "best_window": {
                    "clear_area_m2": 0.45,
                    "clear_width_mm": 550.0,
                    "clear_height_mm": 820.0,
                    "sill_height_mm": 850.0,
                },
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "Fully compliant egress window meeting all 4 dimension criteria",
        },
        {
            "id": "egress_window_area_too_small",
            "engine": "ARCH-EGRESS-001",
            "check_type": "egress_window",
            "element": {
                "guid": "WND-002",
                "space_name": "Guest Bedroom",
                "storey": "Level 2",
                "window_count": 1,
                "best_window": {
                    "clear_area_m2": 0.28,
                    "clear_width_mm": 400.0,
                    "clear_height_mm": 700.0,
                    "sill_height_mm": 900.0,
                },
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Egress window area (0.28 m2) fails 0.35 m2 minimum",
        },
        {
            "id": "egress_window_width_too_narrow",
            "engine": "ARCH-EGRESS-001",
            "check_type": "egress_window",
            "element": {
                "guid": "WND-003",
                "space_name": "Bedroom 3",
                "storey": "Level 2",
                "window_count": 1,
                "best_window": {
                    "clear_area_m2": 0.36,
                    "clear_width_mm": 350.0,
                    "clear_height_mm": 1030.0,
                    "sill_height_mm": 850.0,
                },
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Egress window width (350 mm) fails 380 mm minimum",
        },
        {
            "id": "egress_window_sill_too_high",
            "engine": "ARCH-EGRESS-001",
            "check_type": "egress_window",
            "element": {
                "guid": "WND-004",
                "space_name": "Attic Bedroom",
                "storey": "Attic",
                "window_count": 1,
                "best_window": {
                    "clear_area_m2": 0.48,
                    "clear_width_mm": 600.0,
                    "clear_height_mm": 800.0,
                    "sill_height_mm": 1200.0,
                },
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Egress window sill height (1200 mm) exceeds 1000 mm maximum",
        },
        {
            "id": "egress_window_missing_in_bedroom",
            "engine": "ARCH-EGRESS-001",
            "check_type": "egress_window",
            "element": {
                "guid": "WND-005",
                "space_name": "Basement Bedroom",
                "storey": "Basement",
                "window_count": 0,
                "best_window": None,
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Sleeping room with zero windows",
        },

        # ── 4. ARCH-SPATIAL-001: Daylighting Glazing Ratio (Threshold: >= 0.08) ──
        {
            "id": "spatial_daylight_generous",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "daylight_ratio",
            "element": {
                "space_guid": "DAY-001",
                "space_name": "Living Room",
                "daylight_ratio": 0.14,
                "total_window_area_m2": 3.5,
                "floor_area_m2": 25.0,
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "Daylight ratio (14%) well exceeds 8% minimum",
        },
        {
            "id": "spatial_daylight_boundary_pass",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "daylight_ratio",
            "element": {
                "space_guid": "DAY-002",
                "space_name": "Study Room",
                "daylight_ratio": 0.082,
                "total_window_area_m2": 1.23,
                "floor_area_m2": 15.0,
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "Daylight ratio (8.2%) passes boundary",
        },
        {
            "id": "spatial_daylight_deficient",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "daylight_ratio",
            "element": {
                "space_guid": "DAY-003",
                "space_name": "Dining Alcove",
                "daylight_ratio": 0.045,
                "total_window_area_m2": 0.9,
                "floor_area_m2": 20.0,
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Daylight ratio (4.5%) fails 8% minimum",
        },
        {
            "id": "spatial_daylight_windowless",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "daylight_ratio",
            "element": {
                "space_guid": "DAY-004",
                "space_name": "Interior Den",
                "daylight_ratio": 0.0,
                "total_window_area_m2": 0.0,
                "floor_area_m2": 16.0,
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Interior habitable space with zero daylight",
        },

        # ── 5. ARCH-SPATIAL-001: Party Wall Fire Separation (Threshold: >= 45 min) ──
        {
            "id": "spatial_fire_compliant_one_hour",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "fire_separation",
            "element": {
                "wall_guid": "WALL-001",
                "wall_name": "Demising Party Wall Unit A/B",
                "fire_rating_min": 60.0,
                "adjacent_spaces": ["Unit A Living", "Unit B Living"],
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "1-hour fire separation rating exceeding 45 min requirement",
        },
        {
            "id": "spatial_fire_boundary_pass",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "fire_separation",
            "element": {
                "wall_guid": "WALL-002",
                "wall_name": "Corridor Separation Wall",
                "fire_rating_min": 45.0,
                "adjacent_spaces": ["Corridor", "Unit 102"],
            },
            "expected_status": "PASS",
            "expected_violation": False,
            "description": "45-min fire separation rating exactly matching requirement",
        },
        {
            "id": "spatial_fire_substandard",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "fire_separation",
            "element": {
                "wall_guid": "WALL-003",
                "wall_name": "Tenant Partition Wall",
                "fire_rating_min": 30.0,
                "adjacent_spaces": ["Unit C", "Unit D"],
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "30-min fire rating failing 45 min requirement",
        },
        {
            "id": "spatial_fire_unrated_missing",
            "engine": "ARCH-SPATIAL-001",
            "check_type": "fire_separation",
            "element": {
                "wall_guid": "WALL-004",
                "wall_name": "Party Wall Without Rating",
                "fire_rating_min": None,
                "missing_rating": True,
                "adjacent_spaces": ["Unit E", "Unit F"],
            },
            "expected_status": "FAIL",
            "expected_violation": True,
            "description": "Party wall with undeclared fire resistance rating",
        },
    ]
    return cases


# ══════════════════════════════════════════════════════════════════════════
# Procedural Whole-Building IFC4 Generation
# ══════════════════════════════════════════════════════════════════════════

def generate_procedural_ifc_building(output_path: str | Path | None = None) -> Path:
    """
    Generates a schema-valid IFC4 synthetic building model containing:
    - Spatial Hierarchy: IfcProject -> IfcSite -> IfcBuilding -> IfcBuildingStorey
    - 4 Connected Spaces (Office 101, Corridor 102, Exit Stair S-1, Public Way 104)
    - Building Elements: Walls (with Pset_WallCommon.FireRating), Egress Doors, Windows, Stairs
    - Explicit IfcRelSpaceBoundary relationships linking spaces to boundaries
    - Relational Aggregates and Spatial Containment
    """
    import ifcopenshell
    import ifcopenshell.guid

    f = ifcopenshell.file(schema="IFC4")

    # 1. Project & Spatial Structure
    project = f.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="BIM-Guard Research Benchmark Building")
    site = f.create_entity("IfcSite", GlobalId=ifcopenshell.guid.new(), Name="Benchmark Site")
    building = f.create_entity("IfcBuilding", GlobalId=ifcopenshell.guid.new(), Name="Academic Validation Pavilion")
    storey = f.create_entity("IfcBuildingStorey", GlobalId=ifcopenshell.guid.new(), Name="Level 01", Elevation=0.0)

    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=project, RelatedObjects=[site])
    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=site, RelatedObjects=[building])
    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=building, RelatedObjects=[storey])

    # 2. Spaces
    sp_office = f.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Office 101", LongName="Habitable Office Suite")
    sp_corridor = f.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Corridor 102", LongName="Primary Egress Corridor")
    sp_stair = f.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Exit Stair S-1", LongName="Protected Stair Enclosure")
    sp_public = f.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Exterior Public Way", LongName="Public Way Discharge")

    f.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=storey, RelatedObjects=[sp_office, sp_corridor, sp_stair, sp_public])

    # 3. Elements
    wall_party = f.create_entity("IfcWallStandardCase", GlobalId=ifcopenshell.guid.new(), Name="Wall-Demising-60M")
    wall_corridor = f.create_entity("IfcWallStandardCase", GlobalId=ifcopenshell.guid.new(), Name="Wall-Corridor-45M")
    
    door_office = f.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(), Name="Door-D101", OverallWidth=900.0, OverallHeight=2100.0)
    door_stair = f.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(), Name="Door-D102-Stair", OverallWidth=1000.0, OverallHeight=2100.0)
    door_exit = f.create_entity("IfcDoor", GlobalId=ifcopenshell.guid.new(), Name="Door-D103-Discharge", OverallWidth=1100.0, OverallHeight=2150.0)

    window_office = f.create_entity("IfcWindow", GlobalId=ifcopenshell.guid.new(), Name="Window-W101", OverallWidth=1500.0, OverallHeight=1500.0)
    stair_flight = f.create_entity("IfcStairFlight", GlobalId=ifcopenshell.guid.new(), Name="Stair-SF101", NumberOfRisers=18, RiserHeight=175.0, TreadLength=280.0)

    all_elements = [wall_party, wall_corridor, door_office, door_stair, door_exit, window_office, stair_flight]
    f.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(), RelatingStructure=storey, RelatedElements=all_elements)

    # 4. Property Sets (Fire Resistance Rating)
    pset_wall1 = f.create_entity(
        "IfcPropertySingleValue",
        Name="FireRating",
        NominalValue=f.create_entity("IfcLabel", "60"),
    )
    f.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[wall_party],
        RelatingPropertyDefinition=f.create_entity(
            "IfcPropertySet",
            GlobalId=ifcopenshell.guid.new(),
            Name="Pset_WallCommon",
            HasProperties=[pset_wall1],
        ),
    )

    pset_wall2 = f.create_entity(
        "IfcPropertySingleValue",
        Name="FireRating",
        NominalValue=f.create_entity("IfcLabel", "45"),
    )
    f.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[wall_corridor],
        RelatingPropertyDefinition=f.create_entity(
            "IfcPropertySet",
            GlobalId=ifcopenshell.guid.new(),
            Name="Pset_WallCommon",
            HasProperties=[pset_wall2],
        ),
    )

    # 5. IfcRelSpaceBoundary topological associations
    # Office 101 boundaries
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_office, RelatedBuildingElement=wall_party, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL")
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_office, RelatedBuildingElement=door_office, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL")
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_office, RelatedBuildingElement=window_office, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="EXTERNAL")

    # Corridor 102 boundaries
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_corridor, RelatedBuildingElement=door_office, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL")
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_corridor, RelatedBuildingElement=wall_corridor, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL")
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_corridor, RelatedBuildingElement=door_stair, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL")

    # Exit Stair S-1 boundaries
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_stair, RelatedBuildingElement=door_stair, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL")
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_stair, RelatedBuildingElement=stair_flight, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="INTERNAL")
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_stair, RelatedBuildingElement=door_exit, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="EXTERNAL")

    # Exterior discharge
    f.create_entity("IfcRelSpaceBoundary", GlobalId=ifcopenshell.guid.new(), RelatingSpace=sp_public, RelatedBuildingElement=door_exit, PhysicalOrVirtualBoundary="PHYSICAL", InternalOrExternalBoundary="EXTERNAL")

    if output_path is None:
        target = Path(__file__).resolve().parent / "fixtures" / "procedural_benchmark_building.ifc"
    else:
        target = Path(output_path)

    target.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(target))
    return target


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Generate procedural architectural test cases & IFC4 models")
    parser.add_argument("--export-ifc", type=str, help="Destination path for procedural IFC4 file")
    parser.add_argument("--json", action="store_true", help="Dump architectural test cases to JSON")
    args = parser.parse_args()

    if args.export_ifc:
        out = generate_procedural_ifc_building(args.export_ifc)
        print(f"Generated procedural IFC4 model at: {out}")
        return 0

    cases = get_architectural_test_cases()
    if args.json:
        import json
        print(json.dumps(cases, indent=2))
    else:
        print(f"Loaded {len(cases)} architectural benchmark test cases across ARCH-EGRESS-001 and ARCH-SPATIAL-001.")
        out_default = generate_procedural_ifc_building()
        print(f"Verified procedural IFC4 synthetic building: {out_default}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
