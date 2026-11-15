"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId } from "react";

import falseAlarm from "@content/evidence/false-alarm.json";
import { formatNumber } from "@/lib/format";

// TRD.md:504 (TR-Q-001): the pass rule covers r1 up to 0.2; a higher r1 is reported alone.
const GATED_R1_MAX = 0.2;
const EVIDENCE_FILE = "content/evidence/false-alarm.json";
// ponytail: one decimal of a percent shows a count out of 1,000 series exactly, so a failed
// rate is never rounded down to the rule (D-09). A run with more series needs more digits.
const PERCENT = {
  style: "percent",
  maximumFractionDigits: 1,
} satisfies Intl.NumberFormatOptions;
const PLAIN_DIGITS = { useGrouping: false } satisfies Intl.NumberFormatOptions;

type RateRow = (typeof falseAlarm.rates)[number];
type GateResult = "pass" | "fail" | "separate";

/**
 * The saved false-alarm table of the one protocol run (TR-Q-001, DES-023). The rates
 * come from the evidence file, not from a computation in the browser.
 */
export function FalseAlarmSection() {
  const t = useTranslations("methods.false_alarms");
  const locale = useLocale();
  const headingId = useId();
  const percent = (value: number) => formatNumber(value, locale, PERCENT);
  const count = formatNumber(falseAlarm.series_per_r1, locale);

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <h2 id={headingId} className="text-lg font-semibold">
        {t("heading")}
      </h2>
      <p>
        {t("how", {
          count,
          length: formatNumber(falseAlarm.length, locale),
          alpha: formatNumber(falseAlarm.alpha, locale),
          nominal: percent(falseAlarm.alpha),
          seed: formatNumber(falseAlarm.seed, locale, PLAIN_DIGITS),
        })}
      </p>
      <p>
        {t("rule", {
          max: percent(falseAlarm.false_alarm_max),
          gated: formatNumber(GATED_R1_MAX, locale),
        })}
      </p>
      <p>{t("as_measured")}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="pb-2 text-left text-muted-foreground">
            {t("caption", { count })}
          </caption>
          <thead>
            <tr className="border-b">
              <th scope="col" className="py-2 pr-4 font-medium">
                {t("columns.r1")}
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                {t("columns.rate")}
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                {t("columns.interval")}
              </th>
              <th scope="col" className="py-2 font-medium">
                {t("columns.result")}
              </th>
            </tr>
          </thead>
          <tbody>
            {falseAlarm.rates.map((row) => (
              <tr key={row.r1} className="border-b">
                <th scope="row" className="py-2 pr-4 font-normal tabular-nums">
                  {formatNumber(row.r1, locale)}
                </th>
                <td className="py-2 pr-4 tabular-nums">
                  {percent(row.rate)}{" "}
                  <span className="text-muted-foreground">
                    {t("count", {
                      alarms: formatNumber(row.false_alarms, locale),
                      count,
                    })}
                  </span>
                </td>
                <td className="py-2 pr-4 tabular-nums">
                  {t("interval", {
                    low: percent(row.ci95[0]),
                    high: percent(row.ci95[1]),
                  })}
                </td>
                <td className="py-2 font-medium">
                  {t(`results.${toGateResult(row)}`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-muted-foreground">
        {t("source", {
          file: EVIDENCE_FILE,
          version: falseAlarm.engine_version,
        })}
      </p>
    </section>
  );
}

function toGateResult(row: RateRow): GateResult {
  if (row.r1 > GATED_R1_MAX) {
    return "separate";
  }
  return row.rate <= falseAlarm.false_alarm_max ? "pass" : "fail";
}
