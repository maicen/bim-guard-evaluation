"""
nlp_annotation/annotation_schema.py
---------------------------------------------
TypedDict definitions for the per-paragraph NLP annotation produced by Module 1-b.
These feed into the filtered_text preamble that Module 3 / OpenAI receives.
"""

from typing import TypedDict


class DeonticAnnotation(TypedDict):
    operator: str       # "SHALL", "MUST NOT", "MAY", etc.
    strength: str       # "mandatory" | "prohibited" | "recommended" | "permitted"
    negated: bool
    span: str           # verbatim phrase from source


class ConditionAnnotation(TypedDict):
    type: str           # "applicability" | "exception" | "qualification"
    marker: str         # "Where", "except", "unless", etc.
    text: str           # condition clause text


class CrossRefAnnotation(TypedDict):
    raw: str            # as written in source
    ref_type: str       # "section" | "article" | "table" | "figure" | "clause" | "sentence"
    normalized: str     # digits-only form, e.g. "9.8.4.1"
    context: str        # surrounding phrase, e.g. "in accordance with 9.8.4.1"


class DimensionAnnotation(TypedDict):
    value: float
    unit: str
    constraint: str     # "min" | "max" | "exact" | "range"
    value_min: float | None
    value_max: float | None
    span: str           # full phrase, e.g. "not less than 900 mm"


class DependencyAnnotation(TypedDict):
    dep_type: str       # "exception" | "override" | "alternative" | "addition" | "conditional"
    marker: str         # "notwithstanding", "subject to", "in lieu of", etc.
    text: str           # the full dependency clause
    refs: list          # CrossRefAnnotations found inside this clause


class IFCHintAnnotation(TypedDict):
    surface: str        # "stair", "guard", etc.
    ifc_class: str      # "IfcStairFlight", "IfcRailing", etc.


class ParagraphAnnotation(TypedDict):
    deontics: list
    conditions: list
    requirements: list
    cross_refs: list
    dimensions: list
    dependencies: list
    ifc_hints: list
    subject: str | None
