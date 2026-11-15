"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId } from "react";

import stationCheck from "@content/evidence/station-phoenix-check.json";
import { formatNumber, useFormatRate } from "@/lib/format";

const EVIDENCE_FILE = "content/evidence/station-phoenix-check.json";
// Both series count days, so each rate is in days per decade.
const RATE_UNIT = "days";
// The rounding of the verdict card, so the grid-cell row reads as the demo card does.
const RATE_SHOWN = { maximumSignificantDigits: 2 } satisfies Intl.NumberFormatOptions;
const MEAN_SHOWN = { maximumFractionDigits: 1 } satisfies Intl.NumberFormatOptions;
const R_SHOWN = {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
} satisfies Intl.NumberFormatOptions;
const YEAR = { useGrouping: false } satisfies Intl.NumberFormatOptions;
const ROWS = ["station", "grid_cell"] as const;

/**
 * The station check of the Phoenix demo trend: NOAA GHCN-Daily counts at Sky Harbor
 * against the POWER cell, both tested by the app's engine. The numbers come from the
 * evidence file. Non-NASA context, never an input to a verdict (FR-36).
 */
export function StationCheckSection() {
  const t = useTranslations("methods.station_check");
  const locale = useLocale();
  const formatRate = useFormatRate();
  const headingId = useId();
  const { agreement, source, station } = stationCheck;
  const years = {
    first: formatNumber(station.trend.first_year, locale, YEAR),
    last: formatNumber(station.trend.last_year, locale, YEAR),
  };
  const rate = (value: number) => formatNumber(value, locale, RATE_SHOWN);

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <h2 id={headingId} className="text-lg font-semibold">
        {t("heading")}
      </h2>
      <p className="font-medium">{t("label")}</p>
      <p>{t("how", { station: source.station_id, ...years })}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="pb-2 text-left text-muted-foreground">
            {t("caption", years)}
          </caption>
          <thead>
            <tr className="border-b">
              <th scope="col" className="py-2 pr-4 font-medium">
                {t("columns.series")}
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                {t("columns.rate")}
              </th>
              <th scope="col" className="py-2 pr-4 font-medium">
                {t("columns.interval")}
              </th>
              <th scope="col" className="py-2 font-medium">
                {t("columns.mean")}
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const { mean_days, trend } = stationCheck[row];
              return (
                <tr key={row} className="border-b">
                  <th scope="row" className="py-2 pr-4 font-normal">
                    {t(`rows.${row}`)}
                  </th>
                  <td className="py-2 pr-4 tabular-nums">
                    {formatRate(trend.sen_per_decade, RATE_UNIT, null, RATE_SHOWN)}
                  </td>
                  <td className="py-2 pr-4 tabular-nums">
                    {t("interval", {
                      low: rate(trend.sen_ci_low_per_decade),
                      high: rate(trend.sen_ci_high_per_decade),
                    })}
                  </td>
                  <td className="py-2 tabular-nums">
                    {formatNumber(mean_days, locale, MEAN_SHOWN)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p>
        {t("agreement", {
          r: formatNumber(agreement.pearson_r, locale, R_SHOWN),
          detrended: formatNumber(agreement.link_test.r, locale, R_SHOWN),
        })}
      </p>
      <p>
        {t("gap", {
          gap: formatNumber(agreement.mean_gap_days, locale, MEAN_SHOWN),
        })}
      </p>
      <p className="text-sm text-muted-foreground">
        {t("source", {
          file: EVIDENCE_FILE,
          station: source.station_id,
          version: stationCheck.engine_version,
        })}
      </p>
    </section>
  );
}
