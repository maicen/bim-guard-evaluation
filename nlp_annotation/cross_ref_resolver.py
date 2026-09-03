"""
nlp_annotation/cross_ref_resolver.py
----------------------------------------------
Extracts and normalises cross-references from building code text.

Pattern families covered:
    1. Decimal-hierarchy  — "Section 9.8.4.1", "Table 9.8.4.1.A"   (CODE, IBC, NFPA, NCC)
    2. Section-symbol     — "§ 1009.1", "§3.1(a)"                   (US legal/IBC)
    3. Alphanumeric std   — "EN 1992-1-1", "BS 5950", "AS 1170.1"   (Eurocodes, ISO, AU)
    4. Shorthand clause   — "cl. 2.3", "Reg. 7", "para. 4.1"        (UK, informal)
    5. Named document     — "Approved Document B", "BCA Part 3.9.2"  (UK, AU)
    6. Standard codes     — "ASTM C62", "CAN/ULC-S101", "NFPA 13"   (NA standards)
    7. Part refs          — "Part 3", "Part 9"

Context phrases recognised:
    "in accordance with", "as required by", "referred to in",
    "as provided in", "conforming to", "as specified in",
    "pursuant to", "subject to", "notwithstanding", "see"
"""

import re


# ── Shared helpers ─────────────────────────────────────────────────────────────

# Negative lookahead: don't match if immediately followed by a unit
_NO_UNIT = r'(?!\s*(?:mm|cm|m\b|m2|m²|%|min|h\b|°|deg|storey))'

# ── Pattern family 1: Decimal-hierarchy (CODE/IBC/NFPA/NCC) ────────────────────

_LABELS = (
    r'(?:Section|Article|Clause|Subsection|Sentence|Part|Appendix|Table|Figure|'
    r'Div(?:ision)?|Paragraph|Sub-?clause)'
)

_DECIMAL_NUM = (
    r'[1-9]\d*\.\d+'              # e.g. 9.8 or 10.3
    r'(?:\.\d+(?:\.\d+)?)?'       # up to 2 more groups: 9.8.4.1
    r'(?:\.\([0-9]+\))?'          # optional subsection: 9.8.4.1.(2)
    r'[A-Z]?'                     # optional letter suffix: 9.8.4.1.A (tables)
)

_LABELLED_REF = re.compile(
    rf'({_LABELS})\s+({_DECIMAL_NUM}){_NO_UNIT}',
    re.IGNORECASE,
)

_CONTEXT_PHRASES = (
    r'(?:in\s+accordance\s+with|as\s+required\s+by|referred\s+to\s+in|'
    r'as\s+provided\s+in|conforming\s+to|as\s+specified\s+in|'
    r'pursuant\s+to|subject\s+to|notwithstanding|in\s+conformance\s+with|'
    r'as\s+described\s+in|as\s+permitted\s+by|as\s+allowed\s+by|'
    r'under|per|see)\s+'
)

_CONTEXT_REF = re.compile(
    rf'({_CONTEXT_PHRASES})({_DECIMAL_NUM}){_NO_UNIT}',
    re.IGNORECASE,
)

_BARE_SECTION = re.compile(
    rf'\b({_DECIMAL_NUM}){_NO_UNIT}',
    re.IGNORECASE,
)

# ── Pattern family 2: Section-symbol § (US IBC / legal) ───────────────────────
# "§ 1009.1", "§3.1(a)", "§ R302.1"

_SECTION_SYMBOL = re.compile(
    r'§\s*([A-Z]?\d[\d.]*(?:\([a-z0-9]+\))?)',
    re.IGNORECASE,
)

# ── Pattern family 3: Alphanumeric standards (Eurocodes / ISO / AU / NZ) ──────
# "EN 1992-1-1", "BS 5950-1:2000", "AS 1170.1", "NZS 3101", "ASCE 7", "ACI 318"
# Case-sensitive (no IGNORECASE) to avoid "as required", "is 3.5 m" false positives.

_ALPHANUM_STANDARD = re.compile(
    r'\b((?:EN|BS|AS|NZS|ASCE|ACI|DIN|GB|JIS)\s+\d[\w.\-:]*\b)',
    # deliberately no re.IGNORECASE — uppercase prefix required
)

# Eurocode/AU/NZ standard with clause: "EN 1992-1-1 clause 6.4.3"
# Must fire BEFORE _LABELLED_REF so "clause 6.4.3" is consumed as part of this.
_EUROCODE_CLAUSE = re.compile(
    r'((?:EN|BS|AS|NZS)\s+[\w.\-]+)\s+(?:clause|cl\.?|section)\s+(\d[\d.]*)',
    re.IGNORECASE,
)

# ── Pattern family 4: Shorthand clause refs (UK / informal) ───────────────────
# "cl. 2.3", "cl.7", "Reg. 7", "Regulation 4(2)", "para. 4.1"

_SHORTHAND_REF = re.compile(
    r'\b(?:cl\.?|para\.?|Reg(?:ulation)?\.?)\s*(\d[\d.]*(?:\([a-z0-9]+\))?)',
    re.IGNORECASE,
)

# ── Pattern family 5: Named UK / AU documents ─────────────────────────────────
# "Approved Document B", "Approved Document Part L", "BCA Part 3.9.2"

_NAMED_DOC = re.compile(
    r'\b(?:Approved\s+Document\s+[A-Z\d]+(?:\s+Part\s+[A-Z\d]+)?|'
    r'BCA\s+Part\s+[\d.]+|'
    r'NBC\s+(?:Section\s+)?[\d.]+|'
    r'NBC\s+(?:Article\s+)?[\d.]+)',
    re.IGNORECASE,
)

# ── Pattern family 6: Standards (NA + international) ─────────────────────────
# "ASTM C62", "CAN/ULC-S101", "CSA O86", "ISO 9001", "NFPA 13", "UL 94"

_STANDARD_REF = re.compile(
    r'\b(?:CAN/\w+-\w+|ASTM\s+[A-Z]\d+[\w.-]*|CSA\s+[A-Z]\d+[\w.-]*|'
    r'ISO\s+\d+[\w.-]*|NFPA\s+\d+|UL\s+\d+|ULC-[A-Z]\d+|'
    r'ICC\s+\w+|ANSI\s+[\w/.-]+)\b',
    re.IGNORECASE,
)

# ── Pattern family 7: Part refs ───────────────────────────────────────────────
_PART_REF = re.compile(r'\bPart\s+([1-9]\d*)\b', re.IGNORECASE)


def _label_to_type(label: str) -> str:
    label = label.lower()
    if label in ('table',):
        return 'table'
    if label in ('figure',):
        return 'figure'
    if label in ('sentence',):
        return 'sentence'
    if label in ('article', 'section', 'clause', 'subsection', 'sub-clause', 'subclause'):
        return 'section'
    if label in ('part', 'appendix', 'division', 'paragraph'):
        return 'article'
    return 'section'


class CrossRefResolver:
    """Extract and normalise cross-references from a text string."""

    def extract(self, text: str) -> list:
        """Returns list of CrossRefAnnotation dicts (deduplicated by normalised ref)."""
        results = []
        seen_normalised: set = set()
        consumed_spans: list[tuple] = []

        def _add(raw, ref_type, normalised, context=''):
            if normalised in seen_normalised:
                return
            seen_normalised.add(normalised)
            results.append({
                'raw':        raw,
                'ref_type':   ref_type,
                'normalized': normalised,
                'context':    context,
            })

        def _mark(m):
            consumed_spans.append((m.start(), m.end()))

        def _consumed(m) -> bool:
            for s, e in consumed_spans:
                if m.start() >= s and m.end() <= e:
                    return True
            return False

        # 1. Eurocode/AU/NZ standard + clause — MUST be first so "clause 6.4.3"
        #    is consumed before _LABELLED_REF can match it separately.
        for m in _EUROCODE_CLAUSE.finditer(text):
            combined = f"{m.group(1).upper()} cl.{m.group(2)}"
            _add(m.group(0), 'standard', combined)
            _mark(m)

        # 2. Labelled refs: "Section 9.8.4.1", "Table 9.8.4.1.A"
        for m in _LABELLED_REF.finditer(text):
            if _consumed(m):
                continue
            label = m.group(1)
            num   = m.group(2)
            _add(m.group(0), _label_to_type(label), num)
            _mark(m)

        # 3. Context-phrase bare refs: "in accordance with 9.8.4.1"
        for m in _CONTEXT_REF.finditer(text):
            if _consumed(m):
                continue
            ctx = m.group(1).strip()
            num = m.group(2)
            _add(num, 'section', num, context=ctx)
            _mark(m)

        # 4. NA standards: ASTM, CAN/ULC, CSA, ISO, NFPA, UL, ANSI, ICC
        for m in _STANDARD_REF.finditer(text):
            if _consumed(m):
                continue
            _add(m.group(0), 'standard', m.group(0).upper())
            _mark(m)

        # 5. Alphanumeric standards (case-sensitive): "EN 1992-1-1", "AS 1170.1"
        for m in _ALPHANUM_STANDARD.finditer(text):
            if _consumed(m):
                continue
            _add(m.group(0), 'standard', m.group(1).upper())
            _mark(m)

        # 6. Section-symbol: "§ 1009.1", "§3.1(a)"
        for m in _SECTION_SYMBOL.finditer(text):
            if _consumed(m):
                continue
            _add(m.group(0), 'section', m.group(1))
            _mark(m)

        # 7. Shorthand clause refs: "cl. 2.3", "Reg. 7", "para. 4.1"
        for m in _SHORTHAND_REF.finditer(text):
            if _consumed(m):
                continue
            num    = m.group(1)
            marker = m.group(0).split(num)[0].strip().rstrip('.').lower()
            _add(m.group(0), 'article' if marker.startswith('reg') else 'section', num)
            _mark(m)

        # 8. Named documents: "Approved Document B", "BCA Part 3.9.2"
        for m in _NAMED_DOC.finditer(text):
            if _consumed(m):
                continue
            _add(m.group(0), 'article', m.group(0))
            _mark(m)

        # 9. Part refs: "Part 3"
        for m in _PART_REF.finditer(text):
            if _consumed(m):
                continue
            _add(m.group(0), 'article', f"Part {m.group(1)}")
            _mark(m)

        # 10. Bare decimal-hierarchy numbers with 3+ groups (last resort)
        for m in _BARE_SECTION.finditer(text):
            if _consumed(m):
                continue
            num = m.group(1)
            if num.count('.') >= 2:
                _add(num, 'section', num)
                _mark(m)

        return results

    def summarise(self, text: str) -> str:
        """Returns compact cross-ref list for NLP preamble."""
        refs = self.extract(text)
        if not refs:
            return ''
        parts = []
        for r in refs:
            if r['ref_type'] == 'standard':
                parts.append(r['normalized'])
            elif r['ref_type'] in ('table', 'figure'):
                parts.append(f"{r['ref_type'].capitalize()} {r['normalized']}")
            else:
                parts.append(r['normalized'])
        return ', '.join(parts)
