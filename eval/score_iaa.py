"""
eval/score_iaa.py
---------------------------------------------
Inter-Annotator Agreement (IAA) calculation for building code regulatory NLP annotations.
Computes:
1. Span-level agreement (Precision, Recall, F1 with IoU threshold)
2. Cohen's Kappa (pairwise across annotators for categorical tags: deontics, IFC targets)
3. Fleiss' Kappa (multi-rater categorical agreement)
Outputs formatted markdown tables suitable for publication (Tables 1-7 in research validation).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def compute_span_iou(span_a: Tuple[int, int], span_b: Tuple[int, int]) -> float:
    """Computes Intersection over Union (IoU) of two character spans [start, end]."""
    start_a, end_a = span_a
    start_b, end_b = span_b

    inter_start = max(start_a, start_b)
    inter_end = min(end_a, end_b)
    intersection = max(0, inter_end - inter_start)

    union = max(end_a, end_b) - min(start_a, start_b)
    return intersection / union if union > 0 else 0.0


def compute_cohens_kappa(rater1: List[str], rater2: List[str]) -> float:
    """
    Computes Cohen's Kappa between two raters over aligned categorical items.
    """
    if not rater1 or len(rater1) != len(rater2):
        return 0.0

    n = len(rater1)
    categories = sorted(list(set(rater1) | set(rater2)))
    if len(categories) <= 1:
        return 1.0

    # Observed agreement
    agreements = sum(1 for a, b in zip(rater1, rater2) if a == b)
    p_o = agreements / n

    # Expected agreement by chance
    count1 = Counter(rater1)
    count2 = Counter(rater2)
    p_e = sum((count1[c] / n) * (count2[c] / n) for c in categories)

    if p_e >= 1.0:
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)


def compute_fleiss_kappa(matrix: List[List[int]]) -> float:
    """
    Computes Fleiss' Kappa for inter-rater agreement with fixed number of raters.
    matrix: N x k where matrix[i][j] is count of raters assigning item i to category j.
    """
    if not matrix:
        return 0.0

    N = len(matrix)
    k = len(matrix[0])
    n = sum(matrix[0])  # number of raters per item
    if n <= 1:
        return 1.0

    # Proportion of all assignments to category j
    p_j = [sum(matrix[i][j] for i in range(N)) / (N * n) for j in range(k)]

    # Extent of agreement on the i-th subject
    P_i = []
    for row in matrix:
        sum_sq = sum(nij ** 2 for nij in row)
        P_i.append((sum_sq - n) / (n * (n - 1)))

    p_bar = sum(P_i) / N
    p_e = sum(pj ** 2 for pj in p_j)

    if p_e >= 1.0:
        return 1.0
    return (p_bar - p_e) / (1.0 - p_e)


def compute_span_f1(
    spans_a: List[Tuple[int, int, str]],
    spans_b: List[Tuple[int, int, str]],
    iou_threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Calculates span Precision, Recall, and F1 between reference annotator A and evaluated annotator B.
    Each span is (start, end, label).
    """
    matched_b: Set[int] = set()
    tp = 0

    for sa_start, sa_end, sa_label in spans_a:
        for idx_b, (sb_start, sb_end, sb_label) in enumerate(spans_b):
            if idx_b in matched_b:
                continue
            if sa_label == sb_label:
                iou = compute_span_iou((sa_start, sa_end), (sb_start, sb_end))
                if iou >= iou_threshold:
                    tp += 1
                    matched_b.add(idx_b)
                    break

    fp = len(spans_b) - len(matched_b)
    fn = len(spans_a) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


class IAACalculator:
    """
    Analyzes Label Studio task files with multiple annotations per task.
    """

    def __init__(self, tasks: List[Dict[str, Any]]) -> None:
        self.tasks = tasks

    def extract_annotator_ratings(self) -> Dict[int, Dict[str, Any]]:
        """
        Groups annotations by annotator ID.
        Returns: { annotator_id: { task_id: { "choices": {...}, "spans": [...] } } }
        """
        annotator_data: Dict[int, Dict[str, Any]] = defaultdict(dict)

        for task_idx, task in enumerate(self.tasks):
            task_id = str(task.get("id", task.get("data", {}).get("section_ref", task_idx)))
            annotations = task.get("annotations", [])

            for ann in annotations:
                annotator_id = ann.get("completed_by", 1)
                results = ann.get("result", [])

                spans = []
                choices = {}

                for r in results:
                    r_type = r.get("type")
                    from_name = r.get("from_name")
                    val = r.get("value", {})

                    if r_type == "labels":
                        start = val.get("start", 0)
                        end = val.get("end", 0)
                        labels = val.get("labels", [])
                        for lbl in labels:
                            spans.append((start, end, lbl))

                    elif r_type == "choices":
                        ch = val.get("choices", [])
                        if ch:
                            choices[from_name] = ch[0]

                annotator_data[annotator_id][task_id] = {
                    "spans": spans,
                    "choices": choices,
                }

        return annotator_data

    def evaluate_pairwise(self, annotator_a: int, annotator_b: int) -> Dict[str, Any]:
        """Evaluates pairwise agreement between two annotators."""
        ratings = self.extract_annotator_ratings()
        data_a = ratings.get(annotator_a, {})
        data_b = ratings.get(annotator_b, {})

        common_tasks = sorted(list(set(data_a.keys()) & set(data_b.keys())))
        if not common_tasks:
            return {"error": "No overlapping tasks found between annotators"}

        # 1. Categorical choices alignment
        choice_keys = ["ifc_entity", "property_name", "unit"]
        choice_kappas = {}

        for k in choice_keys:
            labels_a = []
            labels_b = []
            for tid in common_tasks:
                c_a = data_a[tid]["choices"].get(k, "NONE")
                c_b = data_b[tid]["choices"].get(k, "NONE")
                labels_a.append(c_a)
                labels_b.append(c_b)
            choice_kappas[k] = round(compute_cohens_kappa(labels_a, labels_b), 4)

        # 2. Span agreement across all common tasks
        all_spans_a = []
        all_spans_b = []
        for tid in common_tasks:
            all_spans_a.extend(data_a[tid]["spans"])
            all_spans_b.extend(data_b[tid]["spans"])

        span_metrics = compute_span_f1(all_spans_a, all_spans_b, iou_threshold=0.5)

        # By category span metrics
        categories = sorted(list(set(s[2] for s in all_spans_a + all_spans_b)))
        per_category_f1 = {}
        for cat in categories:
            cat_spans_a = [s for s in all_spans_a if s[2] == cat]
            cat_spans_b = [s for s in all_spans_b if s[2] == cat]
            per_category_f1[cat] = compute_span_f1(cat_spans_a, cat_spans_b, iou_threshold=0.5)["f1"]

        return {
            "common_tasks_count": len(common_tasks),
            "categorical_cohens_kappa": choice_kappas,
            "overall_span_metrics": span_metrics,
            "per_category_span_f1": per_category_f1,
        }

    def print_summary_report(self, annotator_pairs: Optional[List[Tuple[int, int]]] = None) -> str:
        """Generates a markdown table report of agreement metrics."""
        ratings = self.extract_annotator_ratings()
        annotator_ids = sorted(list(ratings.keys()))

        if len(annotator_ids) < 2:
            return "Need at least 2 distinct annotators in the export to compute Inter-Annotator Agreement."

        if not annotator_pairs:
            annotator_pairs = [
                (annotator_ids[i], annotator_ids[j])
                for i in range(len(annotator_ids))
                for j in range(i + 1, len(annotator_ids))
            ]

        lines = [
            "# Inter-Annotator Agreement (IAA) Report",
            "",
            f"**Annotators detected**: {annotator_ids}",
            "",
            "## 1. Categorical Choices Agreement (Cohen's Kappa)",
            "",
            "| Pair | Overlap Tasks | ifc_entity $\\kappa$ | property_name $\\kappa$ | unit $\\kappa$ |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]

        all_pair_results = []
        for a, b in annotator_pairs:
            res = self.evaluate_pairwise(a, b)
            all_pair_results.append((a, b, res))
            kappas = res.get("categorical_cohens_kappa", {})
            lines.append(
                f"| Annotator {a} vs {b} | {res['common_tasks_count']} | "
                f"{kappas.get('ifc_entity', 'N/A')} | "
                f"{kappas.get('property_name', 'N/A')} | "
                f"{kappas.get('unit', 'N/A')} |"
            )

        lines.extend([
            "",
            "## 2. Span Extraction Performance (IoU >= 0.5)",
            "",
            "| Pair | Precision | Recall | F1 Score | Total Spans (A / B) |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ])

        for a, b, res in all_pair_results:
            sp = res.get("overall_span_metrics", {})
            lines.append(
                f"| Annotator {a} vs {b} | {sp.get('precision', 0.0)} | "
                f"{sp.get('recall', 0.0)} | **{sp.get('f1', 0.0)}** | "
                f"{sp.get('tp', 0) + sp.get('fn', 0)} / {sp.get('tp', 0) + sp.get('fp', 0)} |"
            )

        return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Inter-Annotator Agreement from Label Studio Exports")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to exported tasks JSON with multiple annotations")
    parser.add_argument("--output", "-o", type=str, help="Optional markdown output report path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    if not isinstance(tasks, list):
        tasks = [tasks]

    calc = IAACalculator(tasks)
    report = calc.print_summary_report()
    print(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
