// Deterministic model comparison: how many of the real hand-annotated
// GOLD_RULES (eval/eval_gold_code_9_8_stairs.py, CODE 9.8.2-9.8.4.7) does
// each OpenRouter model recover from the REAL gold PDF's real sendable
// chunks (score_rule_extraction.py's own pipeline)?
//
// Deliberately not judge-scored: gold-rule recovery is exactly checkable
// (score_rule_extraction.match_gold_to_extracted — the same matcher
// score_rule_extraction.py itself uses, not reimplemented here), so a judge
// would only add cost on a question that already has a right answer. See
// eval/ori_bridge.py's docstring for the full design rationale and its
// "gold" command for the scoring itself.
//
// No fixed recall floor is asserted here: score_rule_extraction.py Part B
// (this repo's only prior LLM-accuracy baseline for this pipeline) was
// broken against bim-guard's current main when this eval was written — see
// ori_bridge.py's docstring — so there is no trustworthy baseline yet to
// assert against. Run this, look at the report, and promote a real number
// once one exists (matching this repo's baseline philosophy in
// eval/eval_config.py: baselines come from an observed run, not a guess).
//
// Run: ori eval evals/rule-extraction/pdf-gold-recall.eval.ts --report evals/rule-extraction/pdf-gold-recall.md
// Pilot the cost first: ori eval evals/rule-extraction/pdf-gold-recall.eval.ts --pilot 1

import { expect, test } from "bun:test";
import { candidateModels } from "ori/eval";
import { runGold } from "./lib/bridge";

// Caps chunks-per-model to bound cost: the real PDF chunks into more
// sections than a 5-candidate sweep should pay for on every run. Raise once
// you're pricing a specific comparison, not iterating on this file.
const CHUNK_LIMIT = 6;

const candidates = await candidateModels({
  limit: 5,
  maxPromptPrice: 0.000005,
});

test.concurrent.each(candidates)("recovers gold rules from the real stairs PDF: %s", async (slug) => {
  const model = `openrouter/${slug}`;
  const result = await runGold(model, { limit: CHUNK_LIMIT });

  // Sanity floor, not a quality bar: a wired-up extractor should recover
  // *something* from a PDF built entirely from CODE 9.8 stair clauses. Zero
  // across the board signals a broken bridge/prompt, not a weak model.
  expect(result.recall).toBeGreaterThan(0);
});
