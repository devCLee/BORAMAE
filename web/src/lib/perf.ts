import type { PerfMark } from "@/state/types";

export const MARK_SKIP_ACTIVATED = "skip-activated" satisfies PerfMark;
export const MARK_MAP_INTERACTIVE = "map-interactive" satisfies PerfMark;
export const MARK_ANALYSIS_STARTED = "analysis-started" satisfies PerfMark;
export const MARK_FIRST_CHART_RENDERED =
  "first-chart-rendered" satisfies PerfMark;

/**
 * Sets a browser performance mark (TR-F-009, TR-Q-009). Read the marks with
 * performance.getEntriesByName(name).
 */
export function markPerf(name: PerfMark): void {
  performance.mark(name);
}
