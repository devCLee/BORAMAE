import type { ShareScale } from "@/contracts/types";

/** The rate unit of a mean-type metric of a share variable (TRD Q-02 definition 9). */
const PERCENT_POINTS = "percent_points";

/** A linear unit change: shown = data x factor + offset. */
export interface Conversion {
  from: string;
  to: string;
  factor: number;
  offset: number;
}

/**
 * The one units table (TDD "Units"). The service stores data units; display and the
 * number guard convert through this table only. RH2M is a percent share, so it gets
 * factor 1.
 */
export const CONVERSIONS = {
  temperature: { from: "C", to: "F", factor: 9 / 5, offset: 32 },
  temperature_difference: { from: "C", to: "F", factor: 9 / 5, offset: 0 },
  precipitation: { from: "mm", to: "in", factor: 1 / 25.4, offset: 0 },
  distance: { from: "km", to: "mi", factor: 1 / 1.609344, offset: 0 },
  share_fraction: { from: "1", to: PERCENT_POINTS, factor: 100, offset: 0 },
  share_percent: { from: "%", to: PERCENT_POINTS, factor: 1, offset: 0 },
} as const satisfies Record<string, Conversion>;

const SHARE_CONVERSIONS: Record<ShareScale, Conversion> = {
  fraction: CONVERSIONS.share_fraction,
  percent: CONVERSIONS.share_percent,
};

export function convert(value: number, conversion: Conversion): number {
  return value * conversion.factor + conversion.offset;
}

export function invert(value: number, conversion: Conversion): number {
  return (value - conversion.offset) / conversion.factor;
}

/**
 * A rate per decade in the unit that the card shows. Only a percent_points rate
 * changes: the share of its variable becomes percentage points. Every other rate
 * keeps its data unit, so an RH2M day count stays in days.
 */
export function toDisplayRate(
  value: number,
  rateUnit: string,
  shareScale: ShareScale | null,
): { value: number; unit: string } {
  if (rateUnit !== PERCENT_POINTS) {
    return { value, unit: rateUnit };
  }
  if (shareScale === null) {
    throw new Error(
      "A percent_points rate needs the share scale of its variable.",
    );
  }
  return {
    value: convert(value, SHARE_CONVERSIONS[shareScale]),
    unit: PERCENT_POINTS,
  };
}
