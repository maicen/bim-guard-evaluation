"""Render the extraction confusion-matrix figure from an e2e confusion.json.

Usage: uv run python eval/plot_extraction_confusion.py eval/results/e2e/run1_browser/confusion.json \
           -o docs/publication/figures/fig_extraction_confusion_run1.png
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _heat(ax, data, rows, cols, title, ylabel, xlabel, fmt=None):
    mx = max(max(r) for r in data) or 1
    ax.imshow(data, cmap="Blues", vmin=0, vmax=mx)
    ax.set_xticks(range(len(cols)), cols)
    ax.set_yticks(range(len(rows)), rows)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    for i, r in enumerate(data):
        for j, v in enumerate(r):
            lab = fmt[i][j] if fmt else str(v)
            ax.text(j, i, lab, ha="center", va="center", fontsize=12,
                    color="white" if v > mx * 0.55 else "black")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("confusion")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    c = json.load(open(a.confusion))
    cl = c["clause_level"]
    m = [[cl["tp"], cl["fn"]], [cl["fp"], cl["tn"]]]
    names = [["TP", "FN"], ["FP", "TN"]]
    fmt = [[f"{names[i][j]}\n{m[i][j]}" for j in range(2)] for i in range(2)]
    ops = [">=", "<=", "==", "between"]
    oc = c["operator_confusion"]
    om = [[oc.get(h, {}).get(e, 0) for e in ops] for h in ops]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1, 1.25]})
    _heat(a1, m, ["Rule", "No rule"], ["Rule", "No rule"],
          "(a) Clause level (OBC 9.8, 117 clauses)", "Human gold", "BIM-Guard extraction", fmt)
    _heat(a2, om, ops, ops, "(b) Operator agreement\n(pairs matching on clause and value)",
          "Human operator", "Extracted operator")
    fig.suptitle("Rule extraction vs. human gold set - TP/FP/FN/TN", fontsize=12)
    fig.tight_layout()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=300)


if __name__ == "__main__":
    main()
