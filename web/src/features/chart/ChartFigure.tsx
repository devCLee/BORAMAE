"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { ChipVerdict } from "@/components/VerdictChip";
import type { Lang, TrendResult } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";
import { formatNumber } from "@/lib/format";
import { MARK_FIRST_CHART_RENDERED, markPerf } from "@/lib/perf";
import { actions, useAppStore } from "@/state/store";

import {
  type ChartForm,
  listForms,
  toBand,
  toPoints,
  toTrendLine,
} from "./chart-forms";
import { ChartPlot, type TrendRole } from "./ChartPlot";
import { ChartTap } from "./ChartTap";

// Rise red, fall blue, not yet gray (DESIGN_SYSTEM.md "Colors"). The legend and the
// verdict card say the same in words, so color is never the only signal.
const TREND_ROLES: Record<ChipVerdict | "pending", TrendRole> = {
  // ponytail: before the tap is answered the line stays gray, so its color does not
  // give the verdict away. No document says how the chart looks before the verdict.
  pending: { line: "stroke-not-yet", band: "fill-not-yet/15" },
  significant_rise: { line: "stroke-trend-rise", band: "fill-trend-rise/15" },
  significant_fall: { line: "stroke-trend-fall", band: "fill-trend-fall/15" },
  not_yet: { line: "stroke-not-yet", band: "fill-not-yet/15" },
  no_trend: { line: "stroke-no-trend", band: "fill-no-trend/15" },
  record_too_short: { line: "stroke-too-short", band: "fill-too-short/15" },
};

/** The chart of one trend result with at least one yearly value. */
export function ChartFigure({ result }: { result: TrendResult }) {
  const t = useTranslations("chart");
  const units = useTranslations("units");
  const lang = useLocale() as Lang;
  const { data: catalog } = useCatalog();
  const gate = useAppStore((state) => state.verdictGate);
  const [form, setForm] = useState<ChartForm>("yearly");
  const figureRef = useRef<HTMLElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    markPerf(MARK_FIRST_CHART_RENDERED);
  }, [result]);

  const forms = listForms(result);
  const shownForm = forms.includes(form) ? form : "yearly";
  const isYearly = shownForm === "yearly";
  // ponytail: the line and the band show on the yearly form only, because the tested
  // series is yearly. Which form shows the band is open (TDD Q-022).
  const trendLine = isYearly ? toTrendLine(result) : null;
  const band = isYearly ? toBand(result) : null;
  // A line exists only with statistics, so a result with no verdict here is record too short.
  const role =
    TREND_ROLES[
      gate === "revealed" ? (result.verdict ?? "record_too_short") : "pending"
    ];
  const variable = catalog?.variables.find(({ id }) => id === result.spec.var);
  const metric = catalog?.metrics.find(({ id }) => id === result.spec.metric.id);
  const toUnitLabel = (unit: string) =>
    units.has(`label.${unit}`) ? units(`label.${unit}`) : unit;
  const yearlyUnit = toUnitLabel(result.unit);
  const { years, values, is_censored: isCensored } = result.series.yearly;
  const hasCensored = isCensored.includes(true);
  const descriptionKey =
    isYearly && trendLine === null ? "yearly_no_trend" : shownForm;

  function handleAnswer() {
    actions.revealVerdict();
    figureRef.current?.focus();
  }

  return (
    <figure
      ref={figureRef}
      tabIndex={-1}
      aria-labelledby={titleId}
      className="flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={titleId} className="text-sm font-medium">
          {t("title", {
            variable: variable?.name[lang] ?? result.spec.var,
            metric: metric?.name[lang] ?? result.spec.metric.id,
          })}
        </h3>
        {forms.length > 1 && (
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            spacing={0}
            value={shownForm}
            onValueChange={(next: ChartForm | "") => next && setForm(next)}
            aria-label={t("forms.label")}
          >
            {forms.map((option) => (
              <ToggleGroupItem key={option} value={option} className="min-h-11">
                {t(`forms.${option}`)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        )}
      </div>
      <p id={descriptionId} className="text-xs text-muted-foreground">
        {t(`description.${descriptionKey}`)}
      </p>
      <ChartPlot
        points={toPoints(result, shownForm)}
        form={shownForm}
        trendLine={trendLine}
        band={band}
        role={role}
        unitLabel={isYearly ? yearlyUnit : toUnitLabel(variable?.unit ?? result.unit)}
        labelledBy={titleId}
        describedBy={descriptionId}
      />
      {isYearly && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <li className="flex items-center gap-1.5">
            <svg aria-hidden width="10" height="10">
              <circle cx="5" cy="5" r="3.5" className="fill-foreground" />
            </svg>
            {t("legend.value")}
          </li>
          {hasCensored && (
            <li className="flex items-center gap-1.5">
              <svg aria-hidden width="10" height="10">
                <circle
                  cx="5"
                  cy="5"
                  r="3.5"
                  className="fill-background stroke-foreground stroke-[1.5]"
                />
              </svg>
              {t("legend.censored")}
            </li>
          )}
          {trendLine && (
            <li className="flex items-center gap-1.5">
              <svg aria-hidden width="16" height="10">
                <line x1="0" x2="16" y1="5" y2="5" className={`stroke-2 ${role.line}`} />
              </svg>
              {t("legend.trend")}
            </li>
          )}
          {band && (
            <li className="flex items-center gap-1.5">
              <svg aria-hidden width="16" height="10">
                <rect width="16" height="10" className={role.band} />
              </svg>
              {t("legend.band")}
            </li>
          )}
        </ul>
      )}
      <table className="sr-only">
        <caption>{t("table.caption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("table.year")}</th>
            <th scope="col">{t("table.value", { unit: yearlyUnit })}</th>
            <th scope="col">{t("table.note")}</th>
          </tr>
        </thead>
        <tbody>
          {years.map((year, index) => (
            <tr key={year}>
              <th scope="row">{year}</th>
              <td>{formatNumber(values[index], lang)}</td>
              <td>{isCensored[index] ? t("table.censored") : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {gate === "pending" && <ChartTap onAnswer={handleAnswer} />}
    </figure>
  );
}
