"""
kg/similarity.py
------------------------------------------------
Multi-signal lexical distance between clause text and bSDD class/property
terms. Lexical-only by design (no embedding API calls): each candidate pair
is scored on four independent signals, combined into a weighted composite,
with the per-signal breakdown kept alongside so low-confidence matches stay
inspectable rather than being silently thresholded away.

Signals:
    exact_substring  — lowercase substring match (the heuristic the
                        production code in bim-guard already uses)
    jaccard_tokens    — Jaccard similarity of word-token sets
    fuzz_ratio        — rapidfuzz token_sort_ratio on the short "name" strings
    tfidf_cosine      — cosine similarity over a TF-IDF space built across the
                         whole corpus (clause texts + class/property
                         definitions), computed as one sparse matrix multiply
                         rather than per-pair, since scikit-learn isn't a
                         dependency of this repo
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

import numpy as np
import scipy.sparse as sp
from rapidfuzz import fuzz

_TOKEN_RE = re.compile(r"[a-z0-9]+")

#: Default composite weights. tfidf_cosine carries the most weight since it's
#: the only signal sensitive to definition/description text, not just names.
DEFAULT_WEIGHTS = {
    "tfidf_cosine": 0.40,
    "jaccard_tokens": 0.25,
    "fuzz_ratio": 0.20,
    "exact_substring": 0.15,
}


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def jaccard_tokens(a_tokens: Sequence[str], b_tokens: Sequence[str]) -> float:
    a, b = set(a_tokens), set(b_tokens)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def exact_substring(a: str, b: str) -> float:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return 1.0 if (a in b or b in a) else 0.0


def fuzz_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a, b) / 100.0


class TfidfSpace:
    """A minimal TF-IDF vectorizer over a fixed corpus, built with numpy/scipy
    only (no scikit-learn dependency). Returns L2-normalized sparse row vectors
    so cosine similarity between any two rows is a plain dot product."""

    def __init__(self, documents: Sequence[str]):
        docs_tokens = [tokenize(doc) for doc in documents]
        doc_freq: Counter = Counter()
        for toks in docs_tokens:
            doc_freq.update(set(toks))

        self.vocab: Dict[str, int] = {term: idx for idx, term in enumerate(doc_freq)}
        n_docs = len(documents)
        idf = np.zeros(len(self.vocab), dtype=np.float64)
        for term, idx in self.vocab.items():
            idf[idx] = math.log((1 + n_docs) / (1 + doc_freq[term])) + 1.0
        self._idf = idf

        rows, cols, vals = [], [], []
        for doc_idx, toks in enumerate(docs_tokens):
            for term, count in Counter(toks).items():
                col = self.vocab.get(term)
                if col is None:
                    continue
                rows.append(doc_idx)
                cols.append(col)
                vals.append(count * idf[col])

        matrix = sp.csr_matrix((vals, (rows, cols)), shape=(n_docs, len(self.vocab)))
        norms = np.sqrt(matrix.multiply(matrix).sum(axis=1)).A1
        norms[norms == 0] = 1.0
        self.matrix = matrix.multiply(1.0 / norms[:, None]).tocsr()


@dataclass
class CandidateMatch:
    """A scored clause <-> bSDD term candidate, with the full signal breakdown."""

    clause_ref: str
    term_uri: str
    term_kind: str  # "class" or "property"
    composite: float
    signals: Dict[str, float] = field(default_factory=dict)


def score_candidates(
    clause_refs: Sequence[str],
    clause_texts: Sequence[str],
    clause_headings: Sequence[str],
    term_uris: Sequence[str],
    term_names: Sequence[str],
    term_texts: Sequence[str],
    term_kind: str,
    *,
    top_k: int = 15,
    min_composite: float = 0.05,
    weights: Dict[str, float] | None = None,
) -> List[CandidateMatch]:
    """Scores clauses against bSDD terms (classes or properties).

    `term_texts` should be a definition+description blob per term (used for
    tfidf_cosine); `term_names` is the short display name (used for
    exact_substring/jaccard/fuzz against the clause heading).

    Uses the TF-IDF cosine matrix to shortlist the top_k candidates per
    clause (cheap: one sparse matmul), then computes the remaining signals
    only for that shortlist (cheap: rapidfuzz is a fast C implementation).
    """
    weights = weights or DEFAULT_WEIGHTS
    if not clause_refs or not term_uris:
        return []

    corpus = list(clause_texts) + list(term_texts)
    space = TfidfSpace(corpus)
    clause_vecs = space.matrix[: len(clause_texts)]
    term_vecs = space.matrix[len(clause_texts):]

    # clause_vecs @ term_vecs.T is dense-shaped (n_clauses x n_terms); for a
    # single-document run this fits comfortably in memory.
    cosine_matrix = (clause_vecs @ term_vecs.T).toarray()

    heading_tokens = [tokenize(h) for h in clause_headings]
    term_name_tokens = [tokenize(n) for n in term_names]

    results: List[CandidateMatch] = []
    for ci, clause_ref in enumerate(clause_refs):
        row = cosine_matrix[ci]
        if top_k and top_k < len(row):
            shortlist = np.argpartition(row, -top_k)[-top_k:]
        else:
            shortlist = np.arange(len(row))

        for ti in shortlist:
            cosine = float(row[ti])
            j_score = jaccard_tokens(heading_tokens[ci], term_name_tokens[ti])
            f_score = fuzz_ratio(clause_headings[ci], term_names[ti])
            s_score = exact_substring(clause_headings[ci], term_names[ti])

            composite = (
                weights.get("tfidf_cosine", 0.0) * cosine
                + weights.get("jaccard_tokens", 0.0) * j_score
                + weights.get("fuzz_ratio", 0.0) * f_score
                + weights.get("exact_substring", 0.0) * s_score
            )
            if composite < min_composite:
                continue

            results.append(
                CandidateMatch(
                    clause_ref=clause_ref,
                    term_uri=term_uris[ti],
                    term_kind=term_kind,
                    composite=composite,
                    signals={
                        "tfidf_cosine": cosine,
                        "jaccard_tokens": j_score,
                        "fuzz_ratio": f_score,
                        "exact_substring": s_score,
                    },
                )
            )

    return results
