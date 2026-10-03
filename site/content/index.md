# BIM-Guard Evaluation

Evaluation harnesses and empirical validation for [BIM-Guard](https://github.com/maicen/bim-guard), an
automated code-compliance platform for OpenBIM (IFC, BCF, IDS). This site presents what the
[evaluation repository](https://github.com/maicen/bim-guard-evaluation) can and cannot back up.

<div class="callout warn" markdown="1">

**Read this first.** Several numbers that appeared in earlier drafts (inter-annotator κ, the LLM-judge
threshold sweep, cross-jurisdiction F1 = 100%) come from scripts that *simulate* their inputs. They are
**not evidence** about BIM-Guard, annotators or the judge, and this site labels them accordingly. Only
the results marked <code class="badge reproduced">reproduced</code> should be cited.

</div>

## What is currently supported

<div class="grid">
<div class="card"><div class="big">22 / 22</div><div class="lbl">Architecture engine benchmark cases correct (13 TP, 9 TN, 0 FP, 0 FN)</div></div>
<div class="card"><div class="big">60 / 60</div><div class="lbl">NLP annotation test cases passing, fully reproducible</div></div>
<div class="card"><div class="big">Wilson 95%</div><div class="lbl">Confidence intervals on every real proportion; accuracy CI is [85.1%, 100%]</div></div>
</div>

The 22-case benchmark is small and procedurally generated, so the interval matters more than the point
estimate: it shows what 22 cases can and cannot establish. See [Results](results.html).

## How this site is organised

- **[Results](results.html)**: the real architecture-engine confusion matrix, then the simulated harnesses, clearly separated.
- **[Claims ledger](claims.html)**: every headline number, its producing script, its artifact, and a verification status.
- **[Limitations](limitations.html)**: methodological gaps, stated plainly.
- **[Determinism audit](determinism.html)**: a run-to-run non-determinism bug that was found, root-caused, fixed and verified.
- **[Reproduce](reproduce.html)**: commands to re-run each harness.

## Verification status legend

| Status | Meaning |
|---|---|
| `reproduced` | Re-run from source inputs on the current codebase; matches the claim. |
| `archived-artifact` | Original output is committed and hash-pinned, but not re-executed. |
| `single-run` | Real result from one execution, no repeats, no variance measured. |
| `not-verified` | Asserted somewhere with no corresponding artifact. |
| `simulated` | Inputs generated from gold data or hard-coded values; **not evidence**. |
| `retired-domain` | Real at the time, but the measured capability has since been removed from the product. |

## Related

- Platform: [BIM Guard](https://bim-guard.xyz/research) (app and documentation) · source: [maicen/bim-guard](https://github.com/maicen/bim-guard)
- Evaluation repo: [maicen/bim-guard-evaluation](https://github.com/maicen/bim-guard-evaluation)
- Cite: see [`CITATION.cff`](https://github.com/maicen/bim-guard-evaluation/blob/main/CITATION.cff)
