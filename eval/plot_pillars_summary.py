"""Two-card results summary: Pillar A (rule extraction) beside Pillar B (architectural audit).

Pillar A reads the scored e2e extraction runs (eval/results/e2e/*/confusion.json).
Pillar B reads a tool-vs-expert matrix from BIM-Guard's Evaluation page: either a
saved GET /api/evaluation/matrix response or the transcribed fixture used by default.

Usage: uv run python eval/plot_pillars_summary.py [-o docs/publication/figures/fig_pillars_summary.png]
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

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from stats_util import confusion_matrix_metrics  # noqa: E402

E2E = EVAL_DIR / "results" / "e2e"
RUNS = [("run1_browser", "Run 1"), ("run2_playwright", "Run 2"), ("run3_variance_a", "Run 3 (after app rebuild)")]
REVISED_GOLD_RUN = "run4_corrected_gold"

PAGE, NAVY, WHITE = "#f0f3f9", "#020a1c", "#ffffff"
INK, MUTED, PALE = "#101828", "#5f6368", "#d5dbe6"
BLUE, BLUE_ON_NAVY, ORANGE, CELL_OFF = "#1565d8", "#4a9bff", "#d95a26", "#eef0f5"
W, H = 1600, 830
plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


def _card(ax, x0, x1, y0, y1, fill, edge):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=38",
                                facecolor=fill, edgecolor=edge, linewidth=1.2))


def _lead(ax, x, y, bold, rest, color, size=14.5):
    """One line with a bold lead-in followed by regular text."""
    head = ax.text(x, y, bold, fontsize=size, fontweight="bold", color=color, va="center")
    box = head.get_window_extent(ax.figure.canvas.get_renderer())
    end = ax.transData.inverted().transform((box.x1, box.y0))[0]
    ax.text(end + 7, y, rest, fontsize=size, color=color, va="center")


def load_extraction() -> dict:
    runs = []
    for folder, label in RUNS:
        c = json.loads((E2E / folder / "confusion.json").read_text(encoding="utf-8"))
        runs.append({"label": label, "c": c})
    first = runs[0]["c"]
    ops = first["operator_confusion"]
    revised = json.loads((E2E / REVISED_GOLD_RUN / "confusion.json").read_text(encoding="utf-8"))
    return {
        "runs": runs,
        "clauses": first["clause_level"]["metrics"]["confusion_matrix"]["total"],
        "gold_rules": first["human_rules"],
        "op_right": sum(n for human, row in ops.items() for got, n in row.items() if got == human),
        "op_total": sum(n for row in ops.values() for n in row.values()),
        "revised": revised,
    }


def draw_extraction(ax, d: dict, x0: float, x1: float, y0: float, y1: float) -> None:
    _card(ax, x0, x1, y0, y1, NAVY, NAVY)
    x = x0 + 40
    ax.text(x, y0 + 55, "Pillar A · Rule extraction vs a human gold set", fontsize=19, fontweight="bold",
            color=BLUE_ON_NAVY, va="center")
    ax.text(x, y0 + 97, f"OBC §9.8 · {d['clauses']} clauses, {d['gold_rules']} rules · {len(d['runs'])} runs "
            "through the live app, same model", fontsize=12.5, style="italic", color=PALE, va="center")
    ax.text(x, y0 + 123, "Door and window packs are hand-written seed rules, so they have no clause to extract",
            fontsize=12.5, style="italic", color=PALE, va="center")

    mid = (x0 + x1) / 2
    for dx, color, name in ((-95, BLUE_ON_NAVY, "Precision"), (25, ORANGE, "Recall")):
        ax.add_patch(Rectangle((mid + dx, y0 + 160), 11, 11, facecolor=color, edgecolor="none"))
        ax.text(mid + dx + 17, y0 + 166, name, fontsize=11.5, color=WHITE, va="center")

    base, full, bar = y0 + 395, 190, 92
    step = (x1 - x0 - 110) / len(d["runs"])
    for i, run in enumerate(d["runs"]):
        centre = x0 + 55 + step * (i + 0.5)
        lenient = run["c"]["rule_level"]["lenient"]
        for left, value, color in ((centre - bar, lenient["precision"], BLUE_ON_NAVY), (centre, lenient["recall"], ORANGE)):
            ax.add_patch(Rectangle((left, base - full * value), bar, full * value, facecolor=color, edgecolor="none"))
            ax.text(left + bar / 2, base - full * value - 14, f"{value:.1%}", fontsize=12, color=WHITE,
                    ha="center", va="center")
        ax.text(centre, base + 26, run["label"], fontsize=12, color=PALE, ha="center", va="center")

    first = d["runs"][0]["c"]["rule_level"]
    false_alarms = " / ".join(str(r["c"]["clause_level"]["fp"]) for r in d["runs"])
    late = d["revised"]["rule_level"]["lenient"]
    lines = [
        ("Misses, not inventions:", f"false-positive clauses per run {false_alarms}"),
        ("Operator almost always right:", f"{d['op_right']} of {d['op_total']} matched rules (run 1)"),
        ("Naming is the weak point:", f"exact IFC names cut precision {first['lenient']['precision']:.0%} → "
                                      f"{first['strict']['precision']:.0%} (run 1)"),
        ("Run 4, revised gold:", f"precision {late['precision']:.1%}, recall {late['recall']:.1%} "
                                 f"on {d['revised']['human_rules']} rules"),
    ]
    for i, (bold, rest) in enumerate(lines):
        _lead(ax, x, y0 + 472 + 38 * i, bold, rest, WHITE)


def draw_audit(ax, m: dict, x0: float, x1: float, y0: float, y1: float) -> None:
    _card(ax, x0, x1, y0, y1, WHITE, "#dfe4ee")
    cm = m["confusion_matrix"]
    binary = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    right = cm["tp"] + cm["tn"]
    acc = confusion_matrix_metrics(cm["tp"], cm["fp"], cm["fn"], cm["tn"], confidence=0.95)["accuracy"]
    agreed = m.get("agreed")
    if agreed is None:  # a raw API response carries the cross-tabulation instead
        same = {"MISSING": "INDETERMINATE", "WAIVED": "NOT_APPLICABLE"}
        agreed = sum(n for tool, row in m["cross_tabulation"].items() for human, n in row.items()
                     if same.get(tool, tool) == human)

    x = x0 + 40
    ax.text(x, y0 + 55, "Pillar B · Architectural audit", fontsize=19, fontweight="bold", color=BLUE, va="center")
    rules = f", {m['rules']} rules" if m.get("rules") else ""
    ax.text(x, y0 + 100, f"Live audit · door and window rule packs{rules}", fontsize=13.5, fontweight="bold",
            color=INK, va="center")
    model = f"Model {m['model']} · " if m.get("model") else ""
    ax.text(x, y0 + 126, f"{model}engine verdict vs expert review", fontsize=11.5, color=MUTED, va="center")

    cw, ch, gap = 150, 92, 6
    gx, gy = x + 108, y0 + 185
    cells = [[("TP", cm["tp"], "violation flagged"), ("FN", cm["fn"], "violation missed")],
             [("FP", cm["fp"], "false alarm"), ("TN", cm["tn"], "compliant passed")]]
    for j, head in enumerate(("Engine: FAIL", "Engine: PASS")):
        ax.text(gx + j * (cw + gap) + cw / 2, gy - 20, head, fontsize=11.5, color=MUTED, ha="center", va="center")
    for i, side in enumerate(("Expert: FAIL", "Expert: PASS")):
        ax.text(gx - 10, gy + i * (ch + gap) + ch / 2, side, fontsize=11.5, color=MUTED, ha="right", va="center")
        for j, (name, count, note) in enumerate(cells[i]):
            on = i == j
            cx, cy = gx + j * (cw + gap), gy + i * (ch + gap)
            ax.add_patch(FancyBboxPatch((cx, cy), cw, ch, boxstyle="round,pad=0,rounding_size=7",
                                        facecolor=BLUE if on else CELL_OFF, edgecolor="none"))
            ax.text(cx + cw / 2, cy + 36, f"{name} {count:,}", fontsize=17, fontweight="bold",
                    color=WHITE if on else MUTED, ha="center", va="center")
            ax.text(cx + cw / 2, cy + 66, note, fontsize=10.5, color=WHITE if on else MUTED, ha="center", va="center")

    side_x = (gx + 2 * cw + gap + x1) / 2
    ax.text(side_x, gy + 62, f"{right:,} / {binary:,}", fontsize=22, fontweight="bold", color=BLUE,
            ha="center", va="center")
    ax.text(side_x, gy + 118, "PASS/FAIL verdicts agree", fontsize=11.5, color=MUTED, ha="center", va="center")
    ax.text(side_x, gy + 143, f"95% CI {acc['ci_lower']:.1%}–{acc['ci_upper']:.0%}", fontsize=11.5, color=MUTED,
            ha="center", va="center")

    by = y0 + 438
    ax.text(x, by, "All captured findings · every rule × element check", fontsize=13.5, fontweight="bold",
            color=INK, va="center")
    ax.text(x, by + 66, f"{agreed:,} / {m['reviewed_findings']:,}", fontsize=30, fontweight="bold", color=BLUE,
            va="center")
    kappa = m.get("metrics", {}).get("cohens_kappa")
    notes = [f"match the expert verdict{f' (κ = {kappa:.2f})' if kappa is not None else ''}.",
             f"{m['reviewed_findings'] - binary:,} are not plain PASS/FAIL checks",
             "and sit outside the matrix above."]
    for i, line in enumerate(notes):
        ax.text(x + 330, by + 40 + 27 * i, line, fontsize=12.5, color=INK, va="center")
    ax.text(x, y1 - 58, "Reference is the expert verdict recorded in the Evaluation tab,", fontsize=10.5,
            style="italic", color=MUTED, va="center")
    ax.text(x, y1 - 37, "not an independent reading of the raw IFC file.", fontsize=10.5, style="italic",
            color=MUTED, va="center")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", type=Path, default=EVAL_DIR / "fixtures" / "evaluation_matrix_res_mrc_2026-10-08.json",
                    help="tool-vs-expert matrix JSON (GET /api/evaluation/matrix shape)")
    ap.add_argument("--title", default="Extraction recall is unstable, so review is mandatory; audit verdicts confirmed")
    ap.add_argument("-o", "--out", type=Path,
                    default=EVAL_DIR.parent / "docs" / "publication" / "figures" / "fig_pillars_summary.png")
    a = ap.parse_args()

    extraction = load_extraction()
    matrix = json.loads(a.matrix.read_text(encoding="utf-8"))

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=240)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    ax.text(14, 52, a.title, fontsize=27, fontweight="bold", color=INK, va="center")
    draw_extraction(ax, extraction, 12, 832, 150, 800)
    draw_audit(ax, matrix, 872, 1588, 150, 800)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, facecolor=PAGE)
    plt.close(fig)

    for run in extraction["runs"]:
        lenient = run["c"]["rule_level"]["lenient"]
        print(f"{run['label']:28s} precision {lenient['precision']:.1%}  recall {lenient['recall']:.1%}")
    cm = matrix["confusion_matrix"]
    print(f"TP {cm['tp']}  FN {cm['fn']}  FP {cm['fp']}  TN {cm['tn']}")
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
