import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { createElement, type ReactNode } from "react";
import { expect, test } from "vitest";

import type { Lang } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import { useFormatRate } from "@/lib/format";
import { CONVERSIONS, convert, invert } from "@/lib/units";

const SAMPLE_VALUE = 12.5;
const ROUND_TRIP_DIGITS = 10;

function getFormatRate(locale: Lang) {
  const wrapper = (props: { children: ReactNode }) =>
    createElement(NextIntlClientProvider, {
      locale,
      messages: messages[locale],
      timeZone: "UTC",
      ...props,
    });
  return renderHook(() => useFormatRate(), { wrapper }).result.current;
}

test.each(Object.values(CONVERSIONS))(
  "should round-trip a value from $from to $to",
  (conversion) => {
    expect(
      invert(convert(SAMPLE_VALUE, conversion), conversion),
    ).toBeCloseTo(SAMPLE_VALUE, ROUND_TRIP_DIGITS);
  },
);

test.each([
  { conversion: CONVERSIONS.temperature, value: 100, expected: 212 },
  { conversion: CONVERSIONS.temperature_difference, value: 1, expected: 1.8 },
  { conversion: CONVERSIONS.precipitation, value: 25.4, expected: 1 },
  { conversion: CONVERSIONS.distance, value: 1.609344, expected: 1 },
  { conversion: CONVERSIONS.share_fraction, value: 0.5, expected: 50 },
  { conversion: CONVERSIONS.share_percent, value: 50, expected: 50 },
])(
  "should convert $value from $conversion.from to $expected $conversion.to",
  ({ conversion, value, expected }) => {
    expect(convert(value, conversion)).toBeCloseTo(expected, ROUND_TRIP_DIGITS);
  },
);

test("should show a fraction share rate in percentage points", () => {
  const formatRate = getFormatRate("en");

  expect(formatRate(0.012, "percent_points", "fraction")).toBe(
    "1.2 points per decade",
  );
});

test("should show a percent share rate with no factor", () => {
  const formatRate = getFormatRate("en");

  expect(formatRate(1.2, "percent_points", "percent")).toBe(
    "1.2 points per decade",
  );
});

test("should show an RH2M day count in days with no factor", () => {
  const formatRate = getFormatRate("en");

  expect(formatRate(0.5, "days", "percent")).toBe("0.5 days per decade");
});

test("should show a temperature rate in its data unit", () => {
  const formatRate = getFormatRate("en");

  expect(formatRate(0.31, "C", null)).toBe("0.31 °C per decade");
});

test("should show a share rate in Korean", () => {
  const formatRate = getFormatRate("ko");

  expect(formatRate(0.012, "percent_points", "fraction")).toBe("10년당 1.2%p");
});

test("should show a unit with no label as the result names it", () => {
  const formatRate = getFormatRate("en");

  expect(formatRate(2, "lux", null)).toBe("2 lux per decade");
});

test("should round the rate by the options it gets", () => {
  const formatRate = getFormatRate("en");

  expect(
    formatRate(3.288288, "days", null, { maximumFractionDigits: 1 }),
  ).toBe("3.3 days per decade");
});
