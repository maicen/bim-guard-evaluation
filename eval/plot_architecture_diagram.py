"""Draw the BIM-Guard pipeline diagram (memo Section 3.0) as a figure.

Usage: uv run python eval/plot_architecture_diagram.py [-o docs/publication/figures/fig_architecture_pipeline.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

INK, MUTED = "#1a1a1a", "#5f6368"
STYLES = {  # kind -> (fill, edge)
    "data": ("#ffffff", "#8a9099"),
    "ai": ("#fdebd3", "#c77d22"),
    "human": ("#e3f1e1", "#3f8a3a"),
    "engine": ("#dfeaf6", "#2b5c8f"),
}
W, H, DX = 1.8, 0.95, 2.15
TOP, BOTTOM = 2.4, 0.0

# (column, row y, label, kind)
BOXES = [
    (0, TOP, "Building-code\nPDF", "data"),
    (1, TOP, "M1 Document\nparser (Docling)", "engine"),
    (2, TOP, "M3 Rule builder\n(LLM)", "ai"),
    (3, TOP, "Rule drafts\n(pending review)", "data"),
    (4, TOP, "Human review\naccept, edit\nor reject", "human"),
    (5, TOP, "Rule database\n(Supabase)", "data"),
    (2, BOTTOM, "IFC model", "data"),
    (3, BOTTOM, "Pre-flight\nvalidation", "engine"),
    (4, BOTTOM, "M2 IFC reader\nelements, geometry\nand space graph", "engine"),
    (5, BOTTOM, "M4 Comparator +\narchitectural\nengines", "engine"),
    (6, BOTTOM, "M5 Reporter", "engine"),
    (7, BOTTOM, "BCF 2.1 issues\n+ 3D viewer", "data"),
]
LEGEND = [("data", "Data / artefact"), ("ai", "AI step"), ("human", "Human decision"), ("engine", "Deterministic code")]


def _box(ax, col, y, label, kind):
    fill, edge = STYLES[kind]
    x = col * DX
    ax.add_patch(FancyBboxPatch((x - W / 2, y - H / 2), W, H, boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor=fill, edgecolor=edge, linewidth=1.3))
    ax.text(x, y, label, ha="center", va="center", fontsize=7.6, color=INK)


def _arrow(ax, start, end):
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 1.2})


def main() -> int:
    ap = argparse.ArgumentParser()
    default = Path(__file__).resolve().parent.parent / "docs" / "publication" / "figures" / "fig_architecture_pipeline.png"
    ap.add_argument("-o", "--out", type=Path, default=default)
    a = ap.parse_args()

    fig, ax = plt.subplots(figsize=(11.5, 4.3), dpi=300)
    for box in BOXES:
        _box(ax, *box)
    for y, cols in ((TOP, range(0, 5)), (BOTTOM, range(2, 7))):
        for c in cols:
            _arrow(ax, (c * DX + W / 2, y), ((c + 1) * DX - W / 2, y))
    _arrow(ax, (5 * DX, TOP - H / 2), (5 * DX, BOTTOM + H / 2))
    ax.text(5 * DX + 0.1, (TOP + BOTTOM) / 2, "approved rules\nand thresholds", ha="left", va="center",
            fontsize=8, color=MUTED, style="italic")

    ax.text(-W / 2, TOP + 0.75, "Pillar A: rule extraction (AI-assisted, human-verified)", fontsize=10,
            fontweight="bold", color=INK, ha="left")
    ax.text(-W / 2, BOTTOM + 0.75, "Pillar B: architectural audit (deterministic)", fontsize=10,
            fontweight="bold", color=INK, ha="left")

    for i, (kind, label) in enumerate(LEGEND):
        fill, edge = STYLES[kind]
        x = -W / 2 + i * 2.6
        ax.add_patch(FancyBboxPatch((x, -1.25), 0.3, 0.22, boxstyle="round,pad=0.01,rounding_size=0.04",
                                    facecolor=fill, edgecolor=edge, linewidth=1.1))
        ax.text(x + 0.42, -1.14, label, fontsize=8.5, color=MUTED, va="center")

    ax.set_xlim(-W / 2 - 0.15, 7 * DX + W / 2 + 0.15)
    ax.set_ylim(-1.45, TOP + 1.1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, facecolor="white")
    plt.close(fig)
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
