"""
nlp_annotation/condition_parser.py
--------------------------------------------
Splits building code sentences into structural clauses:
    applicability  — the WHERE/WHEN/IF clause (scope of the rule)
    exception      — the EXCEPT/UNLESS clause (when rule doesn't apply)
    qualification  — other modifiers (PROVIDED THAT, SUBJECT TO)
    requirement    — the main obligatory clause (contains the deontic verb)

Uses spaCy for sentence boundary detection if available, otherwise
splits on punctuation. Clause splitting is regex-based regardless.

Examples
--------
Input:  "Where a building exceeds 3 storeys, exit stairs shall have a
         minimum clear width of not less than 1100 mm."
Output: applicability = "a building exceeds 3 storeys"
        requirement   = "exit stairs shall have a minimum clear width ..."

Input:  "Guards shall not be less than 900 mm, except where the guard
         is on a stairway."
Output: requirement   = "Guards shall not be less than 900 mm"
        exception     = "the guard is on a stairway"
"""

import re

# ── spaCy optional ─────────────────────────────────────────────────────────────
try:
    import spacy
    _nlp = spacy.load('en_core_web_sm')
    _SPACY_OK = True
except Exception:
    _SPACY_OK = False


# ── Discourse marker patterns ──────────────────────────────────────────────────

# Sentence-opening applicability markers
_APPLICABILITY_OPENERS = re.compile(
    r'^(?:'
    r'where\b|when\b|if\b|'
    r'in\s+(?:the\s+case\s+of|buildings?\s+of|occupancies?\s+of|areas?\s+where)|'
    r'for\s+(?:buildings?|occupancies?|purposes?\s+of|the\s+purposes?\s+of)|'
    r'in\s+buildings?\s+(?:of|where|that)|'
    r'where\s+a\s+building'
    r')',
    re.IGNORECASE,
)

# Exception markers (mid-sentence)
_EXCEPTION_MARKERS = re.compile(
    r',?\s*(?:'
    r'except\s+(?:where|as|that|when|if)\b|'
    r'unless\b|'
    r'other\s+than\b|'
    r'provided\s+that\b|'
    r'on\s+condition\s+that\b'
    r')',
    re.IGNORECASE,
)

# Qualification markers (mid-sentence only — "notwithstanding" at sentence
# start is handled separately below and also by dependency_mapper)
_QUALIFICATION_MARKERS = re.compile(
    r',?\s*(?:subject\s+to|in\s+addition\s+to)\b',
    re.IGNORECASE,
)

# Sentence-opening override: "Notwithstanding X, [requirement]"
# or "Subject to X, [requirement]"
_OVERRIDE_OPENER = re.compile(
    r'^(?:notwithstanding|subject\s+to)\s+',
    re.IGNORECASE,
)

# Deontic verbs — presence indicates the main requirement clause
_DEONTIC_RE = re.compile(
    r'\b(?:shall|must|may|is\s+required|are\s+required|is\s+to\s+be|are\s+to\s+be)\b',
    re.IGNORECASE,
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using spaCy if available, else naive split."""
    if _SPACY_OK:
        doc = _nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    # Naive: split on '. ' followed by capital letter
    parts = re.split(r'(?<=\.)\s+(?=[A-Z])', text)
    return [p.strip() for p in parts if p.strip()]


def _parse_sentence(sentence: str) -> dict:
    """
    Parse a single sentence into conditions, requirements, exceptions.

    Returns:
        dict with keys: conditions, requirements, exceptions
    """
    conditions: list = []
    requirements: list = []
    exceptions: list = []

    # Step 1: check for sentence-opening applicability clause
    # Pattern: "Where [condition], [requirement]"
    # Handle sentence-opening "Notwithstanding X, Y" / "Subject to X, Y"
    # The override clause (X) is captured by dependency_mapper; here we
    # just skip past it so the requirement (Y) is correctly parsed.
    override_match = _OVERRIDE_OPENER.match(sentence.strip())
    if override_match:
        comma_pos = sentence.find(',', override_match.end())
        if comma_pos != -1:
            sentence = sentence[comma_pos + 1:].strip()

    opener_match = _APPLICABILITY_OPENERS.match(sentence.strip())
    if opener_match:
        # Find the comma that ends the condition clause
        comma_pos = sentence.find(',', opener_match.end())
        if comma_pos != -1 and _DEONTIC_RE.search(sentence[comma_pos:]):
            condition_text = sentence[opener_match.start(): comma_pos].strip()
            # Strip the leading marker word
            marker_end = opener_match.end()
            condition_text = sentence[marker_end:comma_pos].strip()
            conditions.append({
                'type':   'applicability',
                'marker': opener_match.group(0).strip(),
                'text':   condition_text,
            })
            remaining = sentence[comma_pos + 1:].strip()
        else:
            remaining = sentence
    else:
        remaining = sentence

    # Step 2: split remaining on exception markers
    exc_match = _EXCEPTION_MARKERS.search(remaining)
    if exc_match:
        req_text  = remaining[:exc_match.start()].strip()
        exc_text  = remaining[exc_match.end():].strip()
        # Strip trailing period
        exc_text  = exc_text.rstrip('.')
        if req_text:
            requirements.append(req_text)
        if exc_text:
            exceptions.append({
                'type':   'exception',
                'marker': exc_match.group(0).strip().lstrip(',').strip(),
                'text':   exc_text,
            })
    else:
        # Step 3: check for qualification markers
        qual_match = _QUALIFICATION_MARKERS.search(remaining)
        if qual_match:
            req_text  = remaining[:qual_match.start()].strip()
            qual_text = remaining[qual_match.end():].strip().rstrip('.')
            if req_text:
                requirements.append(req_text)
            if qual_text:
                conditions.append({
                    'type':   'qualification',
                    'marker': qual_match.group(0).strip().lstrip(',').strip(),
                    'text':   qual_text,
                })
        else:
            if remaining:
                requirements.append(remaining.rstrip('.'))

    return {
        'conditions':   conditions,
        'requirements': requirements,
        'exceptions':   exceptions,
    }


class ConditionParser:
    """
    Parse natural language building code rules into structural clauses.
    """

    def parse(self, text: str) -> dict:
        """
        Parse all sentences in text.

        Returns:
            dict:
                conditions   (list): applicability & qualification clauses
                requirements (list): main obligatory clauses
                exceptions   (list): exception clauses
        """
        sentences = _split_sentences(text)
        all_conditions:   list = []
        all_requirements: list = []
        all_exceptions:   list = []

        for sent in sentences:
            if not sent.strip():
                continue
            result = _parse_sentence(sent)
            all_conditions.extend(result['conditions'])
            all_requirements.extend(result['requirements'])
            all_exceptions.extend(result['exceptions'])

        return {
            'conditions':   all_conditions,
            'requirements': all_requirements,
            'exceptions':   all_exceptions,
        }

    def summarise(self, text: str) -> tuple[str, str]:
        """
        Returns (conditions_summary, exceptions_summary) for the NLP preamble.
        Each is a comma-joined string of quoted clause texts, or '' if none.
        """
        parsed = self.parse(text)

        cond_parts = [
            f'"{c["text"][:100]}"' for c in parsed['conditions']
        ]
        exc_parts = [
            f'"{e["text"][:100]}"' for e in parsed['exceptions']
        ]

        return ', '.join(cond_parts), ', '.join(exc_parts)
