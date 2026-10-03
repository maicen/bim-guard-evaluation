"""Engine verdicts per property for the MVP door and window rule packs.

One bar per rule: the share of elements BIM-Guard marked FAIL / PASS / MISSING,
hatched where that verdict disagrees with the raw-IFC answer key. Shows the
high-reliability rules plus any property named with --also (default SillHeight).

Inputs:
* bim-guard's docs/validation/data/mvp-door-window-audit.json, written by its
  scripts/validation_mvp_door_window_audit.py (verdict vs. raw IFC per rule).
* eval/fixtures/mvp_door_window_rule_reliability.json, each rule's grade from
  bim-guard's app.modules.rule_reliability.assess_rule.

Usage: uv run python eval/plot_mvp_property_verdicts.py [-o docs/publication/figures/fig_mvp_property_verdicts.png]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from eval_config import bimguard_path  # noqa: E402

INK, MUTED = "#1a1a1a", "#5f6368"
VERDICTS = [("VIOLATION", "FAIL", "#c8553d"), ("COMPLIANT", "PASS", "#2166b3"), ("ABSENT", "MISSING", "#8a9099")]
TARGETS = {"IfcDoor": "doors", "IfcWindow": "windows", "IfcOpeningElement": "openings", "IfcBuildingStorey": "storeys"}


def load_rows(audit: Path, reliability: Path, also: set[str]) -> list[dict]:
    grades = {r["reference"]: r["level"] for r in json.loads(reliability.read_text(encoding="utf-8"))}
    rows = []
    for rule in json.loads(audit.read_text(encoding="utf-8"))["per_rule"]:
        level = grades.get(rule["reference"])
        if level != "high" and rule["property"] not in also:
            continue
        cells = {tuple(k.split("->")): n for k, n in rule["cells"].items()}
        if not cells or any(actual == "UNDEFINED" for actual, _ in cells):
            continue  # matched no element, or the rule has no answer key
        total = sum(cells.values())
        rows.append({
            "label": f"{rule['property']} {rule['operator']} {rule['check_value']}  ({rule['reference']})",
            "pack": rule["pack"],
            "level": level,
            "target": TARGETS.get(rule["target"], rule["target"]),
            "total": total,
            "right": sum(n for (a, p), n in cells.items() if a == p),
            "cells": cells,
        })
    return rows


def draw(rows: list[dict], model: str, out: Path) -> None:
    packs = [("doors", "Door rule pack"), ("windows", "Window rule pack")]
    sizes = [sum(r["pack"] == p for r in rows) for p, _ in packs]
    fig, axes = plt.subplots(2, 1, figsize=(10.2, 0.36 * len(rows) + 2.6), dpi=300,
                             gridspec_kw={"height_ratios": sizes, "hspace": 0.22})
    for ax, (pack, title) in zip(axes, packs):
        group = [r for r in rows if r["pack"] == pack][::-1]
        for y, row in enumerate(group):
            left = 0.0
            for verdict, _, color in VERDICTS:
                for agrees in (True, False):
                    n = sum(c for (a, p), c in row["cells"].items() if p == verdict and (a == p) == agrees)
                    if not n:
                        continue
                    share = n / row["total"]
                    ax.barh(y, share, left=left, height=0.62, color=color, edgecolor="white", linewidth=1.5,
                            hatch=None if agrees else "////")
                    if share >= 0.08:
                        ax.text(left + share / 2, y, f"{n:,}", ha="center", va="center", fontsize=8,
                                fontweight="bold", color="white",
                                bbox=None if agrees else {"facecolor": color, "edgecolor": "none", "pad": 1.2})
                    left += share
            ok = row["right"] == row["total"]
            ax.text(1.02, y, f"{row['right']:,} / {row['total']:,} {row['target']}", ha="left", va="center",
                    fontsize=8.5, color=INK if ok else "#a23a25", fontweight="normal" if ok else "bold")
        ax.set_yticks(range(len(group)), [r["label"] + ("" if r["level"] == "high" else f"  [{r['level']}]") for r in group],
                      fontsize=8.5, color=INK)
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, len(group) - 0.4)
        ax.set_xticks([])
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(title, fontsize=10, fontweight="bold", color=INK, loc="left", pad=4)
    axes[0].text(1.02, sizes[0] - 0.25, "Verdict matches raw IFC", fontsize=8.5, color=MUTED, ha="left", va="bottom")

    handles = [Patch(facecolor=c, label=name) for _, name, c in VERDICTS]
    handles.append(Patch(facecolor="#bbbbbb", hatch="////", edgecolor="white", label="Verdict disagrees with raw IFC"))
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 0.035))
    right, total = sum(r["right"] for r in rows), sum(r["total"] for r in rows)
    fig.suptitle("BIM-Guard verdict per property: high-reliability rules and sill height", fontsize=12,
                 fontweight="bold", color=INK, x=0.5, y=0.985)
    fig.text(0.5, 0.005,
             f"Bar = share of elements per verdict; numbers are element counts. {right:,} of {total:,} checks match "
             f"the raw-IFC answer key.\nOne model ({model}). Rules marked [low] are not high-reliability.",
             ha="center", fontsize=8, color=MUTED)
    fig.subplots_adjust(left=0.4, right=0.82, top=0.93, bottom=0.115)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", type=Path,
                    default=bimguard_path() / "docs" / "validation" / "data" / "mvp-door-window-audit.json")
    ap.add_argument("--reliability", type=Path,
                    default=EVAL_DIR / "fixtures" / "mvp_door_window_rule_reliability.json")
    ap.add_argument("--also", nargs="*", default=["SillHeight"], help="extra properties to show whatever their grade")
    ap.add_argument("-o", "--out", type=Path,
                    default=EVAL_DIR.parent / "docs" / "publication" / "figures" / "fig_mvp_property_verdicts.png")
    a = ap.parse_args()
    rows = load_rows(a.audit, a.reliability, set(a.also))
    model = json.loads(a.audit.read_text(encoding="utf-8"))["model"].split("_", 1)[-1]
    draw(rows, model, a.out)
    for r in rows:
        print(f"{r['label']:55s} {r['right']:>5} / {r['total']:<5} {r['target']}")
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
