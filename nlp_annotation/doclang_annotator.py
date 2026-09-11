"""
nlp_annotation/doclang_annotator.py
---------------------------------------------
Native DocLang (v0.7 specification) annotation layer for BIM-Guard.

Parses DocLang XML / .dclg documents, runs the 5 linguistic NLP capabilities:
    1. Deontic operators (SHALL, MUST, MAY, SHOULD) + obligation strength
    2. Conditions (WHERE/WHEN/IF) & exceptions
    3. Cross-references (Articles, Sections, Tables, Figures)
    4. Clause dependencies (NOTWITHSTANDING, EXCEPT, SUBJECT TO)
    5. Dimensions (numeric values, units, constraints min/max/range)
    + IFC entity semantic mapping

Injects structured linguistic metadata into DocLang elements inside the
schema-compliant <custom> extension point (<custom><bg_nlp .../></custom>),
preserving element IDs (<bg_element_id>) and document hierarchy while maintaining
strict DocLang XSD schema compliance.
"""

from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import defusedxml.ElementTree as safe_ET
from defusedxml.common import DefusedXmlException
from doclang import ValidationError, validate

from .annotation_schema import ParagraphAnnotation
from .condition_parser import ConditionParser
from .cross_ref_resolver import CrossRefResolver
from .deontic_extractor import DeonticExtractor
from .dependency_mapper import DependencyMapper
from .dimension_extractor import DimensionExtractor

try:
    from .ifc_mapping import CODE_TO_IFC_MAP
except ImportError:
    CODE_TO_IFC_MAP = {}

DOCLANG_NS = "https://www.doclang.ai/ns/v0"
_HEADING_NUM_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)(?:[.)\s]+(.*))?$")

# Documented element-head tag sequence from doclang.xsd:
# (label?, thread?, (xref | href)?, layer?, location_block?, caption?, description?, summary?, custom?)
_HEAD_TAG_ORDER = [
    "label",
    "thread",
    "xref",
    "href",
    "layer",
    "location",
    "caption",
    "description",
    "summary",
    "custom",
]


def _strip_ns(tag: str) -> str:
    """Return local tag name stripping any XML namespace."""
    return tag.split("}")[-1] if "}" in tag else tag


def _get_element_id(elem: ET.Element) -> Optional[str]:
    """Extracts bg_element_id from <custom><bg_element_id value="..."/></custom> if present."""
    for custom in elem:
        if _strip_ns(custom.tag).lower() == "custom":
            for child in custom:
                if _strip_ns(child.tag).lower() == "bg_element_id":
                    val = child.attrib.get("value") or child.attrib.get("id")
                    if val:
                        return val
    return elem.attrib.get("id")


def parse_otsl_table_text(table_elem: ET.Element) -> Tuple[List[List[str]], str]:
    """
    Parses OTSL table delimiters (<fcel/> and <nl/>) with mixed content
    into rows and markdown-like text representation.
    """
    raw_text = "".join(table_elem.itertext()).strip()
    rows: List[List[str]] = []
    current_row: List[str] = []
    current_cell: List[str] = []

    # In OTSL, cells are delimited by <fcel/> and rows by <nl/>
    # Content typically sits in child.tail after the delimiter element
    for child in table_elem:
        tag = _strip_ns(child.tag).lower()
        if tag == "custom":
            continue
        if tag == "fcel":
            if current_cell:
                txt = " ".join("".join(current_cell).split())
                if txt:
                    current_row.append(txt)
                current_cell = []
            inner = "".join(child.itertext()).strip()
            if inner:
                current_cell.append(inner)
            if child.tail and child.tail.strip():
                current_cell.append(child.tail.strip())
        elif tag == "nl":
            if current_cell:
                txt = " ".join("".join(current_cell).split())
                if txt:
                    current_row.append(txt)
                current_cell = []
            if current_row:
                rows.append(current_row)
                current_row = []
            if child.tail and child.tail.strip():
                current_cell.append(child.tail.strip())
        else:
            txt = "".join(child.itertext()).strip()
            if txt:
                current_cell.append(txt)
            if child.tail and child.tail.strip():
                current_cell.append(child.tail.strip())

    if current_cell:
        txt = " ".join("".join(current_cell).split())
        if txt:
            current_row.append(txt)
    if current_row:
        rows.append(current_row)

    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows and raw_text:
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        rows = [[l] for l in lines]

    if rows:
        col_count = max(len(r) for r in rows)
        padded = [r + [""] * (col_count - len(r)) for r in rows]
        lines = ["| " + " | ".join(padded[0]) + " |", "| " + " | ".join(["---"] * col_count) + " |"]
        for r in padded[1:]:
            lines.append("| " + " | ".join(r) + " |")
        text_repr = "\n".join(lines)
    else:
        text_repr = raw_text

    return rows, text_repr


@dataclass
class DocLangNode:
    """Represents a structured node extracted from DocLang XML."""
    tag: str
    text: str
    element_id: Optional[str] = None
    level: int = 1
    section_number: Optional[str] = None
    section_name: Optional[str] = None
    section_path: List[str] = field(default_factory=list)
    annotation: Optional[ParagraphAnnotation] = None
    elem: Optional[ET.Element] = None


class DocLangAnnotator:
    """
    High-level DocLang processor that extracts, annotates, and serializes
    DocLang documents with linguistic NLP pre-analysis and full XSD validation.
    """

    def __init__(self, code_to_ifc_map: Optional[Dict[str, str]] = None):
        self._deontic = DeonticExtractor()
        self._condition = ConditionParser()
        self._crossref = CrossRefResolver()
        self._dependency = DependencyMapper()
        self._dimension = DimensionExtractor()
        self._ifc_map = code_to_ifc_map if code_to_ifc_map is not None else CODE_TO_IFC_MAP

    # ── Text Extraction & Parsing ─────────────────────────────────────────────

    def parse_nodes(
        self,
        xml_content: Optional[str] = None,
        root: Optional[ET.Element] = None,
    ) -> List[DocLangNode]:
        """
        Parses DocLang XML or an existing ElementTree root into structured DocLangNodes
        tracking section hierarchy, element IDs, and text blocks.
        """
        if root is None:
            if not xml_content or not xml_content.strip():
                return []
            try:
                root = safe_ET.fromstring(xml_content)
            except (ET.ParseError, DefusedXmlException):
                return []

        nodes: List[DocLangNode] = []
        current_sec_num: Optional[str] = None
        current_sec_name: Optional[str] = None
        level_map: Dict[int, str] = {}

        for elem in root.iter():
            tag = _strip_ns(elem.tag).lower()

            if tag == "heading":
                text = "".join(elem.itertext()).strip()
                level_str = elem.attrib.get("level", "1")
                try:
                    level = int(level_str)
                except ValueError:
                    level = 1

                match = _HEADING_NUM_PATTERN.match(text)
                if match:
                    sec_num = match.group(1)
                    sec_name = (match.group(2) or "").strip() or text
                else:
                    sec_num = None
                    sec_name = text

                level_map[level] = sec_num or text
                for deeper in list(level_map.keys()):
                    if deeper > level:
                        level_map.pop(deeper, None)

                current_sec_num = sec_num
                current_sec_name = sec_name
                sec_path = [level_map[l] for l in sorted(level_map.keys())]

                nodes.append(
                    DocLangNode(
                        tag="heading",
                        text=text,
                        element_id=_get_element_id(elem),
                        level=level,
                        section_number=sec_num,
                        section_name=sec_name,
                        section_path=sec_path,
                        elem=elem,
                    )
                )

            elif tag in ("text", "paragraph", "p"):
                text = "".join(elem.itertext()).strip()
                if text:
                    sec_path = [level_map[l] for l in sorted(level_map.keys())]
                    nodes.append(
                        DocLangNode(
                            tag=tag,
                            text=text,
                            element_id=_get_element_id(elem),
                            section_number=current_sec_num,
                            section_name=current_sec_name,
                            section_path=sec_path,
                            elem=elem,
                        )
                    )

            elif tag == "table":
                _, table_text = parse_otsl_table_text(elem)
                if table_text.strip():
                    sec_path = [level_map[l] for l in sorted(level_map.keys())]
                    nodes.append(
                        DocLangNode(
                            tag="table",
                            text=table_text,
                            element_id=_get_element_id(elem),
                            section_number=current_sec_num,
                            section_name=current_sec_name,
                            section_path=sec_path,
                            elem=elem,
                        )
                    )

        return nodes

    def doclang_to_text(self, xml_content: str) -> str:
        """Extracts complete plain text representation from DocLang XML."""
        nodes = self.parse_nodes(xml_content)
        return "\n\n".join(n.text for n in nodes if n.text.strip())

    # ── Paragraph Annotation ──────────────────────────────────────────────────

    def _extract_ifc_hints(self, text: str) -> List[Dict[str, str]]:
        """Map surface forms in text to IFC classes using the code-to-IFC map."""
        found = []
        seen_ifc: set = set()
        lower = text.lower()

        for surface, ifc_class in self._ifc_map.items():
            if re.search(rf"\b{re.escape(surface)}s?\b", lower):
                if ifc_class not in seen_ifc:
                    seen_ifc.add(ifc_class)
                    found.append({"surface": surface, "ifc_class": ifc_class})
        return found

    def _extract_subject(self, text: str, ifc_hints: list) -> Optional[str]:
        """Heuristic: noun phrase before deontic verb or first IFC hint."""
        m = re.match(r"^([^,\.]{3,60}?)\s+(?:shall|must|may|is\s+required)\b", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        if ifc_hints:
            return ifc_hints[0]["surface"]
        return None

    def annotate_text(self, text: str) -> ParagraphAnnotation:
        """Runs the 5 linguistic NLP extraction capabilities on a text block."""
        parsed = self._condition.parse(text)
        ifc_hints = self._extract_ifc_hints(text)
        subject = self._extract_subject(text, ifc_hints)
        crossrefs = self._crossref.extract(text)
        dependencies = self._dependency.extract(text)
        dimensions = self._dimension.extract(text)
        deontics = self._deontic.extract(text)

        # Cross-references inside dependencies
        for dep in dependencies:
            dep_text = dep.get("text", "")
            dep["refs"] = self._crossref.extract(dep_text)

        conditions_list = list(parsed.get("conditions", []))
        if parsed.get("exceptions"):
            for ex in parsed["exceptions"]:
                if isinstance(ex, dict):
                    conditions_list.append(ex)
                else:
                    conditions_list.append({"type": "exception", "marker": "except", "text": str(ex)})

        return {
            "deontics": deontics,
            "conditions": conditions_list,
            "requirements": parsed.get("requirements", []),
            "cross_refs": crossrefs,
            "dimensions": dimensions,
            "dependencies": dependencies,
            "ifc_hints": ifc_hints,
            "subject": subject,
        }

    # ── In-XML Markup Injection & Validation ──────────────────────────────────

    def annotate_doclang(
        self,
        xml_content: str,
        inject_custom_markup: bool = True,
        validate_xsd: bool = True,
    ) -> Tuple[str, List[DocLangNode]]:
        """
        Parses DocLang XML, annotates semantic elements with linguistic analysis,
        injects schema-valid <custom><bg_nlp .../></custom> metadata, and validates
        against DocLang XSD.

        Returns:
            Tuple of (annotated_xml_string, list_of_annotated_nodes).
        """
        if not xml_content or not xml_content.strip():
            return xml_content, []

        ET.register_namespace("", DOCLANG_NS)
        try:
            root = safe_ET.fromstring(xml_content)
        except (ET.ParseError, DefusedXmlException):
            return xml_content, []

        # Map nodes
        nodes = self.parse_nodes(root=root)
        for node in nodes:
            node.annotation = self.annotate_text(node.text)

        if not inject_custom_markup:
            return xml_content, nodes

        # In-place XML annotation injection
        for node in nodes:
            if node.elem is None or node.annotation is None:
                continue

            ann = node.annotation
            # Check if there is any linguistic signal to record
            has_signal = bool(
                ann["deontics"]
                or ann["conditions"]
                or ann["dimensions"]
                or ann["cross_refs"]
                or ann["dependencies"]
                or ann["ifc_hints"]
            )
            if not has_signal:
                continue

            elem = node.elem
            custom_el = None
            for child in elem:
                if _strip_ns(child.tag).lower() == "custom":
                    custom_el = child
                    break

            if custom_el is None:
                custom_el = ET.Element(f"{{{DOCLANG_NS}}}custom" if "}" in elem.tag else "custom")
                # Insert at valid element_head position:
                # Must be before any non-head children (such as text nodes or nested elements)
                # But after any existing head elements (label, xref, location, etc.)
                insert_idx = 0
                for i, child in enumerate(list(elem)):
                    tag_name = _strip_ns(child.tag).lower()
                    if tag_name in _HEAD_TAG_ORDER:
                        insert_idx = i + 1
                    else:
                        break
                elem.insert(insert_idx, custom_el)

            # Build <bg_nlp> container (attributes only, no text node to avoid itertext leaks)
            bg_nlp = ET.SubElement(custom_el, "bg_nlp")
            if ann.get("subject"):
                bg_nlp.set("subject", str(ann["subject"]))

            for d in ann["deontics"]:
                ET.SubElement(
                    bg_nlp,
                    "deontic",
                    attrib={
                        "operator": d.get("operator", ""),
                        "strength": d.get("strength", ""),
                        "negated": "true" if d.get("negated") else "false",
                        "span": d.get("span", ""),
                    },
                )

            for c in ann["conditions"]:
                ET.SubElement(
                    bg_nlp,
                    "condition",
                    attrib={
                        "type": c.get("type", ""),
                        "marker": c.get("marker", ""),
                        "text": c.get("text", "")[:120],
                    },
                )

            for dim in ann["dimensions"]:
                ET.SubElement(
                    bg_nlp,
                    "dimension",
                    attrib={
                        "value": str(dim.get("value", "")),
                        "unit": dim.get("unit", "") or "",
                        "constraint": dim.get("constraint", "") or "",
                        "span": dim.get("span", ""),
                    },
                )

            for xref in ann["cross_refs"]:
                ET.SubElement(
                    bg_nlp,
                    "cross_ref",
                    attrib={
                        "raw": xref.get("raw", ""),
                        "ref_type": xref.get("ref_type", ""),
                        "normalized": xref.get("normalized", ""),
                    },
                )

            for dep in ann["dependencies"]:
                ET.SubElement(
                    bg_nlp,
                    "dependency",
                    attrib={
                        "dep_type": dep.get("dep_type", ""),
                        "marker": dep.get("marker", ""),
                        "text": dep.get("text", "")[:120],
                    },
                )

            for ifc in ann["ifc_hints"]:
                ET.SubElement(
                    bg_nlp,
                    "ifc_hint",
                    attrib={
                        "surface": ifc.get("surface", ""),
                        "ifc_class": ifc.get("ifc_class", ""),
                    },
                )

        annotated_xml = ET.tostring(root, encoding="utf-8").decode("utf-8")

        # Validate against DocLang XSD if requested
        if validate_xsd:
            self.validate_xml(annotated_xml)

        return annotated_xml, nodes

    @staticmethod
    def validate_xml(xml_content: str) -> None:
        """Validates XML content against the official DocLang XSD schema."""
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
            f.write(xml_content)
            temp_path = Path(f.name)

        try:
            validate(str(temp_path), xsd_only=True)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    # ── Chunk Conversion for Rule Extraction ──────────────────────────────────

    def doclang_to_chunks(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Converts DocLang XML into structured section chunks with enriched
        NLP pre-analysis preambles, matching ConfidenceScorer chunk shape.
        """
        nodes = self.parse_nodes(xml_content)
        chunks: List[Dict[str, Any]] = []

        current_sec_num: Optional[str] = None
        current_sec_name: Optional[str] = None
        current_sec_path: List[str] = []
        current_paras: List[Dict[str, Any]] = []

        def flush():
            nonlocal current_paras
            if not current_paras:
                return
            full_text = "\n\n".join(p["text"] for p in current_paras).strip()
            preamble = self._build_preamble(current_paras, current_sec_name or "")
            filtered_text = f"{preamble}\n\n{full_text}" if preamble else full_text

            chunks.append(
                {
                    "section_number": current_sec_num,
                    "section_name": current_sec_name,
                    "section_path": list(current_sec_path),
                    "scored_paragraphs": list(current_paras),
                    "filtered_text": filtered_text,
                    "text": full_text,
                    "char_count": len(full_text),
                }
            )
            current_paras = []

        for node in nodes:
            if node.tag == "heading":
                flush()
                current_sec_num = node.section_number
                current_sec_name = node.section_name
                current_sec_path = node.section_path
                continue

            ann = self.annotate_text(node.text)
            node.annotation = ann
            para_dict = {
                "text": node.text,
                "element_id": node.element_id,
                "annotation": ann,
                "final_decision": "KEEP",
            }
            current_paras.append(para_dict)

        flush()
        return chunks

    def _build_preamble(self, scored_paras: List[Dict[str, Any]], section_name: str) -> str:
        """Constructs a compact [NLP PRE-ANALYSIS] preamble for the LLM."""
        lines = ["[NLP PRE-ANALYSIS]"]
        if section_name:
            lines.append(f"Section context: {section_name}")

        all_deontics = []
        all_dims = []
        all_xrefs = []
        all_deps = []
        all_hints = []

        for p in scored_paras:
            ann = p.get("annotation") or {}
            for d in ann.get("deontics", []):
                all_deontics.append(f"{d['operator']} ({d['strength']})")
            for dim in ann.get("dimensions", []):
                all_dims.append(dim.get("span") or f"{dim['value']} {dim['unit']}")
            for x in ann.get("cross_refs", []):
                all_xrefs.append(x.get("normalized") or x.get("raw"))
            for dep in ann.get("dependencies", []):
                all_deps.append(f"{dep['marker'].upper()}: {dep['text'][:60]}")
            for h in ann.get("ifc_hints", []):
                all_hints.append(f"{h['surface']} -> {h['ifc_class']}")

        if all_deontics:
            lines.append("Deontic signals: " + ", ".join(dict.fromkeys(all_deontics)))
        if all_dims:
            lines.append("Numeric constraints: " + ", ".join(dict.fromkeys(all_dims)))
        if all_xrefs:
            lines.append("Cross-references: " + ", ".join(dict.fromkeys(all_xrefs)))
        if all_deps:
            lines.append("Exceptions/Overrides: " + " | ".join(dict.fromkeys(all_deps)))
        if all_hints:
            lines.append("IFC Entity hints: " + ", ".join(dict.fromkeys(all_hints)))

        return "\n".join(lines) if len(lines) > 2 else ""
