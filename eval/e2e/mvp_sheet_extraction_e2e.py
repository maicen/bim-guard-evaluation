"""Run a door or window MVP rule sheet (PDF) through BIM-Guard's live Rule Extraction
Studio and score the drafts against the sheet's own rule table.

Reuses the UI flow of extraction_confusion_e2e.py (same saved session; run that
script with --login first) and the scorer in eval/score_mvp_pdf_extraction.py.

Usage: uv run python eval/e2e/mvp_sheet_extraction_e2e.py --pack door \
           --pdf path/to/BIMGuard_Door_MVP_20_Rules_Categorized.pdf --run 1

Outputs to eval/results/mvp_pdf_extraction/<pack>_run<N>/: drafts.json, confusion.json,
draft_review.png, trace.zip.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO, REPO / "eval"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from eval.e2e.extraction_confusion_e2e import DEFAULT_BASE_URL, DEFAULT_STATE, newest_run, run_extraction  # noqa: E402
from score_mvp_pdf_extraction import GOLD_PATH, score  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", choices=("door", "window"), required=True)
    ap.add_argument("--pdf", type=Path, help="the rule sheet, uploaded if the library does not hold it yet; "
                                             "omit to reuse the library document of the same name")
    ap.add_argument("--run", type=int, required=True, help="run number, used in the output folder name")
    ap.add_argument("--model", default="openai/gpt-5.6-luna-pro")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--storage-state", type=Path, default=DEFAULT_STATE)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()

    pack = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["packs"][a.pack]
    if a.pdf and a.pdf.name != pack["document"]:
        sys.exit(f"--pdf must be {pack['document']}: the answer key was transcribed from that file")
    stem = Path(pack["document"]).stem
    out_dir = REPO / "eval" / "results" / "mvp_pdf_extraction" / f"{a.pack}_run{a.run}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # run_extraction selects --existing-doc by file name and uploads that path only when the
    # library does not hold it; `clauses` just has to be a readable file on this route.
    ui = argparse.Namespace(storage_state=a.storage_state, base_url=a.base_url, clauses=a.pdf or GOLD_PATH, doc_title=stem,
                            existing_doc=str(a.pdf.resolve()) if a.pdf else pack["document"], model=a.model,
                            attempts=a.attempts, headed=a.headed)
    drafts = newest_run(run_extraction(ui, out_dir))
    for leftover in out_dir.glob(f"{stem}_*.txt"):  # run_extraction's clause-file copy, unused here
        leftover.unlink()
    (out_dir / "drafts.json").write_text(json.dumps(drafts, indent=1, default=str) + "\n", encoding="utf-8")

    res = score(pack, drafts)
    res["run"] = {"base_url": a.base_url, "model": a.model, "run_at": datetime.now(UTC).isoformat(timespec="seconds")}
    (out_dir / "confusion.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    right = res["all_fields_right"]
    print(f"{a.pack} run {a.run}: {len(drafts)} drafts, {res['found']} of {res['gold_rules']} rules found, "
          f"{right} right in every field, {len(res['invented'])} invented -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
