/**
 * The allowlist of the number guard (DES-017, TDD Q-009): the named fields whose
 * numbers AI text may state, by record kind. Series values and cell indices are not
 * on it, because almost any small number would then match one of them.
 *
 * ponytail: the lists, the scale of each field and the year ranges are Proposed
 * working values (TRD Q-03). The TRD owner records the final lists.
 */
import type {
  CanonicalSpec,
  CaseBoard,
  Catalog,
  DraftSpec,
  MethodConstants,
  RatesPerDecade,
  ScanHit,
  ScanResult,
  SpecMetric,
  TrendResult,
} from "@/contracts/types";
import type { AppState } from "@/state/types";

/**
 * A level, such as a threshold, converts with the offset of its unit. A change, such
 * as a rate, converts with the factor only.
 */
export type Scale = "level" | "change";

export interface GuardField {
  /** The path of the field in its record, such as "stats.rates.sen". */
  name: string;
  value: number;
  /** The data unit, which picks the conversions of the units table. */
  unit?: string;
  scale?: Scale;
  /** The cards cut a p-value toward zero (VerdictStats.tsx), so the cut form also passes. */
  isPValue?: boolean;
  /** A share of 1, such as the level 0.95, which a percent sign reads as 95. */
  isFraction?: boolean;
  /** The key of the trend result whose provenance the number links to. */
  link?: string;
}

/** The first and the last year of a window. A bare 4-digit year inside one passes. */
export type YearRange = [from: number, to: number];

export interface RecordFields {
  fields: GuardField[];
  years: YearRange[];
}

type FieldDraft = Omit<GuardField, "value"> & { value: number | null | undefined };

const RATE_FIELDS = [
  "sen",
  "sen_ci_low",
  "sen_ci_high",
  "ols",
  "ols_ci_plain_low",
  "ols_ci_plain_high",
  "ols_ci_adj_low",
  "ols_ci_adj_high",
] as const satisfies readonly (keyof RatesPerDecade)[];
/** The method constants that are shares of 1. min_record_years is the other one. */
const METHOD_FRACTIONS = [
  "alpha",
  "ci_level",
  "missing_share_flag",
  "censored_share_switch",
] as const satisfies readonly (keyof MethodConstants)[];
const KM = "km";
/** The rate unit of a mean of a share variable (units.ts): the variable names its data unit. */
const PERCENT_POINTS = "percent_points";

export function trendFields(
  result: TrendResult,
  key: string,
  catalog: Catalog | null,
): RecordFields {
  const { stats, record, method } = result;
  const change = { unit: result.unit, scale: "change" } as const;
  const { first_year: first, last_year: last } = stats;
  const drafts: FieldDraft[] = [
    ...RATE_FIELDS.map((name) => ({
      name: `stats.rates.${name}`,
      value: stats.rates[name],
      ...change,
    })),
    { name: "change_over_record", value: result.change_over_record, ...change },
    { name: "sd", value: result.sd, ...change },
    { name: "stats.mk.p", value: stats.mk.p, isPValue: true },
    { name: "stats.ols.p_plain", value: stats.ols.p_plain, isPValue: true },
    { name: "stats.ols.p_adj", value: stats.ols.p_adj, isPValue: true },
    { name: "years_needed.total", value: result.years_needed?.total },
    { name: "years_needed.more", value: result.years_needed?.more },
    { name: "stats.n", value: stats.n },
    { name: "record.years_covered", value: record.years_covered },
    { name: "span_years", value: result.span_years },
    { name: "record.missing_share", value: record.missing_share, isFraction: true },
    { name: "method.min_record_years", value: method.min_record_years },
    ...METHOD_FRACTIONS.map((name) => ({
      name: `method.${name}`,
      value: method[name],
      isFraction: true,
    })),
    { name: "provenance.period.start", value: monthOf(result.provenance.period.start) },
    ...canonicalDrafts(result.spec, catalog),
  ];
  const tested: YearRange[] = first !== null && last !== null ? [[first, last]] : [];
  return {
    fields: toFields(drafts, key),
    years: [windowYears(result.spec.window), ...tested],
  };
}

export function caseBoardFields(board: CaseBoard, catalog: Catalog | null): RecordFields {
  const { nodes } = board;
  const drafts: FieldDraft[] = [
    { name: "nodes.length", value: nodes.length },
    { name: "drivers.length", value: nodes.filter(({ role }) => role === "driver").length },
    { name: "responses.length", value: nodes.filter(({ role }) => role === "response").length },
    ...nodes.flatMap(({ link, row }) => [
      { name: "link.r", value: link.r },
      { name: "link.p", value: link.p, isPValue: true },
      { name: "link.n_eff", value: link.n_eff },
      { name: "link.lag_years", value: link.lag_years },
      { name: "link.n_overlap", value: link.n_overlap },
      ...metricDrafts(row.driver.var, row.driver.metric, catalog),
      ...metricDrafts(row.response.var, row.response.metric, catalog),
    ]),
    ...canonicalDrafts(board.spec, catalog),
  ];
  // The links run on the cells and the window of the focus, so they link to its
  // provenance, as CaseBoard.tsx does.
  return { fields: toFields(drafts, board.focus_key), years: [windowYears(board.spec.window)] };
}

export function scanFields(scan: ScanResult, catalog: Catalog | null): RecordFields {
  const drafts: FieldDraft[] = [
    { name: "hits.length", value: scan.hits.length },
    { name: "checked.length", value: scan.checked.length },
    {
      name: "checked.tested",
      value: scan.checked.filter(({ status }) => status === "tested").length,
    },
    { name: "nearby.length", value: scan.nearby.length },
    ...scan.nearby.map(({ distance_km: distance }) => ({
      name: "nearby.distance_km",
      value: distance,
      unit: KM,
      scale: "level" as const,
    })),
    ...canonicalDrafts(scan.spec, catalog),
  ];
  // A scan holds no provenance, so a hit links to its stored trend (ScanLists.tsx).
  const hits = scan.hits.flatMap((hit) =>
    toFields(
      [
        { name: "hits.p", value: hit.p, isPValue: true },
        { name: "hits.q", value: hit.q, isPValue: true },
        {
          name: "hits.rate_per_decade",
          value: hit.rate_per_decade,
          unit: hitUnit(hit, catalog),
          scale: "change",
        },
      ],
      hit.trend_key,
    ),
  );
  return {
    fields: [...toFields(drafts), ...hits],
    years: [
      windowYears(scan.spec.window),
      ...scan.nearby.map(({ grid_window: gridWindow }) => windowYears(gridWindow)),
    ],
  };
}

/** The threshold, the months and the season start of the confirmed spec. */
export function specFields(spec: DraftSpec, catalog: Catalog | null): GuardField[] {
  return toFields(metricDrafts(spec.var, spec.metric, catalog));
}

export function appStateFields({
  area,
  window,
  cellPreview,
}: Pick<AppState, "area" | "window" | "cellPreview">): RecordFields {
  return {
    fields: toFields([
      { name: "area.radiusKm", value: area.radiusKm, unit: KM, scale: "level" },
      { name: "cellPreview.count", value: cellPreview?.count },
    ]),
    // "latest" names no year until a result gives its last month.
    years: [[window.start, window.end === "latest" ? window.start : window.end]],
  };
}

function canonicalDrafts(spec: CanonicalSpec, catalog: Catalog | null): FieldDraft[] {
  return [
    ...metricDrafts(spec.var, spec.metric, catalog),
    { name: "spec.cells.length", value: spec.cells.length },
    { name: "spec.window.end", value: monthOf(spec.window[1]) },
  ];
}

function metricDrafts(
  variable: string,
  metric: SpecMetric,
  catalog: Catalog | null,
): FieldDraft[] {
  const { threshold, months, season_start: seasonStart } = metric;
  const [startMonth, startDay] = seasonStart?.split("-").map(Number) ?? [];
  return [
    {
      name: "metric.threshold",
      value: threshold == null ? null : Number(threshold),
      unit: unitOf(variable, catalog),
      scale: "level",
    },
    ...(months ?? []).map((month) => ({ name: "metric.months", value: month })),
    { name: "metric.months.length", value: months?.length },
    { name: "metric.season_start.month", value: startMonth },
    { name: "metric.season_start.day", value: startDay },
  ];
}

function hitUnit(hit: ScanHit, catalog: Catalog | null): string | undefined {
  return hit.rate_unit === PERCENT_POINTS ? unitOf(hit.var, catalog) : hit.rate_unit;
}

function unitOf(variable: string, catalog: Catalog | null): string | undefined {
  return catalog?.variables.find(({ id }) => id === variable)?.unit;
}

/** Drops the empty fields and gives the rest the link of their record. */
function toFields(drafts: FieldDraft[], link?: string): GuardField[] {
  return drafts.flatMap(({ value, ...field }) =>
    typeof value === "number" && Number.isFinite(value) ? [{ ...field, value, link }] : [],
  );
}

function windowYears([start, end]: [number, string]): YearRange {
  return [start, Number(end.slice(0, 4))];
}

function monthOf(yearMonth: string): number {
  return Number(yearMonth.slice(5, 7));
}
