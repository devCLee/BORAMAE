import type { NoVerdictReason, TrendResult, Verdict } from "@/contracts/types";

/** What a trend result says: its verdict, or the reason that it holds none. */
export type Outcome = Verdict | NoVerdictReason;

export function outcomeOf(result: TrendResult): Outcome {
  // The contract gives a result a verdict or a reason, never neither.
  return result.verdict ?? result.reason ?? "no_data";
}
