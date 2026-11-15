import { useLocale, useTranslations } from "next-intl";

import type { ShareScale } from "@/contracts/types";
import { toDisplayRate } from "@/lib/units";

// ponytail: the drawer shows the stored size in SI megabytes (Intl "megabyte") with one
// decimal; no document fixes the form. The exact byte count shows only for the request facts.
const BYTES_PER_MEGABYTE = 1_000_000;

export function formatNumber(
  value: number,
  locale: string,
  options?: Intl.NumberFormatOptions,
): string {
  return new Intl.NumberFormat(locale, options).format(value);
}

/** A year and month such as "1981-01", as the locale writes it. */
export function formatMonth(yearMonth: string, locale: string): string {
  const [year, month] = yearMonth.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(Date.UTC(year, month - 1));
}

export function formatMegabytes(bytes: number, locale: string): string {
  return formatNumber(bytes / BYTES_PER_MEGABYTE, locale, {
    style: "unit",
    unit: "megabyte",
    maximumFractionDigits: 1,
  });
}

/**
 * formatRate(value, rate_unit, share_scale) in the UI language, such as
 * "1.2 points per decade". A hook, because the words come from the units messages.
 * A unit with no label shows as the result names it.
 */
export function useFormatRate() {
  const locale = useLocale();
  const t = useTranslations("units");

  return function formatRate(
    value: number,
    rateUnit: string,
    shareScale: ShareScale | null,
    options?: Intl.NumberFormatOptions,
  ): string {
    const rate = toDisplayRate(value, rateUnit, shareScale);
    const labelKey = `label.${rate.unit}`;
    return t("per_decade", {
      value: formatNumber(rate.value, locale, options),
      unit: t.has(labelKey) ? t(labelKey) : rate.unit,
    });
  };
}
