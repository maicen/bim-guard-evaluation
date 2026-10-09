"""Two-card results summary: Pillar A (rule extraction) beside Pillar B (architectural audit).

Pillar A reads the scored e2e extraction runs 1-3 (eval/results/e2e/*/confusion.json).
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
RUNS = [("run1_browser", "Run 1"), ("run2_playwright", "Run 2"), ("run3_variance_a", "Run 3")]

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


def _matrix(ax, gx, gy, cells, cols, rows, on, off, head, cw=150, ch=92, gap=6):
    """2x2 grid; `on` and `off` are (fill, text colour) for the agreeing and disagreeing cells."""
    for j, label in enumerate(cols):
        ax.text(gx + j * (cw + gap) + cw / 2, gy - 20, label, fontsize=11.5, color=head, ha="center", va="center")
    for i, label in enumerate(rows):
        ax.text(gx - 10, gy + i * (ch + gap) + ch / 2, label, fontsize=11.5, color=head, ha="right", va="center")
        for j, (name, count, note) in enumerate(cells[i]):
            fill, ink = on if i == j else off
            cx, cy = gx + j * (cw + gap), gy + i * (ch + gap)
            ax.add_patch(FancyBboxPatch((cx, cy), cw, ch, boxstyle="round,pad=0,rounding_size=7",
                                        facecolor=fill, edgecolor="none"))
            ax.text(cx + cw / 2, cy + ch * 0.39, f"{name} {count:,}", fontsize=17, fontweight="bold", color=ink,
                    ha="center", va="center")
            ax.text(cx + cw / 2, cy + ch * 0.72, note, fontsize=10.5, color=ink, ha="center", va="center")
    return gx + 2 * cw + gap


def load_extraction() -> list[dict]:
    return [json.loads((E2E / folder / "confusion.json").read_text(encoding="utf-8")) for folder, _ in RUNS]


def draw_extraction(ax, runs: list[dict], x0: float, x1: float, y0: float, y1: float) -> None:
    _card(ax, x0, x1, y0, y1, NAVY, NAVY)
    first = runs[0]
    clause = first["clause_level"]["metrics"]
    cm = clause["confusion_matrix"]
    x = x0 + 40
    ax.text(x, y0 + 55, "Pillar A · LLM rule extraction vs a human gold set", fontsize=19, fontweight="bold",
            color=BLUE_ON_NAVY, va="center")
    ax.text(x, y0 + 97, f"OBC §9.8 · {cm['total']} clauses, {first['human_rules']} gold rules · {len(runs)} runs "
            "through the live app, same model", fontsize=12.5, style="italic", color=PALE, va="center")

    ax.text(x, y0 + 142, "Did the LLM find the clauses that hold a rule? (run 1)", fontsize=13.5,
            fontweight="bold", color=WHITE, va="center")
    cells = [[("TP", cm["tp"], "rule drafted"), ("FN", cm["fn"], "rule missed")],
             [("FP", cm["fp"], "rule invented"), ("TN", cm["tn"], "correctly empty")]]
    gy = y0 + 192
    edge = _matrix(ax, x + 105, gy, cells, ("LLM: rule", "LLM: none"), ("Human: rule", "Human: none"),
                   (BLUE, WHITE), ("#16213a", PALE), PALE, ch=80)
    side = (edge + x1) / 2
    others = " and ".join(str(r["clause_level"]["tp"] + r["clause_level"]["tn"]) for r in runs[1:])
    ax.text(side, gy + 50, f"{cm['tp'] + cm['tn']} / {cm['total']}", fontsize=22, fontweight="bold",
            color=BLUE_ON_NAVY, ha="center", va="center")
    for dy, line in ((100, "clauses classified correctly"),
                     (124, f"95% CI {clause['accuracy']['ci_lower']:.1%}–{clause['accuracy']['ci_upper']:.1%}"),
                     (148, f"runs 2 and 3: {others}")):
        ax.text(side, gy + dy, line, fontsize=11.5, color=PALE, ha="center", va="center")

    drafted = first["extracted_rules"]
    ax.text(x, y0 + 408, f"Was the drafted rule itself right? ({drafted} dimensional rules, run 1)", fontsize=13.5,
            fontweight="bold", color=WHITE, va="center")
    left, length = x + 285, 300
    for i, (label, mode) in enumerate((("Operator and value", "lenient"),
                                       ("+ IFC class and property (synonyms)", "normalized"),
                                       ("+ exact IFC names", "strict"))):
        right = first["rule_level"][mode]["tp"]
        y = y0 + 446 + 36 * i
        ax.text(x, y, label, fontsize=12, color=PALE, va="center")
        ax.add_patch(Rectangle((left, y - 11), length, 22, facecolor=ORANGE, edgecolor="none"))
        ax.add_patch(Rectangle((left, y - 11), length * right / drafted, 22, facecolor=BLUE_ON_NAVY, edgecolor="none"))
        ax.text(left + length + 14, y, f"{right} right · {drafted - right} wrong", fontsize=12, color=WHITE, va="center")

    found = " / ".join(str(r["rule_level"]["lenient"]["tp"]) for r in runs)
    _lead(ax, x, y0 + 572, "Recall is the weak point:", f"gold rules found per run {found} of {first['human_rules']}", WHITE)
    _lead(ax, x, y0 + 610, "Door and window packs:", "hand-written seed rules, nothing to extract", WHITE)


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

    gy = y0 + 185
    cells = [[("TP", cm["tp"], "violation flagged"), ("FN", cm["fn"], "violation missed")],
             [("FP", cm["fp"], "false alarm"), ("TN", cm["tn"], "compliant passed")]]
    edge = _matrix(ax, x + 108, gy, cells, ("Engine: FAIL", "Engine: PASS"), ("Expert: FAIL", "Expert: PASS"),
                   (BLUE, WHITE), (CELL_OFF, MUTED), MUTED)

    side_x = (edge + x1) / 2
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

    for name, cm in (("extraction, run 1 clauses", extraction[0]["clause_level"]), ("audit", matrix["confusion_matrix"])):
        print(f"{name:26s} TP {cm['tp']}  FN {cm['fn']}  FP {cm['fp']}  TN {cm['tn']}")
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
