"""
kg/dclx_loader.py
------------------------------------------------
Extracts the DocLang XML document part out of a .dclx OPC archive
(a zip package, analogous to .docx/.pptx, produced by scripts/pdf_to_dclx.py).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import defusedxml.ElementTree as safe_ET

_DEFAULT_ENTRY = "document.xml"


def load_dclx_document_xml(path: Path) -> str:
    """Unzips a .dclx archive and returns the DocLang XML content of its main document part."""
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        entry = _DEFAULT_ENTRY if _DEFAULT_ENTRY in names else _find_document_part(zf, names)
        with zf.open(entry) as f:
            return f.read().decode("utf-8")


def _find_document_part(zf: zipfile.ZipFile, names: set[str]) -> str:
    """Falls back to reading _rels/.rels for the document part's Target, else the first
    top-level *.xml entry that isn't packaging metadata."""
    if "_rels/.rels" in names:
        with zf.open("_rels/.rels") as f:
            root = safe_ET.fromstring(f.read())
        for rel in root:
            rel_type = rel.attrib.get("Type", "")
            target = rel.attrib.get("Target", "").lstrip("/")
            if "document" in rel_type.lower() and target in names:
                return target

    candidates = sorted(
        n for n in names
        if n.endswith(".xml") and not n.startswith("_rels") and n != "[Content_Types].xml"
    )
    if not candidates:
        raise FileNotFoundError(f"No DocLang document part found in archive entries: {sorted(names)}")
    return candidates[0]
