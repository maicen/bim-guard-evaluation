# Ori Eval — rule-extraction model comparison

Uses [Ori Eval](https://openrouter.ai/docs/guides/ori/eval) to answer: *which
OpenRouter model should BIM-Guard use for rule extraction?* Ori supplies the
live OpenRouter model catalog and LLM-as-judge scoring; the actual extraction
call is BIM-Guard's own real code (see `../../eval/ori_bridge.py`'s
docstring for the full design rationale — short version: Ori's
`setupAgent()`/`agent.run()` is built for coding-agent harnesses, not a
single structured-output LLM call, so these evals shell out to bim-guard's
real extractor via a subprocess bridge instead of reimplementing it).

## Files

- `judge-quality.eval.ts` — LLM-as-judge scoring (correctness/completeness/
  executability) over `eval_harness.py`'s hand-authored golden sentences.
  Replaces this repo's old single-provider judge in `eval_harness.py`.
- `pdf-gold-recall.eval.ts` — deterministic recall against the real
  hand-annotated `GOLD_RULES` (`eval/eval_gold_code_9_8_stairs.py`), run over
  the real gold PDF. No judge involved — recall against a known-correct
  answer key is exactly checkable.
- `lib/bridge.ts` — spawns `eval/ori_bridge.py` with bim-guard's own Python
  interpreter and parses its JSON output.

## Prerequisites

1. **Ori CLI**: `curl -fsSL https://openrouter.ai/labs/ori/install.sh | bash`
2. **Bun** (Ori runs evals through `bun test`): `curl -fsSL https://bun.sh/install | bash` (or the PowerShell installer on Windows: `irm bun.sh/install.ps1 | iex`)
3. **An OpenRouter credential** — `ori login`, or set `OPENROUTER_API_KEY`.
4. **bim-guard checked out with its own venv installed** (`ifcopenshell`,
   `litellm`, `llama-index` — not this repo's dependencies). Defaults to a
   sibling `../bim-guard` directory, same convention as `eval/eval_config.py`.
   Override with `BIMGUARD_PATH` / `BIMGUARD_PYTHON` if that doesn't apply.

## Running

```bash
# See what would run and what it would cost, with zero spend:
ori eval evals/rule-extraction --list --allow-no-key
ori eval evals/rule-extraction --dry-run --allow-no-key

# Price it before paying for the full sweep:
ori eval evals/rule-extraction/pdf-gold-recall.eval.ts --pilot 1

# Run for real, with a shareable report:
ori eval evals/rule-extraction --report evals/rule-extraction/comparison.md
```

## Known limitations (as of writing)

- `pdf-gold-recall.eval.ts` asserts no fixed recall floor — this repo had no
  working LLM-accuracy baseline for the current extraction pipeline when
  this was written (`score_rule_extraction.py` Part B imports a module bim-guard
  deleted in `64b13e9`; see `ori_bridge.py`'s docstring). Run it, read the
  report, and promote a real number into the eval once you have one.
- The live extraction adapter (`LlamaIndexRuleGenerator.extract_rules_from_text`)
  doesn't surface `value_min_property`/`value_max_property`, so `GOLD_RULES`
  entries expressing a relative bound (e.g. "Run to Run+25mm") always land in
  `missed` — a real production gap, not a bug here.
- `CHUNK_LIMIT` / `CASE_IDS` in the eval files bound cost during iteration.
  Raise them once you're pricing a specific comparison, not editing the file.
