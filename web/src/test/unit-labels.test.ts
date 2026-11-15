import { expect, test } from "vitest";

import { messages } from "@/i18n/messages";

// The unit texts of the POWER stores in the built catalog (build-catalog, 2026-11-15)
// and the yearly unit words of the trend service (RULE_UNITS in services/trend.py).
const SERVICE_UNITS = [
  "C",
  "mm/day",
  "mm",
  "cm",
  "1",
  "%",
  "kg m-2",
  "Days",
  "m/s",
  "degree-day-c",
  "Dobsons",
  "hPa",
  "day of season",
  "days",
  "degree-day",
  "months",
  "percent_points",
];
const CASES = (["en", "ko"] as const).flatMap((locale) =>
  SERVICE_UNITS.map((unit) => [locale, unit] as const),
);

test.each(CASES)("should hold a %s label for the unit %s", (locale, unit) => {
  expect(messages[locale].units.label).toHaveProperty([unit]);
});
