"""
nlp_annotation
-----------------------
Module 1-b: NLP Annotation Layer.

Sits between Module 1-a (ConfidenceScorer output) and Module 3 (OpenAI extraction).
Annotates each paragraph with structured linguistic analysis:

    - Deontic operators     SHALL, MUST, MAY, SHOULD + obligation strength
    - Conditions            WHERE/WHEN/IF applicability clauses
    - Requirements          Main obligatory clauses
    - Cross-references      Section, Article, Table, Figure citations
    - Dependencies          NOTWITHSTANDING, EXCEPT, SUBJECT TO, IN LIEU OF
    - Dimensions            Numeric values + units + constraint type (min/max/range)
    - IFC hints             Surface form → IFC class mapping

These annotations are:
    1. Stored per-paragraph in `scored_paragraphs[i]['annotation']`
    2. Aggregated into a compact [NLP PRE-ANALYSIS] preamble prepended to each
       chunk's `filtered_text` — so Module 3 / OpenAI receives pre-parsed hints
       without any interface changes.

Usage:
    from app.modules.nlp_annotation import NLPAnnotator

    # Takes ConfidenceScorer output, returns annotated version
    annotated_chunks = NLPAnnotator().annotate(final_chunks)
"""

from .deontic_extractor  import DeonticExtractor
from .condition_parser   import ConditionParser
from .cross_ref_resolver import CrossRefResolver
from .dependency_mapper  import DependencyMapper
from .dimension_extractor import DimensionExtractor

# IFC entity map
try:
    from .ifc_mapping import CODE_TO_IFC_MAP
except ImportError:
    try:
        from app.modules.config import CODE_TO_IFC_MAP
    except ImportError:
        CODE_TO_IFC_MAP = {}


class NLPAnnotator:
    """
    NLP annotation layer. Annotates chunks in-place and enriches filtered_text
    with a structured pre-analysis preamble for the downstream LLM.
    """

    def __init__(self):
        self._deontic   = DeonticExtractor()
        self._condition = ConditionParser()
        self._crossref  = CrossRefResolver()
        self._dependency = DependencyMapper()
        self._dimension  = DimensionExtractor()

    # ── Public API ────────────────────────────────────────────────────────────

    def annotate(self, chunks: list) -> list:
        """
        Annotate all paragraphs in a list of ConfidenceScorer output chunks.

        Args:
            chunks (list): output from ConfidenceScorer.combine()
                           Each chunk has 'scored_paragraphs' and 'filtered_text'.

        Returns:
            list: same chunks with:
                  - 'annotation' key added to each paragraph dict
                  - 'filtered_text' enriched with [NLP PRE-ANALYSIS] preamble
        """
        print("[NLPAnnotator] Running NLP annotation...")
        total_paras = 0

        annotated_chunks = []
        for chunk in chunks:
            annotated_paras = []
            for para in chunk.get('scored_paragraphs', []):
                if para.get('final_decision') == 'SKIP':
                    annotated_paras.append(para)
                    continue

                annotation = self._annotate_paragraph(para['text'])
                annotated_paras.append({**para, 'annotation': annotation})
                total_paras += 1

            # Build chunk-level annotation preamble from all non-skip paragraphs
            chunk_text = chunk.get('filtered_text', '').strip()
            if chunk_text:
                preamble = self._build_preamble(chunk_text, chunk.get('section_name', ''))
                if preamble:
                    enriched_text = f"{preamble}\n\n{chunk_text}"
                else:
                    enriched_text = chunk_text
            else:
                enriched_text = chunk_text

            annotated_chunks.append({
                **chunk,
                'scored_paragraphs': annotated_paras,
                'filtered_text':     enriched_text,
            })

        print(f"[NLPAnnotator] Annotated {total_paras} paragraphs across {len(chunks)} sections.")
        return annotated_chunks

    # ── Private ───────────────────────────────────────────────────────────────

    def _annotate_paragraph(self, text: str) -> dict:
        """Run all extractors on a single paragraph and return annotation dict."""
        parsed   = self._condition.parse(text)
        ifc_hints = self._extract_ifc_hints(text)
        subject   = self._extract_subject(text, ifc_hints)

        return {
            'deontics':     self._deontic.extract(text),
            'conditions':   parsed['conditions'],
            'requirements': parsed['requirements'],
            'exceptions':   parsed['exceptions'],
            'cross_refs':   self._crossref.extract(text),
            'dimensions':   self._dimension.extract(text),
            'dependencies': self._dependency.extract(text),
            'ifc_hints':    ifc_hints,
            'subject':      subject,
        }

    def _extract_ifc_hints(self, text: str) -> list:
        """Map surface forms in text to IFC classes using the shared code-to-IFC map."""
        import re
        found = []
        seen_ifc: set = set()
        lower = text.lower()

        for surface, ifc_class in CODE_TO_IFC_MAP.items():
            # Whole-word match
            if re.search(rf'\b{re.escape(surface)}s?\b', lower):
                if ifc_class not in seen_ifc:
                    seen_ifc.add(ifc_class)
                    found.append({'surface': surface, 'ifc_class': ifc_class})
        return found

    def _extract_subject(self, text: str, ifc_hints: list) -> str | None:
        """
        Heuristic: the subject of the rule is usually the first noun phrase
        before the deontic verb. Falls back to first IFC hint's surface form.
        """
        import re
        # Look for "X shall" or "X must" — X is the subject noun phrase
        m = re.match(r'^([^,\.]{3,60}?)\s+(?:shall|must|may|is\s+required)\b', text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        if ifc_hints:
            return ifc_hints[0]['surface']
        return None

    def _build_preamble(self, filtered_text: str, section_name: str = '') -> str:
        """
        Build a compact [NLP PRE-ANALYSIS] block for the chunk's filtered_text.
        Returns '' if nothing notable was found.
        """
        lines = []

        deontic_summary = self._deontic.summarise(filtered_text)
        if deontic_summary:
            lines.append(f"Deontic: {deontic_summary}")

        ref_summary = self._crossref.summarise(filtered_text)
        if ref_summary:
            lines.append(f"Cross-refs: {ref_summary}")

        dim_summary = self._dimension.summarise(filtered_text)
        if dim_summary:
            lines.append(f"Dimensions: {dim_summary}")

        cond_summary, exc_summary = self._condition.summarise(filtered_text)
        if cond_summary:
            lines.append(f"Conditions: {cond_summary}")
        if exc_summary:
            lines.append(f"Exceptions: {exc_summary}")

        dep_summary = self._dependency.summarise(filtered_text)
        if dep_summary:
            lines.append(f"Dependencies: {dep_summary}")

        # IFC hints from whole chunk
        ifc_hints = self._extract_ifc_hints(filtered_text)
        if ifc_hints:
            classes = ', '.join(dict.fromkeys(h['ifc_class'] for h in ifc_hints))
            lines.append(f"IFC targets: {classes}")

        if not lines:
            return ''

        header = f"[NLP PRE-ANALYSIS - {section_name}]" if section_name else "[NLP PRE-ANALYSIS]"
        body   = '\n'.join(f"  {line}" for line in lines)
        return f"{header}\n{body}\n[END PRE-ANALYSIS]"
