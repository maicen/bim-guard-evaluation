"""Pillar A card: precision and recall of rule extraction over repeated runs.

Reads a small JSON of per-run counts and derives the percentages, so the card
cannot show a rate that the counts do not support:

    {"subtitle": "Door and window rule sheets, 40 rules, 3 runs through the live app",
     "gold_rules": 40,
     "runs": [{"label": "Run 1", "drafts": 0, "duplicates": 0, "correct": 0}, ...],
     "notes": [["Bold lead-in:", "rest of the line"], ...]}

precision = correct / (drafts - duplicates), recall = correct / gold_rules. duplicates
(drafts restating a rule already counted) are optional and count neither way.

Usage: uv run python eval/plot_extraction_runs_card.py runs.json -o docs/publication/figures/fig_pillar_a_runs.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

NAVY, PAGE, WHITE, PALE = "#020a1c", "#f0f3f9", "#ffffff", "#d5dbe6"
BLUE, ORANGE = "#3b8bea", "#d95a26"
W, H = 1000, 750
plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


def _lead(ax, x, y, bold, rest):
    head = ax.text(x, y, bold, fontsize=15.5, fontweight="bold", color=WHITE, va="center")
    box = head.get_window_extent(ax.figure.canvas.get_renderer())
    end = ax.transData.inverted().transform((box.x1, box.y0))[0]
    ax.text(end + 8, y, rest, fontsize=15.5, color=PALE, va="center")


def draw(d: dict, out: Path) -> None:
    runs, gold = d["runs"], d["gold_rules"]
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=240)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((22, 6), W - 28, H - 12, boxstyle="round,pad=0,rounding_size=40",
                                facecolor=NAVY, edgecolor="none"))
    x = 70
    ax.text(x, 66, d.get("title", "Pillar A · Rule extraction vs the source rule sheets"), fontsize=21,
            fontweight="bold", color="#4a9bff", va="center")
    for i, line in enumerate(d["subtitle"].split("\n")):
        ax.text(x, 120 + 30 * i, line, fontsize=14, style="italic", color=PALE, va="center")

    for dx, color, name in ((-95, BLUE, "Precision"), (30, ORANGE, "Recall")):
        ax.add_patch(Rectangle((W / 2 + dx, 203), 12, 12, facecolor=color, edgecolor="none"))
        ax.text(W / 2 + dx + 18, 210, name, fontsize=13, color=WHITE, va="center")

    base, full = 458, 180
    bar = min(110, 0.38 * (W - 140) / len(runs))
    wide = bar > 80
    step = (W - 140) / len(runs)
    for i, run in enumerate(runs):
        centre = 85 + step * (i + 0.5)
        distinct = run["drafts"] - run.get("duplicates", 0)
        precision = run["correct"] / distinct if distinct else 0.0
        for left, value, color in ((centre - bar, precision, BLUE), (centre, run["correct"] / gold, ORANGE)):
            ax.add_patch(Rectangle((left, base - full * value), bar, full * value, facecolor=color, edgecolor="none"))
            ax.text(left + bar / 2, base - full * value - 18, f"{value:.1%}" if wide else f"{value:.0%}", fontsize=14 if wide else 11.5, color=WHITE,
                    ha="center", va="center")
        ax.text(centre, base + 30, run["label"], fontsize=13.5, color=PALE, ha="center", va="center")

    found = " / ".join(str(r["correct"]) for r in runs)
    wrong = " / ".join(str(r["drafts"] - r.get("duplicates", 0) - r["correct"]) for r in runs)
    notes = [["Rules found:", f"{found} of {gold} per run"],
             ["Drafts matching no rule:", f"{wrong} per run"], *d.get("notes", [])]
    for i, (bold, rest) in enumerate(notes):
        _lead(ax, x, 548 + 44 * i, bold, rest)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=PAGE)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", type=Path, help="JSON of per-run counts (see module docstring)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    a = ap.parse_args()
    d = json.loads(a.runs.read_text(encoding="utf-8"))
    for run in d["runs"]:
        if not 0 <= run["correct"] <= min(run["drafts"] - run.get("duplicates", 0), d["gold_rules"]):
            sys.exit(f"{run['label']}: correct must be between 0 and min(drafts - duplicates, gold_rules)")
    draw(d, a.out)
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
