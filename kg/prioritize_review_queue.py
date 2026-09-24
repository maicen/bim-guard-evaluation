"""
kg/prioritize_review_queue.py
------------------------------------------------
Closes a second loop: cross-links real production correction signal (from
eval/score_rule_extraction_corrections.py's live scoring against bim-guard's
`rule_extraction_drafts`) with the KG's uncertain-edge review queue
(kg.export_grounding / kg.apply_review_decisions), so a human reviewer works
through terms a *real extraction error* implicates first, rather than
whatever the LLM verification pass happened to find most ambiguous.

This is read-only end to end: it consumes a corrections result and a review
queue, and writes a re-ordered review queue. It does not write anything back
to bim-guard.

Two correction-rate signals, combined:

1. Exact-term match (strong signal): score_rule_extraction_corrections.py's
   diff_draft() records the LLM's wrong value and the human's fix for every
   changed field. When a `property_name` or `target_ifc_class` field was
   corrected, the LLM's original (wrong) value is a real, specific,
   production-observed bad grounding -- if that same term_name appears in
   the KG's uncertain-review queue, that row is almost certainly the root
   cause, and jumps to the top.

2. Field-kind correction rate (weaker signal): even without an exact term
   match, if `property_name` corrections are common in production but
   `target_ifc_class` corrections are rare, property-kind uncertain rows are
   more likely to matter than class-kind ones, all else equal.

Usage:
    uv run python -m kg.prioritize_review_queue \\
        --queue research/kg/obc_app_a_uncertain_review.csv \\
        --corrections eval/results/score_rule_extraction_corrections_<run_id>.json \\
        --out research/kg/obc_app_a_prioritized_review
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from kg.grounding import write_review_queue

# Maps a corrections diff's structural field name to the review queue's
# term_kind vocabulary ("class" | "property") -- only fields that are
# actually bSDD-grounded terms participate; a "severity" or "operator"
# correction has no KG term to match against.
FIELD_TO_TERM_KIND = {
    "target_ifc_class": "class",
    "property_name": "property",
    "property_set": "property",
}


def _norm(v: Any) -> str:
    return str(v or "").strip().lower()


def load_queue(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_correction_signal(path: Path) -> tuple[set[tuple[str, str]], Counter]:
    """Returns (bad_terms, kind_counts) from a score_rule_extraction_corrections.py --json result.

    bad_terms: {(term_kind, normalized_term_name), ...} -- every LLM-original
    value of a corrected target_ifc_class/property_name/property_set field,
    across every edited draft in the result.
    kind_counts: Counter({"class": n, "property": n}) -- how many corrections
    of each kind occurred, for the weaker kind-level signal.
    """
    with open(path, encoding="utf-8") as f:
        result = json.load(f)

    diffs = (result.get("details") or {}).get("diffs") or []
    bad_terms: set[tuple[str, str]] = set()
    kind_counts: Counter = Counter()

    for diff in diffs:
        for fd in diff.get("field_diffs", []):
            kind = FIELD_TO_TERM_KIND.get(fd.get("field"))
            if kind is None:
                continue
            kind_counts[kind] += 1
            original = _norm(fd.get("original"))
            if original:
                bad_terms.add((kind, original))

    return bad_terms, kind_counts


def prioritize(
    queue: list[dict[str, Any]], bad_terms: set[tuple[str, str]], kind_counts: Counter
) -> list[dict[str, Any]]:
    """Returns `queue` re-sorted, each row annotated with priority_score/priority_reason.

    Ordering, highest priority first: exact-term-matched rows (any real
    production correction implicating this exact term), then by field-kind
    correction count, then by the original llm_confidence ascending (the
    pipeline's own most-ambiguous-first ordering, preserved as the final
    tiebreaker so this is a re-ranking, not a replacement, of that signal).
    """
    total_kind = sum(kind_counts.values()) or 1
    prioritized = []
    for row in queue:
        kind = row.get("term_kind")
        term = _norm(row.get("term_name"))
        exact_match = (kind, term) in bad_terms
        kind_weight = kind_counts.get(kind, 0) / total_kind

        row = dict(row)
        row["priority_score"] = round((1000 if exact_match else 0) + kind_weight * 10, 4)
        row["priority_reason"] = (
            f"exact match: a real production correction changed a {kind} field "
            f"away from this exact term ({row.get('term_name')!r})"
            if exact_match
            else f"{kind}-kind fields are corrected in production ({kind_counts.get(kind, 0)}/{total_kind} of tracked corrections)"
            if kind_weight > 0
            else "no production correction signal for this term or kind -- ranked by original LLM ambiguity only"
        )
        prioritized.append(row)

    def _confidence(r: dict[str, Any]) -> float:
        v = r.get("llm_confidence")
        return float(v) if v not in (None, "") else 0.0

    prioritized.sort(key=lambda r: (-r["priority_score"], _confidence(r)))
    return prioritized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue", required=True, type=Path, help="Uncertain-review queue (CSV or JSON)")
    parser.add_argument("--corrections", required=True, type=Path, help="score_rule_extraction_corrections.py --json result file")
    parser.add_argument("--out", required=True, type=Path, help="Output path base (no extension)")
    args = parser.parse_args(argv)

    print(f"[1/3] Loading review queue: {args.queue}")
    queue = load_queue(args.queue)
    print(f"      {len(queue)} row(s)")

    print(f"[2/3] Loading correction signal: {args.corrections}")
    bad_terms, kind_counts = load_correction_signal(args.corrections)
    print(f"      {len(bad_terms)} exact bad-term signal(s), kind counts: {dict(kind_counts)}")

    print("[3/3] Prioritizing")
    prioritized = prioritize(queue, bad_terms, kind_counts)
    n_boosted = sum(1 for r in prioritized if r["priority_score"] >= 1000)
    print(f"      {n_boosted} row(s) boosted by an exact production-correction match")

    json_path = args.out.with_name(args.out.name + ".json")
    csv_path = args.out.with_name(args.out.name + ".csv")
    write_review_queue(prioritized, json_path, csv_path)
    print(f"      -> {csv_path}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
