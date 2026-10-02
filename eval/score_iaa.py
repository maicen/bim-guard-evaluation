"""
eval/score_iaa.py
---------------------------------------------
Inter-Annotator Agreement (IAA) calculation for building code regulatory NLP annotations.
Computes:
1. Span-level agreement (Precision, Recall, F1 with IoU threshold: 0.50 and 0.75) with bootstrap 95% CIs.
2. Cohen's Kappa (pairwise across annotators for categorical tags: deontics, IFC targets, units) with bootstrap 95% CIs.
3. Fleiss' Kappa (multi-rater categorical agreement across all annotators) with bootstrap 95% CIs.
Outputs formatted markdown tables suitable for publication (Tables 1-7 in research validation)
and machine-readable JSON telemetry with cryptographic provenance.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from eval.env_snapshot import get_environment_snapshot
from eval.stats_util import bootstrap_ci, format_ci


def compute_span_iou(span_a: tuple[int, int], span_b: tuple[int, int]) -> float:
    """Computes Intersection over Union (IoU) of two character spans [start, end]."""
    start_a, end_a = span_a
    start_b, end_b = span_b

    inter_start = max(start_a, start_b)
    inter_end = min(end_a, end_b)
    intersection = max(0, inter_end - inter_start)

    union = max(end_a, end_b) - min(start_a, start_b)
    return intersection / union if union > 0 else 0.0


def compute_cohens_kappa(rater1: list[str], rater2: list[str]) -> float:
    """Computes Cohen's Kappa between two raters over aligned categorical items."""
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


def compute_fleiss_kappa(matrix: list[list[int]]) -> float:
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
    if abs(1.0 - p_e) < 1e-9:
        return 1.0
    return (p_bar - p_e) / (1.0 - p_e)


def compute_span_f1(
    spans_a: list[tuple[int, int, str]],
    spans_b: list[tuple[int, int, str]],
    iou_threshold: float = 0.5,
) -> dict[str, float]:
    """
    Calculates span Precision, Recall, and F1 between reference annotator A and evaluated annotator B.
    Each span is (start, end, label).
    """
    matched_b: set[int] = set()
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
    Analyzes multi-annotator datasets, calculating Cohen's Kappa, Fleiss' Kappa,
    and Span-IoU F1 with bootstrap confidence intervals.
    """

    def __init__(self, tasks: list[dict[str, Any]]) -> None:
        self.tasks = tasks

    def extract_annotator_ratings(self) -> dict[int, dict[str, Any]]:
        """
        Groups annotations by annotator ID.
        Returns: { annotator_id: { task_id: { "choices": {...}, "spans": [...] } } }
        """
        annotator_data: dict[int, dict[str, Any]] = defaultdict(dict)

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

                    elif r_type == "choices" and "start" not in val:
                        # Per-region choices (e.g. dim_property) carry span offsets and
                        # describe one span, not the task; keep them out of task choices.
                        ch = val.get("choices", [])
                        if ch:
                            choices[from_name] = ch[0]

                annotator_data[annotator_id][task_id] = {
                    "spans": spans,
                    "choices": choices,
                }

        return annotator_data

    def evaluate_pairwise(self, annotator_a: int, annotator_b: int) -> dict[str, Any]:
        """Evaluates pairwise agreement between two annotators with bootstrap CIs."""
        ratings = self.extract_annotator_ratings()
        data_a = ratings.get(annotator_a, {})
        data_b = ratings.get(annotator_b, {})

        common_tasks = sorted(list(set(data_a.keys()) & set(data_b.keys())))
        if not common_tasks:
            return {"error": "No overlapping tasks found between annotators"}

        # 1. Categorical choices alignment
        choice_keys = ["ifc_entity", "property_name", "unit", "deontic_strength"]
        choice_kappas = {}
        choice_cis = {}

        for k in choice_keys:
            labels_a = []
            labels_b = []
            for tid in common_tasks:
                c_a = data_a[tid]["choices"].get(k, "NONE")
                c_b = data_b[tid]["choices"].get(k, "NONE")
                labels_a.append(c_a)
                labels_b.append(c_b)

            paired = list(zip(labels_a, labels_b))
            if any(la != "NONE" or lb != "NONE" for la, lb in paired):
                pt, lo, hi = bootstrap_ci(
                    paired,
                    lambda sample: compute_cohens_kappa([x[0] for x in sample], [x[1] for x in sample]),
                    n_resamples=500,
                    seed=42,
                )
                choice_kappas[k] = pt
                choice_cis[k] = {"ci_95": [lo, hi], "formatted": format_ci(pt, lo, hi, as_percent=False)}

        # 2. Span agreement across all common tasks
        all_spans_a = []
        all_spans_b = []
        for tid in common_tasks:
            all_spans_a.extend(data_a[tid]["spans"])
            all_spans_b.extend(data_b[tid]["spans"])

        span_metrics_50 = compute_span_f1(all_spans_a, all_spans_b, iou_threshold=0.5)
        span_metrics_75 = compute_span_f1(all_spans_a, all_spans_b, iou_threshold=0.75)

        # Bootstrap CI for span F1 across tasks
        task_f1_items = []
        for tid in common_tasks:
            sp_a = data_a[tid]["spans"]
            sp_b = data_b[tid]["spans"]
            task_f1_items.append((sp_a, sp_b))

        def _task_sample_f1(sample, threshold=0.5):
            merged_a = []
            merged_b = []
            for sa, sb in sample:
                merged_a.extend(sa)
                merged_b.extend(sb)
            return compute_span_f1(merged_a, merged_b, iou_threshold=threshold)["f1"]

        pt_f1_50, lo_f1_50, hi_f1_50 = bootstrap_ci(
            task_f1_items,
            lambda s: _task_sample_f1(s, 0.5),
            n_resamples=500,
            seed=42,
        )
        pt_f1_75, lo_f1_75, hi_f1_75 = bootstrap_ci(
            task_f1_items,
            lambda s: _task_sample_f1(s, 0.75),
            n_resamples=500,
            seed=42,
        )

        span_metrics_50["ci_95"] = [lo_f1_50, hi_f1_50]
        span_metrics_50["formatted_ci"] = format_ci(pt_f1_50, lo_f1_50, hi_f1_50, as_percent=False)
        span_metrics_75["ci_95"] = [lo_f1_75, hi_f1_75]
        span_metrics_75["formatted_ci"] = format_ci(pt_f1_75, lo_f1_75, hi_f1_75, as_percent=False)

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
            "categorical_cohens_kappa_cis": choice_cis,
            "overall_span_metrics": span_metrics_50,
            "overall_span_metrics_iou_05": span_metrics_50,
            "overall_span_metrics_iou_075": span_metrics_75,
            "per_category_span_f1": per_category_f1,
        }

    def compute_multi_rater_fleiss(self, annotator_ids: list[int]) -> dict[str, Any]:
        """Computes Fleiss' Kappa across all specified annotators for categorical fields."""
        ratings = self.extract_annotator_ratings()
        # Find tasks annotated by ALL specified annotators
        common_tasks = set(ratings[annotator_ids[0]].keys())
        for aid in annotator_ids[1:]:
            common_tasks &= set(ratings[aid].keys())

        common_tasks = sorted(list(common_tasks))
        if not common_tasks:
            return {}

        fleiss_results = {}
        choice_keys = ["ifc_entity", "property_name", "unit", "deontic_strength"]

        for key in choice_keys:
            # Build matrix: N (tasks) x k (unique categories)
            all_labels = set()
            for tid in common_tasks:
                for aid in annotator_ids:
                    all_labels.add(ratings[aid][tid]["choices"].get(key, "NONE"))

            cat_list = sorted(list(all_labels))
            cat_to_idx = {c: i for i, c in enumerate(cat_list)}

            matrix = []
            for tid in common_tasks:
                row = [0] * len(cat_list)
                for aid in annotator_ids:
                    c = ratings[aid][tid]["choices"].get(key, "NONE")
                    row[cat_to_idx[c]] += 1
                matrix.append(row)

            if len(cat_list) > 1:
                pt, lo, hi = bootstrap_ci(
                    matrix,
                    compute_fleiss_kappa,
                    n_resamples=500,
                    seed=42,
                )
                fleiss_results[key] = {
                    "kappa": pt,
                    "ci_95": [lo, hi],
                    "formatted": format_ci(pt, lo, hi, as_percent=False),
                }

        return fleiss_results

    def generate_full_results(self) -> dict[str, Any]:
        """Produces a comprehensive results dictionary including provenance."""
        ratings = self.extract_annotator_ratings()
        annotator_ids = sorted(list(ratings.keys()))

        annotator_pairs = [
            (annotator_ids[i], annotator_ids[j])
            for i in range(len(annotator_ids))
            for j in range(i + 1, len(annotator_ids))
        ]

        pairwise = {}
        for a, b in annotator_pairs:
            pair_key = f"{a}_vs_{b}"
            pairwise[pair_key] = self.evaluate_pairwise(a, b)

        fleiss = self.compute_multi_rater_fleiss(annotator_ids) if len(annotator_ids) >= 2 else {}

        return {
            "total_tasks": len(self.tasks),
            "annotators": annotator_ids,
            "pairwise_evaluations": pairwise,
            "multi_rater_fleiss_kappa": fleiss,
            "provenance": get_environment_snapshot(),
        }

    def print_summary_report(self) -> str:
        """Generates a publication-grade markdown table report of agreement metrics."""
        ratings = self.extract_annotator_ratings()
        annotator_ids = sorted(list(ratings.keys()))

        if len(annotator_ids) < 2:
            return "Need at least 2 distinct annotators in the export to compute Inter-Annotator Agreement."

        results = self.generate_full_results()
        pairwise = results["pairwise_evaluations"]
        fleiss = results["multi_rater_fleiss_kappa"]

        lines = [
            "# Inter-Annotator Agreement (IAA) Report",
            "",
            f"**Total Tasks Evaluated**: {len(self.tasks)}  ",
            f"**Annotators Evaluated**: {annotator_ids} (1: Arch Specialist, 2: Computational BIM Specialist, 3: Adjudicator)  ",
            "",
            "## 1. Categorical Agreement (Cohen's $\\kappa$ with 95% Bootstrap CIs)",
            "",
            "| Pair | Tasks | IFC Entity $\\kappa$ [95% CI] | Property Name $\\kappa$ [95% CI] | Deontic Strength $\\kappa$ [95% CI] | Unit $\\kappa$ [95% CI] |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]

        for pair_key, res in pairwise.items():
            pair_label = pair_key.replace("_vs_", " vs ")
            k_cis = res.get("categorical_cohens_kappa_cis", {})
            ifc_fmt = k_cis.get("ifc_entity", {}).get("formatted", "N/A")
            prop_fmt = k_cis.get("property_name", {}).get("formatted", "N/A")
            deon_fmt = k_cis.get("deontic_strength", {}).get("formatted", "N/A")
            unit_fmt = k_cis.get("unit", {}).get("formatted", "N/A")

            lines.append(
                f"| Annotator {pair_label} | {res['common_tasks_count']} | {ifc_fmt} | {prop_fmt} | {deon_fmt} | {unit_fmt} |"
            )

        if fleiss:
            lines.extend([
                "",
                "## 2. Multi-Rater Fleiss' $\\kappa$ (All Evaluators)",
                "",
                "| Attribute Category | Fleiss' $\\kappa$ Point Estimate | 95% Bootstrap Confidence Interval |",
                "| :--- | :---: | :---: |",
            ])
            for cat, data in fleiss.items():
                lines.append(f"| `{cat}` | {data['kappa']:.4f} | [{data['ci_95'][0]:.4f}, {data['ci_95'][1]:.4f}] |")

        lines.extend([
            "",
            "## 3. Regulatory Span Extraction Agreement (IoU $\\ge$ 0.50 & 0.75)",
            "",
            "| Pair | Precision (0.50) | Recall (0.50) | **F1 (IoU $\\ge$ 0.50) [95% CI]** | **F1 (IoU $\\ge$ 0.75) [95% CI]** |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ])

        for pair_key, res in pairwise.items():
            pair_label = pair_key.replace("_vs_", " vs ")
            sp50 = res.get("overall_span_metrics_iou_05", {})
            sp75 = res.get("overall_span_metrics_iou_075", {})
            lines.append(
                f"| Annotator {pair_label} | {sp50.get('precision', 0.0):.4f} | {sp50.get('recall', 0.0):.4f} | "
                f"**{sp50.get('formatted_ci', 'N/A')}** | **{sp75.get('formatted_ci', 'N/A')}** |"
            )

        return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Inter-Annotator Agreement from Label Studio Exports")
    parser.add_argument("--input", "-i", type=str, help="Path to exported tasks JSON with multiple annotations")
    parser.add_argument("--output", "-o", type=str, help="Optional output report path (markdown or json)")
    parser.add_argument("--json", action="store_true", help="Output full structured JSON telemetry")
    args = parser.parse_args()

    # Determine input path: explicit -> dual_annotator_corpus -> sample_tasks
    if args.input:
        input_path = Path(args.input)
    else:
        root_dir = Path(__file__).resolve().parent.parent
        default_dual = root_dir / "research" / "annotations" / "dual_annotator_corpus.json"
        default_sample = root_dir / "research" / "label_studio" / "sample_tasks.json"
        input_path = default_dual if default_dual.exists() else default_sample

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        return 2

    with open(input_path, encoding="utf-8") as f:
        tasks = json.load(f)

    if not isinstance(tasks, list):
        tasks = [tasks]

    import time
    start_t = time.perf_counter()
    calc = IAACalculator(tasks)
    full_data = calc.generate_full_results()
    duration = time.perf_counter() - start_t

    if args.json:
        try:
            from eval.eval_config import build_result, write_result
            res_dict = build_result(
                "score_iaa",
                tier=1,
                passed=len(tasks),
                failed=0,
                total=len(tasks),
                duration_s=duration,
                details=full_data,
            )
            write_result(res_dict)
        except Exception:
            pass

        out_json = json.dumps(full_data, indent=2)
        if args.output:
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(out_json)
        print(out_json)
        return 0

    report = calc.print_summary_report()
    print(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
