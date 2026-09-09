// Which OpenRouter model best extracts a correct, complete, executable rule
// from a golden building-code sentence?
//
// The "agent" under test is BIM-Guard's real rule extractor
// (app.modules.rule_builder.llamaindex_rule_generator.LlamaIndexRuleGenerator),
// invoked for real once per (candidate model, case) through eval/ori_bridge.py
// — see that file's docstring for why this doesn't reimplement the extractor
// in TypeScript. Ori supplies what it's built for: the live OpenRouter model
// catalog (candidateModels) and LLM-as-judge scoring (setupJudge), replacing
// this repo's old hand-rolled single-provider judge in eval_harness.py.
//
// Cases are eval_harness.py's EVAL_CASES (hand-authored golden sentences +
// ideal rules) — kept there as the single source of truth; only the id list
// is duplicated here since bun test cannot import a Python module.
//
// Run: ori eval evals/rule-extraction/judge-quality.eval.ts
// Pilot the cost first: ori eval evals/rule-extraction/judge-quality.eval.ts --pilot 1

import { expect, test } from "bun:test";
import { candidateModels, pilotCases, setupJudge } from "ori/eval";
import { runCase } from "./lib/bridge";

// Mirrors eval_harness.EVAL_CASES's `id` field. Source text and ideal rule
// stay in Python — ori_bridge.py's `case` command hands both back per call,
// so a case can't silently drift between the two copies.
const CASE_IDS = [
  "stair_width",
  "riser_height",
  "tread_run",
  "guard_height",
  "door_width",
  "window_egress",
  "handrail_height_range",
  "ambiguous_ventilation",
];

const CASES = pilotCases(CASE_IDS);

const RULE_EXTRACTION_CRITERIA = `
You are grading a BIM compliance rule-extraction system. You will see the
source building-code sentence, the IDEAL_RULE a human expert would write,
and the GENERATED_RULE the system under test actually produced.

Pass only when the generated rule would let an automated IFC compliance
checker verify the same requirement the source text expresses, with the
right element target, property, operator, and value(s)/unit. Minor naming
differences (e.g. "ClearWidth" vs "clear_width") are fine as long as the
mapping is unambiguous; a wrong element, wrong operator, wrong value, or a
requirement dropped entirely is a failure. A GENERATED_RULE of null (no rule
extracted) fails unless IDEAL_RULE itself has no numeric threshold to check
(a "needs_review" case).
`.trim();

// Cheap OpenRouter catalog query (free, no model spend) — narrows the
// slate before any billable call happens below.
const candidates = await candidateModels({
  limit: 5,
  maxPromptPrice: 0.000005,
});

// Judge default (~anthropic/claude-opus-latest) is fine as long as no
// Anthropic model is in `candidates` above — Ori prints a warning naming any
// family collision at run time; heed it before trusting a run.
const judge = setupJudge({ minScore: 0.7 });

test.concurrent.each(candidates)("extracts correct, executable rules: %s", async (slug) => {
  const model = `openrouter/${slug}`;
  const failures: Error[] = [];

  for (const caseId of CASES) {
    try {
      const result = await runCase(caseId, model);
      const verdict = await judge.evaluate({
        criteria: RULE_EXTRACTION_CRITERIA,
        prompt: result.source_text,
        output: JSON.stringify({
          IDEAL_RULE: result.ideal_rule,
          GENERATED_RULE: result.generated,
        }),
      });
      if (!verdict.pass) {
        failures.push(new Error(`${caseId}: ${verdict.reason} (score=${verdict.score.toFixed(2)})`));
      }
    } catch (error) {
      failures.push(error instanceof Error ? error : new Error(String(error)));
    }
  }

  // Every case runs and books its own verdict above regardless of earlier
  // failures (per-case try/catch, not a throwing assertion mid-loop) — the
  // single assertion at the end just decides pass/fail for the whole slate.
  expect(failures).toEqual([]);
});
