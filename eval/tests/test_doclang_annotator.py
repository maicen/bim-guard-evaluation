"""
eval/tests/test_doclang_annotator.py
---------------------------------------------
Unit tests for DocLangAnnotator, native DocLang v0.7 XML processing,
linguistic annotation injection, and Label Studio DocLang bridge.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from doclang import validate

from eval.label_studio_bridge import LabelStudioBridge
from nlp_annotation.doclang_annotator import DocLangAnnotator, parse_otsl_table_text

SAMPLE_DOCLANG_XML = """<doclang xmlns="https://www.doclang.ai/ns/v0" version="0.7">
  <heading level="1">9.8. Stairs and Ramps</heading>
  <heading level="2">9.8.4. Step Dimensions</heading>
  <text><custom><bg_element_id value="elem-stairs-run"/></custom>Every flight of stairs shall have a minimum run of 280 mm.</text>
  <text><custom><bg_element_id value="elem-stairs-riser"/></custom>Except as permitted in Sentence (2), risers in stairs shall not exceed 200 mm in height.</text>
  <table>
    <fcel/>Location<fcel/>Max Rise (mm)<fcel/>Min Run (mm)<nl/>
    <fcel/>Residential<fcel/>200<fcel/>210<nl/>
    <fcel/>Commercial<fcel/>180<fcel/>280
  </table>
</doclang>"""


def test_parse_doclang_nodes():
    annotator = DocLangAnnotator()
    nodes = annotator.parse_nodes(SAMPLE_DOCLANG_XML)

    assert len(nodes) == 5
    assert nodes[0].tag == "heading"
    assert nodes[0].text == "9.8. Stairs and Ramps"
    assert nodes[0].section_number == "9.8"

    assert nodes[1].tag == "heading"
    assert nodes[1].text == "9.8.4. Step Dimensions"
    assert nodes[1].section_number == "9.8.4"

    assert nodes[2].tag == "text"
    assert nodes[2].element_id == "elem-stairs-run"
    assert nodes[2].section_number == "9.8.4"
    assert "minimum run of 280 mm" in nodes[2].text

    assert nodes[3].tag == "text"
    assert nodes[3].element_id == "elem-stairs-riser"

    assert nodes[4].tag == "table"
    assert "Location" in nodes[4].text


def test_doclang_element_id_preservation():
    annotator = DocLangAnnotator()
    nodes = annotator.parse_nodes(SAMPLE_DOCLANG_XML)

    assert nodes[2].element_id == "elem-stairs-run"
    assert nodes[3].element_id == "elem-stairs-riser"


def test_doclang_annotate_and_xsd_validation():
    annotator = DocLangAnnotator()
    annotated_xml, nodes = annotator.annotate_doclang(SAMPLE_DOCLANG_XML, validate_xsd=True)

    assert "<custom>" in annotated_xml
    assert "<bg_nlp" in annotated_xml
    assert 'bg_element_id value="elem-stairs-run"' in annotated_xml
    assert 'operator="SHALL"' in annotated_xml
    assert 'value="280.0"' in annotated_xml
    assert 'unit="mm"' in annotated_xml

    # Explicit direct XSD validation via doclang library
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(annotated_xml)
        temp_file = Path(f.name)
    try:
        validate(str(temp_file), xsd_only=True)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def test_doclang_to_text_no_leakage():
    annotator = DocLangAnnotator()
    annotated_xml, _ = annotator.annotate_doclang(SAMPLE_DOCLANG_XML, validate_xsd=True)

    plain_text = annotator.doclang_to_text(annotated_xml)
    assert "9.8. Stairs and Ramps" in plain_text
    assert "minimum run of 280 mm" in plain_text
    # Annotations must not leak into text extraction
    assert "bg_nlp" not in plain_text
    assert "operator=" not in plain_text
    assert "bg_element_id" not in plain_text


def test_doclang_to_chunks_with_preamble():
    annotator = DocLangAnnotator()
    chunks = annotator.doclang_to_chunks(SAMPLE_DOCLANG_XML)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["section_number"] == "9.8.4"
    assert "[NLP PRE-ANALYSIS]" in chunk["filtered_text"]
    assert "Deontic signals:" in chunk["filtered_text"]
    assert "Numeric constraints:" in chunk["filtered_text"]
    assert len(chunk["scored_paragraphs"]) == 3  # 2 text paragraphs + 1 table


def test_otsl_table_parsing():
    import xml.etree.ElementTree as ET
    xml = "<table><fcel/>Header 1<fcel/>Header 2<nl/><fcel/>Val A<fcel/>Val B</table>"
    elem = ET.fromstring(xml)
    rows, text_repr = parse_otsl_table_text(elem)

    assert len(rows) == 2
    assert rows[0] == ["Header 1", "Header 2"]
    assert rows[1] == ["Val A", "Val B"]
    assert "| Header 1 | Header 2 |" in text_repr


def test_label_studio_doclang_bidirectional_roundtrip():
    # 1. Convert DocLang XML to Label Studio tasks
    tasks = LabelStudioBridge.doclang_to_label_studio_tasks(SAMPLE_DOCLANG_XML, pre_annotate=True)
    assert len(tasks) == 5

    # Check task metadata and pre-annotations
    stair_task = next(t for t in tasks if t["data"]["meta"]["element_id"] == "elem-stairs-run")
    assert stair_task["data"]["section_ref"] == "9.8.4"
    assert len(stair_task["predictions"]) == 1
    results = stair_task["predictions"][0]["result"]
    assert any(r.get("value", {}).get("labels") == ["MANDATORY"] for r in results)
    assert any(r.get("value", {}).get("labels") in (["DIM_EXACT"], ["DIM_MIN"]) for r in results)

    riser_task = next(t for t in tasks if t["data"]["meta"]["element_id"] == "elem-stairs-riser")
    riser_results = riser_task["predictions"][0]["result"]
    assert any(r.get("value", {}).get("labels") == ["DIM_MAX"] for r in riser_results)
    assert any(r.get("value", {}).get("labels") == ["EXCEPTION"] for r in riser_results)

    # 2. Inject back into DocLang XML and validate XSD
    updated_xml = LabelStudioBridge.label_studio_to_doclang(tasks, SAMPLE_DOCLANG_XML, validate_xsd=True)
    assert 'bg_element_id value="elem-stairs-run"' in updated_xml
    assert "<bg_nlp" in updated_xml
    assert 'deontic operator="SHALL"' in updated_xml
