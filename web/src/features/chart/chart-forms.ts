import type { TrendResult } from "@/contracts/types";

/** The forms of the chart (FR-10). The yearly form is the tested series. */
export type ChartForm = "yearly" | "monthly" | "anomalies";

export interface ChartPoint {
  /** The year, with a month as a twelfth of it. */
  x: number;
  /** Null for a missing month. */
  y: number | null;
  isCensored: boolean;
}

export interface BandPoint {
  x: number;
  y0: number;
  y1: number;
}

const MONTHS_PER_YEAR = 12;

/**
 * The forms that the file holds (TDD "Chart", Q-022): the yearly form always,
 * and the monthly values and anomalies only for a monthly source.
 */
export function listForms(result: TrendResult): ChartForm[] {
  return result.series.monthly === null
    ? ["yearly"]
    : ["yearly", "monthly", "anomalies"];
}

export function toPoints(result: TrendResult, form: ChartForm): ChartPoint[] {
  const { yearly, monthly } = result.series;
  if (form === "yearly" || monthly === null) {
    return yearly.years.map((year, index) => ({
      x: year,
      y: yearly.values[index],
      isCensored: yearly.is_censored[index],
    }));
  }
  const values = form === "monthly" ? monthly.values : monthly.anomalies;
  return monthly.months.map((month, index) => ({
    x: toYearPosition(month),
    y: values[index],
    isCensored: false,
  }));
}

/** The ends of the Sen line (intercept + slope x year) over the tested years, or null with no line. */
export function toTrendLine(result: TrendResult): ChartPoint[] | null {
  const { slope, intercept } = result.stats.sen;
  const ends = toYearEnds(result);
  if (slope === null || intercept === null || ends === null) {
    return null;
  }
  return ends.map((x) => ({ x, y: intercept + slope * x, isCensored: false }));
}

/**
 * The 95% band: the lines of the two Sen interval slopes through the Sen line at
 * the middle of the tested years. They cross there, so three points draw it.
 */
// ponytail: TRD Q-02 leaves the slope and interval of the band open; the Sen
// interval through the midpoint is the working value. Change it here once Q-02 is fixed.
export function toBand(result: TrendResult): BandPoint[] | null {
  const { slope, intercept, ci_low: low, ci_high: high } = result.stats.sen;
  const ends = toYearEnds(result);
  if (
    slope === null ||
    intercept === null ||
    low === null ||
    high === null ||
    ends === null
  ) {
    return null;
  }
  const [first, last] = ends;
  const middle = (first + last) / 2;
  const atMiddle = intercept + slope * middle;
  return [first, middle, last].map((x) => {
    const lowY = atMiddle + low * (x - middle);
    const highY = atMiddle + high * (x - middle);
    return { x, y0: Math.min(lowY, highY), y1: Math.max(lowY, highY) };
  });
}

function toYearEnds(result: TrendResult): [number, number] | null {
  const { years } = result.series.yearly;
  return years.length === 0 ? null : [years[0], years[years.length - 1]];
}

function toYearPosition(yearMonth: string): number {
  const [year, month] = yearMonth.split("-").map(Number);
  return year + (month - 1) / MONTHS_PER_YEAR;
}
