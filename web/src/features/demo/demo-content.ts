import type { DemoCase, DemoScript } from "@/contracts/types";
import casesJson from "@content/demo/cases.json";
import firstSnowSeoulJson from "@content/demo/scripts/first-snow-seoul.json";
import hotDaysPhoenixJson from "@content/demo/scripts/hot-days-phoenix.json";

// A JSON import has wide types (an action becomes string), so each file is cast
// once here. lint-content and lint:demo check the files against their shapes.
export const DEMO_CASES = casesJson as unknown as DemoCase[];
const DEMO_SCRIPTS = [
  firstSnowSeoulJson,
  hotDaysPhoenixJson,
] as unknown as DemoScript[];

export function findScript(caseId: string): DemoScript | undefined {
  return DEMO_SCRIPTS.find((script) => script.case_id === caseId);
}

/** lint:demo checks that every script has exactly one verdict step. */
export function verdictIndexOf(script: DemoScript): number {
  return script.steps.findIndex((step) => step.is_verdict_step);
}
