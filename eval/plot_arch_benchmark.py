"""Render the architecture-engine benchmark figures from a live benchmark run.

Writes the confusion matrix and the per-check verdict breakdown for the
22 synthetic scenarios in generate_arch_test_models.py.

Usage: uv run python eval/plot_arch_benchmark.py [-o docs/publication/figures]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

INK, MUTED = "#1a1a1a", "#5f6368"
FAIL_COLOR, PASS_COLOR = "#c8553d", "#2166b3"
CHECK_LABELS = {
    "travel_distance": "Travel distance (<= 25 m)",
    "exit_count": "Exits per storey (>= 2)",
    "egress_window": "Egress window (area, size, sill)",
    "daylight_ratio": "Daylight ratio (>= 8%)",
    "fire_separation": "Wall fire rating (>= 45 min)",
}


def draw_confusion(metrics: dict[str, Any], out: Path) -> None:
    """2x2 matrix, rows = synthetic ground truth, columns = engine verdict."""
    cm = metrics["confusion_matrix"]
    counts = [[cm["tp"], cm["fn"]], [cm["fp"], cm["tn"]]]
    names = [["TP", "FN"], ["FP", "TN"]]
    notes = [["violation flagged", "violation missed"], ["false alarm", "compliant passed"]]
    top = max(max(r) for r in counts) or 1

    fig, ax = plt.subplots(figsize=(6.0, 5.0), dpi=300)
    ax.imshow(counts, cmap="Blues", vmin=0, vmax=top * 1.25)
    for i in range(2):
        for j in range(2):
            color = "white" if counts[i][j] > top * 0.5 else INK
            ax.text(j, i - 0.08, f"{names[i][j]} = {counts[i][j]}", ha="center", va="center",
                    fontsize=17, fontweight="bold", color=color)
            ax.text(j, i + 0.2, notes[i][j], ha="center", va="center", fontsize=9, color=color)
    ax.set_xticks([0, 1], ["FAIL\n(violation)", "PASS\n(compliant)"], fontsize=10, color=INK)
    ax.set_yticks([0, 1], [f"Violation\n(n = {cm['actual_positives']})", f"Compliant\n(n = {cm['actual_negatives']})"],
                  fontsize=10, color=INK)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("Engine verdict", fontsize=10, color=MUTED, labelpad=8)
    ax.set_ylabel("Ground truth (set by the scenario generator)", fontsize=10, color=MUTED, labelpad=8)
    ax.tick_params(length=0)
    ax.set_xticks([0.5], minor=True)
    ax.set_yticks([0.5], minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    acc = metrics["accuracy"]
    fig.suptitle(f"Architecture engines on {cm['total']} synthetic scenarios", fontsize=12,
                 fontweight="bold", color=INK, y=0.98)
    fig.text(0.5, 0.03,
             f"Accuracy {acc['point']:.0%} (95% Wilson CI {acc['ci_lower']:.1%} to {acc['ci_upper']:.1%}). "
             "Egress and spatial engines;\ninputs are generated values, not measurements from real models.",
             ha="center", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.09, 1, 0.96))
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def draw_verdicts(results: dict[str, Any], out: Path) -> None:
    """Stacked bars: FAIL and PASS verdicts per check type."""
    by_check = results["by_check_type"]
    checks = list(by_check)[::-1]
    fails = [by_check[c]["tp"] + by_check[c]["fp"] for c in checks]
    passes = [by_check[c]["tn"] + by_check[c]["fn"] for c in checks]
    wrong = sum(by_check[c]["fp"] + by_check[c]["fn"] for c in checks)
    labels = [CHECK_LABELS.get(c, c) for c in checks]

    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=300)
    ax.barh(labels, fails, height=0.55, color=FAIL_COLOR, edgecolor="white", linewidth=2, label="FAIL (violation flagged)")
    ax.barh(labels, passes, left=fails, height=0.55, color=PASS_COLOR, edgecolor="white", linewidth=2, label="PASS (compliant)")
    for y, (f, p) in enumerate(zip(fails, passes)):
        if f:
            ax.text(f / 2, y, str(f), ha="center", va="center", fontsize=10, fontweight="bold", color="white")
        if p:
            ax.text(f + p / 2, y, str(p), ha="center", va="center", fontsize=10, fontweight="bold", color="white")
        ax.text(f + p + 0.12, y, f"n = {f + p}", ha="left", va="center", fontsize=9, color=MUTED)
    ax.set_xlim(0, max(f + p for f, p in zip(fails, passes)) + 1.0)
    ax.set_xlabel("Scenarios", fontsize=10, color=MUTED)
    ax.tick_params(axis="y", length=0, labelsize=10, labelcolor=INK)
    ax.tick_params(axis="x", labelsize=9, labelcolor=MUTED, color="#cccccc")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#cccccc")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False, fontsize=9)
    total = results["total_cases"]
    ax.set_title(f"Engine verdicts by check type, {total} synthetic scenarios\n"
                 f"{total - wrong} of {total} verdicts match the expected outcome",
                 fontsize=11, fontweight="bold", color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out-dir", type=Path, default=EVAL_DIR.parent / "docs" / "publication" / "figures")
    a = ap.parse_args()
    from score_arch_engines import run_benchmark

    results = run_benchmark()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    draw_confusion(results["classification_metrics"], a.out_dir / "fig_1_confusion_matrix_heatmap.png")
    draw_verdicts(results, a.out_dir / "fig_arch_verdict_breakdown.png")
    cm = results["classification_metrics"]["confusion_matrix"]
    print(f"TP {cm['tp']}  FN {cm['fn']}  FP {cm['fp']}  TN {cm['tn']}  -> {a.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
