"""
nlp_annotation/dependency_mapper.py
---------------------------------------------
Identifies complex logical dependencies in building code text.

Dependency types:
    override     — "notwithstanding X, Y"       (Y supersedes X)
    subject_to   — "subject to X, Y"            (Y applies under X)
    alternative  — "in lieu of X, Y"            (Y is an alternative to X)
    addition     — "in addition to X, Y"        (Y supplements X)
    exception    — "except where/as X"          (Y does not apply when X)
    conditional  — "provided that X"            (X is a precondition for Y)
    tiered       — "where A ... where B ..."    (different thresholds per context)

Also extracts any cross-references embedded in the dependency clause.
"""

import re
from .cross_ref_resolver import CrossRefResolver


# Clause terminator: stop only at a sentence-ending period (period + space or
# period at end-of-string), NOT at dots inside CODE section numbers like 9.8.3.(1).
# Section numbers end with a digit or ')'; sentence-ending periods are followed
# by whitespace+capital or nothing.
_T = r'(?:,\s+(?=[A-Z(])|\.(?:\s+[A-Z]|\s*$)|$)'   # full clause boundary
_T_NOCOMMA = r'(?:\.(?:\s+[A-Z]|\s*$)|$)'            # period-only boundary

_DEPENDENCY_PATTERNS = [
    # Override: "Notwithstanding Sentence 9.8.2.1.(1), ..."
    (
        re.compile(rf'notwithstanding\s+(.+?){_T}', re.IGNORECASE | re.DOTALL),
        'override',
        'notwithstanding',
    ),
    # Subject to: "Subject to Subsection 9.8.2, ..."
    (
        re.compile(rf'subject\s+to\s+(.+?){_T}', re.IGNORECASE | re.DOTALL),
        'subject_to',
        'subject to',
    ),
    # In lieu of
    (
        re.compile(rf'in\s+lieu\s+of\s+(.+?){_T}', re.IGNORECASE | re.DOTALL),
        'alternative',
        'in lieu of',
    ),
    # In addition to
    (
        re.compile(rf'in\s+addition\s+to\s+(.+?){_T}', re.IGNORECASE | re.DOTALL),
        'addition',
        'in addition to',
    ),
    # Except where / except as permitted by / except that
    (
        re.compile(
            rf'except\s+(?:where|as\s+(?:permitted|required|provided|allowed)\s+(?:in|by)|that)\s+(.+?){_T_NOCOMMA}',
            re.IGNORECASE | re.DOTALL,
        ),
        'exception',
        'except',
    ),
    # Unless
    (
        re.compile(rf'unless\s+(.+?){_T}', re.IGNORECASE | re.DOTALL),
        'exception',
        'unless',
    ),
    # Provided that
    (
        re.compile(rf'provided\s+that\s+(.+?){_T}', re.IGNORECASE | re.DOTALL),
        'conditional',
        'provided that',
    ),
    # On condition that
    (
        re.compile(rf'on\s+condition\s+that\s+(.+?){_T}', re.IGNORECASE | re.DOTALL),
        'conditional',
        'on condition that',
    ),
    # Deemed to comply / deemed to satisfy
    (
        re.compile(
            rf'(?:is|are)\s+deemed\s+to\s+(?:comply|satisfy)\s+(?:with\s+)?(.+?){_T}',
            re.IGNORECASE | re.DOTALL,
        ),
        'alternative',
        'deemed to comply',
    ),
]

_RESOLVER = CrossRefResolver()


class DependencyMapper:
    """Identify complex logical dependencies in building code text."""

    def extract(self, text: str) -> list:
        """Returns list of DependencyAnnotation dicts."""
        results = []
        seen_spans: set[tuple] = set()

        for pattern, dep_type, marker in _DEPENDENCY_PATTERNS:
            for m in pattern.finditer(text):
                span_key = (m.start(), m.end())
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)

                clause_text = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else m.group(0)
                refs = _RESOLVER.extract(clause_text)

                results.append({
                    'dep_type': dep_type,
                    'marker':   marker,
                    'text':     m.group(0).strip(),
                    'refs':     refs,
                })

        return results

    def summarise(self, text: str) -> str:
        """
        Returns compact dependency summary for the NLP preamble.
        Groups by type and includes the clause text (truncated).
        """
        deps = self.extract(text)
        if not deps:
            return ''

        by_type: dict[str, list[str]] = {}
        for d in deps:
            by_type.setdefault(d['dep_type'], []).append(
                f'"{d["text"][:80].rstrip()}"'
            )

        parts = []
        for dep_type, clauses in by_type.items():
            parts.append(f"{dep_type}: {'; '.join(clauses)}")
        return ' | '.join(parts)
