# Data Licensing

This repository commits third-party copyrighted building-code corpora under
`sources/` for use as evaluation inputs (rule extraction, gold-standard
annotation, DocLang conversion). This document states what those materials
are, why they are here, and the terms they are retained under.

## What is committed

| File | Source | Copyright holder |
|---|---|---|
| `sources/OBC_2023.App-A.pdf` | Ontario Building Code 2023, Appendix A | © King's Printer for Ontario (Crown copyright) |
| `sources/OBC_2023.App-A_docling.dclx` | Docling-parsed derivative of the above (full text) | derivative of the above |
| `sources/OBC_2023.Volume_1_P_9.pdf` | Ontario Building Code 2023, Volume 1, Part 9 | © King's Printer for Ontario (Crown copyright) |
| `sources/OBC_2023.Volume_1_P_9.dclg` | DocLang-annotated derivative of the above (full text) | derivative of the above |
| `sources/OBC_2023.Volume_1_P_9_extracted_subset.pdf` | Extracted subset of the above (Part 9.8, stairs) | derivative of the above |
| `sources/OBC_2023.Volume_1_P_9_extracted_subset_docling.dclg` | DocLang derivative of the subset above | derivative of the above |
| `sources/SBC-201-2007.pdf` | Saudi Building Code 201-2007 | © Saudi Building Code National Committee (SBCNC) |
| `sources/SBC-201-2007.md` | Full-text Markdown transcription of the above | derivative of the above |

## Basis for retention

These materials are retained in this **private** repository for **non-commercial
academic research and educational use**, specifically:

- as the evaluation corpus for automated rule-extraction and NLP-annotation
  accuracy scoring (`eval/score_rule_extraction.py`, `eval/score_nlp_annotation.py`,
  `nlp_annotation/`);
- as the source for hand-annotated gold-standard ground truth
  (`eval/eval_gold_code_9_8_stairs.py`);
- in support of an MSc thesis (MAICEN Group 5, Final Master Project) whose
  primary contribution is the compliance-checking software these documents
  are used to evaluate, not the documents themselves.

This use is treated as covered by fair dealing for the purpose of research
and private study (Canada, *Copyright Act* s. 29, applicable to the Ontario
Building Code materials) and by the equivalent research/education exception
under Saudi copyright law for the SBC materials. Building codes are also
routinely treated as having a public-interest dimension distinct from
ordinary copyrighted works, since compliance with them is a legal
requirement — but that does not by itself grant a redistribution right, and
none is claimed here.

## What this does NOT authorize

- **No redistribution.** This repository is and will remain **private**. No
  license or permission to copy, redistribute, publish, or sublicense these
  materials — in original or derivative form — is granted to any third party
  by their presence here.
- **No commercial use** of the corpus text itself (as distinct from the
  compliance-checking software, which is separately licensed under
  [`LICENSE`](../LICENSE)).
- **No implied endorsement** by the King's Printer for Ontario, SBCNC, or any
  other rights holder.

## If this repository's visibility ever changes

Before this repository is made public, transferred, or its access is
broadened beyond the current examiner/reviewer audience, the `sources/`
directory (and its derivatives — the `.dclg`/`.dclx`/`.md` files above) must
either be removed from the working tree and replaced with a fetch script plus
document checksums, or a specific redistribution license must be confirmed
with each rights holder. **Note that git history retains these files even
after a working-tree removal** — see the repository rebuild plan's discussion
of why a full history rewrite (`git filter-repo`) was assessed and rejected
for this repository while it stays private; that assessment would need to be
revisited if publication is ever planned.

## Contact

Questions about this repository's use of third-party materials: contact the
repository owner via the contact information in `CITATION.cff`.
