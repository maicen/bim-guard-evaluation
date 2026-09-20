"""
kg/bsdd_loader.py
------------------------------------------------
Loads the bSDD ontology reference database (classes/properties/class_properties)
by reusing bim-guard's own storage module (app.services.bsdd_duckdb_store) as
the single source of truth for the DuckDB schema, rather than re-implementing
it here.

That module is loaded directly from its file path (importlib), not via a
normal `from app.services... import ...` package import: `app/services/__init__.py`
eagerly imports the full service layer (FastAPI, Supabase, etc.), none of
which this evaluation repo's environment has installed, and none of which
bsdd_duckdb_store.py itself needs (it only touches `duckdb` + stdlib).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Set, Tuple

_EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from eval_config import setup_bimguard_path  # noqa: E402


def _load_bsdd_duckdb_store() -> ModuleType:
    """Imports bim-guard's app/services/bsdd_duckdb_store.py as a standalone
    module, bypassing app/services/__init__.py's heavy import chain."""
    bimguard_root = setup_bimguard_path()
    module_path = bimguard_root / "app" / "services" / "bsdd_duckdb_store.py"
    if not module_path.exists():
        raise FileNotFoundError(f"bim-guard's bsdd_duckdb_store.py not found at {module_path}")

    module_name = "_bimguard_bsdd_duckdb_store"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

#: Substrings matched against each class's full dictionary_uri (e.g.
#: "https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3"), not
#: exact values — the reference DB carries a couple of differently-spelled
#: IFC 4.3 dictionary URIs (observed via exploration of the live data).
DEFAULT_DICTIONARIES = {"ifc-4.3", "ifc/4.3"}

ClassRow = Dict[str, Any]
PropertyRow = Dict[str, Any]
EdgeRow = Dict[str, Any]


def default_bsdd_db_path() -> Path:
    bimguard_root = setup_bimguard_path()
    return bimguard_root / "data" / "reference" / "bsdd" / "bsdd_ontology.duckdb"


def load_ontology(
    db_path: Optional[Path] = None,
    dictionaries: Optional[Set[str]] = None,
) -> Tuple[Dict[str, ClassRow], Dict[str, PropertyRow], List[EdgeRow]]:
    """Reads (classes, properties, class_properties) from the bSDD DuckDB file.

    classes/properties are keyed by uri; edges is a flat list of
    {class_uri, property_uri, property_set, data_type, units, allowed_values}.

    When `dictionaries` is given, only classes whose dictionary_uri contains
    one of those substrings are kept (properties/edges are filtered down to
    what those classes reference), keeping the graph focused on the relevant
    vocabulary.
    """
    read_ontology_tables = _load_bsdd_duckdb_store().read_ontology_tables

    if db_path is None:
        db_path = default_bsdd_db_path()

    classes, properties, edges = read_ontology_tables(db_path)

    if not dictionaries:
        return classes, properties, edges

    classes = {
        uri: row
        for uri, row in classes.items()
        if any(d in (row.get("dictionary_uri") or "") for d in dictionaries)
    }
    kept_class_uris = set(classes)
    edges = [e for e in edges if e["class_uri"] in kept_class_uris]
    kept_property_uris = {e["property_uri"] for e in edges}
    properties = {uri: row for uri, row in properties.items() if uri in kept_property_uris}
    return classes, properties, edges
