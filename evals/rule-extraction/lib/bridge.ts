// Spawns eval/ori_bridge.py (repo root) with bim-guard's own Python
// interpreter and parses its single JSON line. See ori_bridge.py's module
// docstring for why this shells out instead of reimplementing BIM-Guard's
// rule extractor in TypeScript.
//
// Interpreter resolution, in order:
//   1. BIMGUARD_PYTHON env var (explicit path to a python executable)
//   2. <BIMGUARD_PATH>/.venv/{Scripts/python.exe, bin/python} — BIM-Guard's
//      own venv, which has ifcopenshell/litellm/llama-index; this repo's
//      venv does not.
// BIMGUARD_PATH itself defaults to a sibling "bim-guard" directory next to
// this repo, matching eval/eval_config.py's bimguard_path() convention.

import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

const REPO_ROOT = resolve(import.meta.dir, "..", "..", "..");

function bimguardPath(): string {
  return process.env.BIMGUARD_PATH ?? resolve(REPO_ROOT, "..", "bim-guard");
}

function bimguardPython(): string {
  if (process.env.BIMGUARD_PYTHON) return process.env.BIMGUARD_PYTHON;
  const root = bimguardPath();
  const candidates =
    process.platform === "win32"
      ? [join(root, ".venv", "Scripts", "python.exe")]
      : [join(root, ".venv", "bin", "python")];
  const found = candidates.find((p) => existsSync(p));
  if (!found) {
    throw new Error(
      `could not find bim-guard's Python interpreter under ${root}/.venv. ` +
        `Set BIMGUARD_PYTHON to an explicit interpreter path, or BIMGUARD_PATH ` +
        `to bim-guard's checkout (needs ifcopenshell/litellm/llama-index installed).`
    );
  }
  return found;
}

async function runBridge(args: string[]): Promise<Record<string, unknown>> {
  const proc = Bun.spawn([bimguardPython(), join(REPO_ROOT, "eval", "ori_bridge.py"), ...args], {
    cwd: REPO_ROOT,
    env: { ...process.env, BIMGUARD_PATH: bimguardPath() },
    stdout: "pipe",
    stderr: "pipe",
  });

  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ]);

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(stdout.trim());
  } catch {
    throw new Error(
      `ori_bridge.py produced non-JSON stdout (exit ${exitCode}). stdout: ${stdout.slice(0, 500)} stderr: ${stderr.slice(-2000)}`
    );
  }
  if (exitCode !== 0 || "error" in payload) {
    throw new Error(`ori_bridge.py failed: ${String(payload.error ?? `exit ${exitCode}`)}`);
  }
  return payload;
}

export interface CaseResult {
  readonly case_id: string;
  readonly source_text: string;
  readonly ideal_rule: Record<string, unknown>;
  readonly generated: Record<string, unknown> | null;
  readonly extraction_error: string | null;
  readonly duration_s: number;
}

export interface GoldResult {
  readonly chunks_sent: number;
  readonly failed_chunks: number;
  readonly hits: number;
  readonly total_gold: number;
  readonly recall: number;
  readonly extracted_total: number;
  readonly missed: readonly string[];
  readonly duration_s: number;
}

export function runCase(caseId: string, model: string): Promise<CaseResult> {
  return runBridge(["case", "--case-id", caseId, "--model", model]) as Promise<CaseResult>;
}

export function runGold(model: string, options: { limit?: number } = {}): Promise<GoldResult> {
  const args = ["gold", "--model", model];
  if (options.limit !== undefined) args.push("--limit", String(options.limit));
  return runBridge(args) as Promise<GoldResult>;
}
