"""
nlp_annotation/dimension_extractor.py
-----------------------------------------------
Extracts numeric dimensions and their units from building code text.

Identifies constraint type from surrounding context:
    min    — "not less than X", "at least X", "minimum X"
    max    — "not more than X", "not greater than X", "maximum X"
    range  — "between X and Y", "from X to Y"
    exact  — bare value with unit, no qualifier

Units covered: mm, m, cm, m², m³, %, min, h, °, storeys
"""

import re


# Unit normalisation: variant → canonical
_UNIT_VARIANTS = {
    'mm':         'mm',
    'millimetre': 'mm',  'millimeter': 'mm',
    'millimetres':'mm',  'millimeters':'mm',
    'cm':         'cm',
    'm²':         'm2',  'm2': 'm2',  'sq m': 'm2',  'sq. m': 'm2',
    'm³':         'm3',  'm3': 'm3',
    'm':          'm',   'metre': 'm', 'meter': 'm',
    'metres': 'm', 'meters': 'm',
    'min':        'min', 'minute': 'min', 'minutes': 'min',
    'h':          'h',   'hr': 'h',  'hour': 'h',   'hours': 'h',
    '%':          '%',   'percent': '%', 'per cent': '%',
    '°':          'deg', 'deg': 'deg', 'degrees': 'deg',
    'storey':     'storeys', 'storeys': 'storeys',
    'story':      'storeys', 'stories': 'storeys',
    'floor':      'storeys', 'floors': 'storeys',
}

_UNIT_RE = (
    r'(?:mm|millimetres?|millimeters?|cm|m²|m³|m2|m3|sq\.?\s*m|metres?|meters?|m\b|'
    r'min(?:utes?)?|h(?:rs?|ours?)?|%|per\s?cent|°|deg(?:rees?)?|'
    r'store?y(?:s|ies)?|floors?)'
)
_NUM_RE  = r'\d+(?:[.,]\d+)?'

# Range: "between X [unit] and Y [unit]"
_RANGE_PATTERN = re.compile(
    rf'between\s+({_NUM_RE})\s*({_UNIT_RE})?\s+and\s+({_NUM_RE})\s*({_UNIT_RE})',
    re.IGNORECASE,
)

# From-to range: "from X mm to Y mm"
_FROM_TO_PATTERN = re.compile(
    rf'from\s+({_NUM_RE})\s*({_UNIT_RE})?\s+to\s+({_NUM_RE})\s*({_UNIT_RE})',
    re.IGNORECASE,
)

# Min qualifier: "not less than X unit", "not be less than X unit", etc.
_MIN_PATTERNS = [
    re.compile(
        rf'(?:not\s+(?:be\s+)?less\s+than|not\s+(?:be\s+)?fewer\s+than|'
        rf'at\s+least|a\s+minimum\s+(?:of\s+)?|minimum\s+(?:of\s+)?)\s*({_NUM_RE})\s*({_UNIT_RE})',
        re.IGNORECASE,
    ),
]

# Max qualifier: "not more than X unit", "not be greater than X unit", etc.
_MAX_PATTERNS = [
    re.compile(
        rf'(?:not\s+(?:be\s+)?more\s+than|not\s+(?:be\s+)?greater\s+than|'
        rf'not\s+(?:be\s+)?exceed\s+|a\s+maximum\s+(?:of\s+)?|maximum\s+(?:of\s+)?)\s*({_NUM_RE})\s*({_UNIT_RE})',
        re.IGNORECASE,
    ),
]

# Exact: bare number + unit (not already captured by range/min/max)
_EXACT_PATTERN = re.compile(
    rf'({_NUM_RE})\s*({_UNIT_RE})',
    re.IGNORECASE,
)


def _normalise_unit(raw: str) -> str:
    if not raw:
        return ''
    key = raw.strip().lower().replace('.', '')
    return _UNIT_VARIANTS.get(key, raw.strip().lower())


def _to_float(s: str) -> float:
    return float(str(s).replace(',', '.'))


class DimensionExtractor:
    """Extract numeric dimensions with units and constraint types."""

    def extract(self, text: str) -> list:
        """Returns list of DimensionAnnotation dicts."""
        results = []
        consumed_spans: list[tuple] = []

        def already_consumed(m) -> bool:
            for s, e in consumed_spans:
                if m.start() >= s and m.end() <= e:
                    return True
            return False

        # 1. Ranges: between X and Y
        for m in _RANGE_PATTERN.finditer(text):
            if already_consumed(m):
                continue
            v_min  = _to_float(m.group(1))
            u_min  = _normalise_unit(m.group(2) or '')
            v_max  = _to_float(m.group(3))
            u_max  = _normalise_unit(m.group(4) or u_min)
            unit   = u_min or u_max
            results.append({
                'value':     None,
                'unit':      unit,
                'constraint': 'range',
                'value_min': v_min,
                'value_max': v_max,
                'span':      m.group(0),
            })
            consumed_spans.append((m.start(), m.end()))

        # 2. From-to ranges
        for m in _FROM_TO_PATTERN.finditer(text):
            if already_consumed(m):
                continue
            v_min = _to_float(m.group(1))
            u_min = _normalise_unit(m.group(2) or '')
            v_max = _to_float(m.group(3))
            u_max = _normalise_unit(m.group(4) or u_min)
            unit  = u_min or u_max
            results.append({
                'value':     None,
                'unit':      unit,
                'constraint': 'range',
                'value_min': v_min,
                'value_max': v_max,
                'span':      m.group(0),
            })
            consumed_spans.append((m.start(), m.end()))

        # 3. Min qualifiers
        for pattern in _MIN_PATTERNS:
            for m in pattern.finditer(text):
                if already_consumed(m):
                    continue
                results.append({
                    'value':     _to_float(m.group(1)),
                    'unit':      _normalise_unit(m.group(2) or ''),
                    'constraint': 'min',
                    'value_min': _to_float(m.group(1)),
                    'value_max': None,
                    'span':      m.group(0),
                })
                consumed_spans.append((m.start(), m.end()))

        # 4. Max qualifiers
        for pattern in _MAX_PATTERNS:
            for m in pattern.finditer(text):
                if already_consumed(m):
                    continue
                results.append({
                    'value':     _to_float(m.group(1)),
                    'unit':      _normalise_unit(m.group(2) or ''),
                    'constraint': 'max',
                    'value_min': None,
                    'value_max': _to_float(m.group(1)),
                    'span':      m.group(0),
                })
                consumed_spans.append((m.start(), m.end()))

        # 5. Exact values (not already consumed)
        for m in _EXACT_PATTERN.finditer(text):
            if already_consumed(m):
                continue
            unit = _normalise_unit(m.group(2))
            if not unit:
                continue
            results.append({
                'value':     _to_float(m.group(1)),
                'unit':      unit,
                'constraint': 'exact',
                'value_min': None,
                'value_max': None,
                'span':      m.group(0),
            })
            consumed_spans.append((m.start(), m.end()))

        return results

    def summarise(self, text: str) -> str:
        """
        Returns compact dimension summary for NLP preamble.
        e.g. "900 mm (min), 125–200 mm (range), 0.35 m²"
        """
        dims = self.extract(text)
        if not dims:
            return ''
        parts = []
        for d in dims:
            if d['constraint'] == 'range':
                parts.append(f"{d['value_min']}-{d['value_max']} {d['unit']} (range)")
            elif d['constraint'] == 'min':
                parts.append(f"{d['value']} {d['unit']} (min)")
            elif d['constraint'] == 'max':
                parts.append(f"{d['value']} {d['unit']} (max)")
            else:
                parts.append(f"{d['value']} {d['unit']}")
        return ', '.join(parts)
