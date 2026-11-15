import type { Op } from "@/contracts/types";
import { formatNumber } from "@/lib/format";
import type { Point } from "@/state/types";

/** The message key of each comparison, because an ICU key cannot hold ">=". */
export const OP_KEYS: Record<Op, "gte" | "gt" | "lte" | "lt"> = {
  ">=": "gte",
  ">": "gt",
  "<=": "lte",
  "<": "lt",
};

// ponytail: two decimals (about 1 km) name a pin; no document fixes the form.
const COORDINATE_DIGITS = 2;

/** A pin as "37.57, 126.98" in the locale. */
export function formatPoint({ lat, lon }: Point, locale: string): string {
  const options = { maximumFractionDigits: COORDINATE_DIGITS };
  return `${formatNumber(lat, locale, options)}, ${formatNumber(lon, locale, options)}`;
}

/** A month 1 to 12 by name in the locale, such as "May" or "5월". */
export function formatMonthName(month: number, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    month: "long",
    timeZone: "UTC",
  }).format(Date.UTC(2000, month - 1));
}
