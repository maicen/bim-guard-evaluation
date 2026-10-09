"""Two-card results summary: Pillar A (rule extraction) beside Pillar B (architectural audit).

Pillar A reads the per-run counts of the door and window rule-sheet extractions
(eval/fixtures/mvp_pdf_extraction_runs.json, from eval/score_mvp_pdf_extraction.py).
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


def draw_extraction(ax, d: dict, x0: float, x1: float, y0: float, y1: float) -> None:
    _card(ax, x0, x1, y0, y1, NAVY, NAVY)
    runs, gold = d["runs"], d["gold_rules"]
    sheets = list(dict.fromkeys(r["sheet"] for r in runs))
    x = x0 + 40
    ax.text(x, y0 + 55, "Pillar A · LLM rule extraction vs the source PDFs", fontsize=19, fontweight="bold",
            color=BLUE_ON_NAVY, va="center")
    ax.text(x, y0 + 97, f"{len(sheets)} structured rule sheets ({', '.join(sheets)}) · {gold} rules each · "
            f"{len(runs) // len(sheets)} runs per sheet in the live app", fontsize=12.5, style="italic", color=PALE,
            va="center")

    ax.text(x, y0 + 142, f"Did the LLM find the {gold} rules of each sheet?", fontsize=13.5, fontweight="bold",
            color=WHITE, va="center")
    gx, gy, cw, ch, gap = x + 112, y0 + 192, 98, 38, 5
    rows = (("TP · found", lambda r: r["correct"], True), ("FN · missed", lambda r: r["missed"], False),
            ("FP · invented", lambda r: r["drafts"] - r.get("duplicates", 0) - r["correct"], False))
    for j, run in enumerate(runs):
        cx = gx + j * (cw + gap) + (10 if run["sheet"] != sheets[0] else 0)
        ax.text(cx + cw / 2, gy - 18, run["label"], fontsize=11.5, color=PALE, ha="center", va="center")
        for i, (_, count, on) in enumerate(rows):
            ax.add_patch(FancyBboxPatch((cx, gy + i * (ch + gap)), cw, ch, boxstyle="round,pad=0,rounding_size=6",
                                        facecolor=BLUE if on else "#16213a", edgecolor="none"))
            ax.text(cx + cw / 2, gy + i * (ch + gap) + ch / 2, str(count(run)), fontsize=15, fontweight="bold",
                    color=WHITE if on else PALE, ha="center", va="center")
    for i, (label, _, _) in enumerate(rows):
        ax.text(gx - 10, gy + i * (ch + gap) + ch / 2, label, fontsize=11.5, color=PALE, ha="right", va="center")

    found = sum(r["correct"] for r in runs)
    ax.text(x, y0 + 362, f"Was the drafted rule itself right? ({found} rules found, all runs)", fontsize=13.5,
            fontweight="bold", color=WHITE, va="center")
    left, length = x + 205, 370
    bars = [(label, sum(r["fields_right"][key] for r in runs))
            for label, key in (("IFC class", "target"), ("Property name", "property"), ("Operator", "operator"),
                               ("Value", "value"), ("Unit", "unit"))]
    bars.append(("Every field", sum(r["all_fields_right"] for r in runs)))
    for i, (label, right) in enumerate(bars):
        y = y0 + 396 + 28 * i
        ax.text(x, y, label, fontsize=12, color=PALE, va="center")
        ax.add_patch(Rectangle((left, y - 9), length, 18, facecolor=ORANGE, edgecolor="none"))
        ax.add_patch(Rectangle((left, y - 9), length * right / found, 18, facecolor=BLUE_ON_NAVY, edgecolor="none"))
        ax.text(left + length + 14, y, f"{right} right · {found - right} wrong", fontsize=12, color=WHITE, va="center")

    per_sheet = "; ".join(f"{s} sheet " + " / ".join(str(r["correct"]) for r in runs if r["sheet"] == s) for s in sheets)
    _lead(ax, x, y0 + 578, "Recall is the weak point:", f"found per run, {per_sheet}", WHITE, size=13.5)
    _lead(ax, x, y0 + 614, "Review stays mandatory:", "one run of six found every rule and invented none", WHITE,
          size=13.5)


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
    ap.add_argument("--extraction", type=Path, default=EVAL_DIR / "fixtures" / "mvp_pdf_extraction_runs.json",
                    help="per-run extraction counts")
    ap.add_argument("--title", default="Extraction recall is unstable, so review is mandatory; audit verdicts confirmed")
    ap.add_argument("-o", "--out", type=Path,
                    default=EVAL_DIR.parent / "docs" / "publication" / "figures" / "fig_pillars_summary.png")
    a = ap.parse_args()

    extraction = json.loads(a.extraction.read_text(encoding="utf-8"))
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
        print(f"{run['label']:10s} found {run['correct']:>2}  missed {run['missed']:>2}  drafts {run['drafts']}")
    cm = matrix["confusion_matrix"]
    print(f"audit      TP {cm['tp']}  FN {cm['fn']}  FP {cm['fp']}  TN {cm['tn']}")
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
