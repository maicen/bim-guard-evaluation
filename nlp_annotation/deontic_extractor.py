"""
nlp_annotation/deontic_extractor.py
---------------------------------------------
Extracts deontic modal operators from building code text.

Deontic logic maps modal verbs to obligation strength:
    mandatory    — SHALL, MUST, IS REQUIRED TO, IS TO BE
    prohibited   — SHALL NOT, MUST NOT, IS PROHIBITED
    recommended  — SHOULD, OUGHT TO
    permitted    — MAY, IS PERMITTED, IS ALLOWED

Order matters: SHALL NOT must be checked before SHALL.
"""

import re
from collections import Counter


# (pattern, strength, canonical_operator)
# Most specific / negated patterns FIRST
_DEONTIC_PATTERNS = [
    (r'\bshall\s+not\b',                 'prohibited',   'SHALL NOT'),
    (r'\bmust\s+not\b',                  'prohibited',   'MUST NOT'),
    (r'\bis\s+prohibited\b',             'prohibited',   'IS PROHIBITED'),
    (r'\bare\s+prohibited\b',            'prohibited',   'ARE PROHIBITED'),
    (r'\bno\s+\w+\s+shall\b',           'prohibited',   'NO … SHALL'),
    (r'\bshall\b',                       'mandatory',    'SHALL'),
    (r'\bmust\b',                        'mandatory',    'MUST'),
    (r'\bis\s+required\s+to\b',         'mandatory',    'IS REQUIRED TO'),
    (r'\bare\s+required\s+to\b',        'mandatory',    'ARE REQUIRED TO'),
    (r'\bis\s+to\s+be\b',               'mandatory',    'IS TO BE'),
    (r'\bare\s+to\s+be\b',              'mandatory',    'ARE TO BE'),
    (r'\bshould\s+not\b',               'recommended',  'SHOULD NOT'),
    (r'\bshould\b',                      'recommended',  'SHOULD'),
    (r'\bought\s+to\b',                  'recommended',  'OUGHT TO'),
    (r'\bis\s+recommended\b',           'recommended',  'IS RECOMMENDED'),
    (r'\bmay\s+not\b',                   'prohibited',   'MAY NOT'),
    (r'\bmay\b',                         'permitted',    'MAY'),
    (r'\bis\s+permitted\s+to\b',        'permitted',    'IS PERMITTED TO'),
    (r'\bare\s+permitted\s+to\b',       'permitted',    'ARE PERMITTED TO'),
    (r'\bis\s+permitted\b',             'permitted',    'IS PERMITTED'),
    (r'\bare\s+permitted\b',            'permitted',    'ARE PERMITTED'),
    (r'\bis\s+allowed\b',               'permitted',    'IS ALLOWED'),
    (r'\bare\s+allowed\b',              'permitted',    'ARE ALLOWED'),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), s, op) for p, s, op in _DEONTIC_PATTERNS]


class DeonticExtractor:
    """Extract all deontic operators from a text string."""

    def extract(self, text: str) -> list:
        """
        Returns list of DeonticAnnotation dicts, one per match.
        Duplicate operators (e.g. SHALL appearing 3 times) each appear separately.
        """
        results = []
        for pattern, strength, operator in _COMPILED:
            for m in pattern.finditer(text):
                results.append({
                    'operator': operator,
                    'strength': strength,
                    'negated':  'NOT' in operator or strength == 'prohibited',
                    'span':     m.group(0),
                })
        return results

    def summarise(self, text: str) -> str:
        """
        Returns a compact summary string for the NLP preamble.
        e.g. "SHALL ×3 (mandatory), SHALL NOT ×1 (prohibited), MAY ×1 (permitted)"
        """
        annotations = self.extract(text)
        if not annotations:
            return ''

        counts: Counter = Counter()
        strength_map: dict = {}
        for ann in annotations:
            counts[ann['operator']] += 1
            strength_map[ann['operator']] = ann['strength']

        parts = [
            f"{op} x{counts[op]} ({strength_map[op]})"
            for op in counts
        ]
        return ', '.join(parts)
