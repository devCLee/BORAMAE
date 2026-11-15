"use client";

import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Num } from "@/components/Num";
import { Term } from "@/components/Term";
import type {
  CatalogVariable,
  Op,
  RequestMeta,
  TrendResult,
  YearsNeeded,
} from "@/contracts/types";
import { toDisplayRate } from "@/lib/units";

// ponytail: two significant digits for every rate, amount and statistic, and the OLS
// row shows the adjusted interval. No document fixes either (Q-42 is open).
const SHOWN = { maximumSignificantDigits: 2 } satisfies Intl.NumberFormatOptions;
// A p-value is cut, not rounded, so a p just below 0.05 never reads as 0.05.
const P_SHOWN = {
  maximumSignificantDigits: 2,
  roundingMode: "trunc",
} satisfies Intl.NumberFormatOptions;
const YEAR = { useGrouping: false } satisfies Intl.NumberFormatOptions;
const PERCENT = { style: "percent" } satisfies Intl.NumberFormatOptions;
const OP_SIGNS = { ">=": "≥", ">": ">", "<=": "≤", "<": "<" } satisfies Record<
  Op,
  string
>;

interface VerdictStatsProps {
  result: TrendResult;
  meta: RequestMeta | null;
  variable: CatalogVariable;
}

/** The numbers behind the verdict. Each one is a Num, so each opens its provenance. */
export function VerdictStats({ result, meta, variable }: VerdictStatsProps) {
  const t = useTranslations("verdict");
  const tUnits = useTranslations("units");
  const locale = useLocale();
  const { stats, method, spec } = result;
  const { rates } = stats;
  const source = {
    provenance: result.provenance,
    footprint: result.footprint,
    meta,
  };
  const rate = { unit: result.rate_unit, shareScale: variable.share_scale };
  const [endYear, endMonth] = spec.window[1].split("-").map(Number);
  const { threshold, op } = spec.metric;

  const num = (value: number, options?: Intl.NumberFormatOptions) => (
    <Num value={value} options={options} {...source} />
  );
  const rateNum = (value: number) => (
    <Num value={value} rate={rate} options={SHOWN} {...source} />
  );
  const range = (from: ReactNode, to: ReactNode) =>
    t.rich("range", { from: () => from, to: () => to });
  const unitLabel = (unit: string) =>
    tUnits.has(`label.${unit}`) ? tUnits(`label.${unit}`) : unit;
  // The change and the scatter are in the unit of the rate, with no "per decade".
  const amount = (value: number) => {
    const shown = toDisplayRate(value, result.rate_unit, variable.share_scale);
    return t.rich("amount", {
      unit: unitLabel(shown.unit),
      num: () => num(shown.value, SHOWN),
    });
  };
  // FR-15: the years still needed (more), never the total.
  const yearsNeeded = ({ more, reason }: YearsNeeded) =>
    reason == null && more !== null ? (
      <>
        {t.rich("more_years", { count: more, num: () => num(more) })}
        <span className="block text-muted-foreground">
          {t("detection_estimate")}
        </span>
      </>
    ) : (
      t(`years_needed_reasons.${reason}`)
    );
  const monthName = new Intl.DateTimeFormat(locale, {
    month: "long",
    timeZone: "UTC",
  }).format(Date.UTC(endYear, endMonth - 1));

  return (
    <dl className="grid gap-2">
      {rates.sen !== null && (
        <Row label={<Term id="sen_slope" />}>{rateNum(rates.sen)}</Row>
      )}
      {rates.sen_ci_low !== null && rates.sen_ci_high !== null && (
        <Row
          label={
            <>
              <Term id="confidence_interval" /> ({num(method.ci_level, PERCENT)})
            </>
          }
        >
          {range(rateNum(rates.sen_ci_low), rateNum(rates.sen_ci_high))}
        </Row>
      )}
      {rates.ols !== null && (
        <Row label={<Term id="ols_cross_check" />}>
          {rateNum(rates.ols)}
          {rates.ols_ci_adj_low !== null && rates.ols_ci_adj_high !== null && (
            <>
              {" ("}
              {range(rateNum(rates.ols_ci_adj_low), rateNum(rates.ols_ci_adj_high))}
              {")"}
            </>
          )}
        </Row>
      )}
      {stats.mk.p !== null && (
        <Row
          label={
            <>
              <Term id="mann_kendall" /> <Term id="p_value" />
            </>
          }
        >
          {num(stats.mk.p, P_SHOWN)}
        </Row>
      )}
      {result.change_over_record !== null && (
        <Row label={t("fields.change")}>{amount(result.change_over_record)}</Row>
      )}
      {result.sd !== null && (
        <Row label={<Term id="scatter" />}>{amount(result.sd)}</Row>
      )}
      {stats.first_year !== null && stats.last_year !== null && (
        <Row label={t("fields.years_tested")}>
          {range(num(stats.first_year, YEAR), num(stats.last_year, YEAR))}
        </Row>
      )}
      <Row label={t("fields.values")}>{num(stats.n)}</Row>
      <Row label={t("fields.min_record")}>
        {t.rich("years", {
          count: method.min_record_years,
          num: () => num(method.min_record_years),
        })}
      </Row>
      {result.years_needed !== null && (
        <Row label={<Term id="years_needed" />}>
          {yearsNeeded(result.years_needed)}
        </Row>
      )}
      {threshold != null && (
        <Row label={t("fields.threshold")}>
          {op && OP_SIGNS[op]} {num(Number(threshold))} {unitLabel(variable.unit)}
        </Row>
      )}
      <Row label={t("fields.data_through")}>
        {t.rich("month", {
          month_name: monthName,
          year: () => num(endYear, YEAR),
          month: () => num(endMonth),
        })}
      </Row>
    </dl>
  );
}

function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
