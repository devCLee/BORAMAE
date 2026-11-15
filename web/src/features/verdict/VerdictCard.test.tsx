import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";

import type { TrendResult } from "@/contracts/types";
import { closeProvenance } from "@/features/provenance/provenance-state";
import {
  trendNoData,
  trendNoTrend,
  trendNotYet,
  trendSignificant,
  trendTooShort,
  trendZeroInside,
} from "@/test/fixtures";

import {
  definitionOf,
  META,
  numbersMissingFrom,
  numsIn,
  renderCard,
  textOutsideNum,
} from "./verdict-test-kit";

/** What the download link serves: the result file behind the card. */
const FILES: Record<string, TrendResult> = { [META.sourceUrl]: trendSignificant };

const OLS_CONSTANT: TrendResult = {
  ...trendSignificant,
  flags: ["ols_p_missing"],
  stats: {
    ...trendSignificant.stats,
    ols: { ...trendSignificant.stats.ols, reason: "constant_series" },
  },
};
const SHARE_RATE: TrendResult = {
  ...trendNoTrend,
  stats: {
    ...trendNoTrend.stats,
    rates: { ...trendNoTrend.stats.rates, sen: 0.012 },
  },
};

beforeEach(() => {
  closeProvenance();
});

test.each([
  { result: trendSignificant, number: "3.3 days per decade" },
  { result: trendTooShort, number: "-0.045 °C per decade" },
  { result: SHARE_RATE, number: "1.2 points per decade" },
])("should show the rate $number per decade through Num", ({ result, number }) => {
  renderCard(result);

  expect(screen.getByRole("button", { name: `Source of ${number}` })).toBeInTheDocument();
});

test.each([
  {
    card: "significant",
    result: trendSignificant,
    label: "Confidence interval",
    text: "2 days per decade to 5 days per decade",
  },
  {
    card: "significant",
    result: trendSignificant,
    label: "OLS cross-check",
    text: "8.4 days per decade",
  },
  { card: "significant", result: trendSignificant, label: "Threshold used", text: "≥ 0.1 mm/day" },
  { card: "significant", result: trendSignificant, label: "Data through", text: "September 2026" },
  { card: "not-yet", result: trendNotYet, label: "Years needed", text: "20 more years" },
  {
    card: "not-yet",
    result: trendNotYet,
    label: "Years needed",
    text: "A detection estimate, not a forecast.",
  },
  {
    card: "zero-inside",
    result: trendZeroInside,
    label: "Years needed",
    text: "The record is already as long as the estimate needs",
  },
  { card: "no-trend", result: trendNoTrend, label: "Years tested", text: "1981 to 2025" },
  {
    card: "no-trend",
    result: trendNoTrend,
    label: "Confidence interval",
    text: "-0.041 points per decade to 0.29 points per decade",
  },
  { card: "too-short", result: trendTooShort, label: "Minimum record", text: "20 years" },
])("should show $text as $label on the $card card", ({ result, label, text }) => {
  renderCard(result);

  expect(definitionOf(label)).toHaveTextContent(text);
});

test("should show no number of years when the record is already long enough", () => {
  renderCard(trendZeroInside);

  expect(numsIn(definitionOf("Years needed"))).toEqual([]);
});

test("should show the pinned end month in Korean", () => {
  renderCard(trendSignificant, { locale: "ko" });

  expect(definitionOf("자료의 마지막 달")).toHaveTextContent("2026년 9월");
});

test("should put the change over the record beside the scatter", () => {
  renderCard(trendSignificant);

  expect(
    definitionOf("Change over the record")?.parentElement?.nextElementSibling,
  ).toHaveTextContent("Scatter37 days");
});

test.each([
  { result: trendZeroInside, word: "Not yet significant" },
  { result: trendTooShort, word: "Record too short" },
])("should label the card $word", ({ result, word }) => {
  renderCard(result);

  expect(within(screen.getByRole("article")).getByText(word)).toBeInTheDocument();
});

test("should give no verdict on a too-short card", () => {
  renderCard(trendTooShort);

  expect(screen.getByRole("article")).not.toHaveTextContent(
    /Rising, significant|Falling, significant|Not yet significant|No trend detected/,
  );
});

test("should name what a no-trend card tested", () => {
  renderCard(trendNoTrend);

  expect(
    screen.getByRole("article", { name: "Surface soil wetness · Annual mean" }),
  ).toBeInTheDocument();
});

test("should show no statistics for no data", () => {
  renderCard(trendNoData);

  expect(screen.queryAllByRole("button", { name: /^Source of / })).toEqual([]);
});

test.each([
  { result: trendSignificant, text: "The values in this area are rising" },
  { result: trendNotYet, text: "The values lean one way" },
  { result: trendNoTrend, text: "This does not mean that no change is possible" },
  { result: trendTooShort, text: "The record is shorter than the minimum" },
  { result: trendNoData, text: "No data for this area and time window" },
  {
    result: trendNoTrend,
    text: "The OLS cross-check and the Mann–Kendall test disagree on this series.",
  },
  {
    result: OLS_CONSTANT,
    text: "Every yearly value is the same, so the OLS cross-check has no p-value and no interval.",
  },
])("should say: $text", ({ result, text }) => {
  renderCard(result);

  expect(screen.getByRole("article")).toHaveTextContent(text);
});

test("should open with the plain sentence in Korean", () => {
  renderCard(trendSignificant, { locale: "ko" });

  expect(screen.getByRole("article")).toHaveTextContent("이 지역의 값이 오르고 있고");
});

test.each(["disagree", "has no p-value", "No grid cell center"])(
  "should leave out the note with %s without its flag",
  (text) => {
    renderCard(trendSignificant);

    expect(screen.getByRole("article")).not.toHaveTextContent(text);
  },
);

test("should show the containing-cell notice when the service used it", () => {
  renderCard(trendSignificant, { meta: { ...META, usedContainingCell: true } });

  expect(screen.getByRole("article")).toHaveTextContent(
    "No grid cell center falls inside this area",
  );
});

test.each([
  "Snowfall",
  "First date",
  "Sen slope",
  "Confidence interval",
  "OLS cross-check",
  "Mann–Kendall test",
  "p-value",
  "Scatter",
  "Model data",
  "Yearly values are not independent",
])("should link %s to its definition", (name) => {
  renderCard(trendSignificant);

  expect(screen.getByRole("button", { name })).toHaveAttribute("aria-haspopup", "dialog");
});

test.each([
  { name: "significant", result: trendSignificant },
  { name: "not yet", result: trendNotYet },
  { name: "zero inside", result: trendZeroInside },
  { name: "no trend", result: trendNoTrend },
  { name: "too short", result: trendTooShort },
  { name: "no data", result: trendNoData },
])("should render no digit outside Num on the $name card", ({ result }) => {
  renderCard(result);

  expect(textOutsideNum(screen.getByRole("article"))).not.toMatch(/\d/);
});

test("should render no digit outside Num on a Korean card", () => {
  renderCard(trendSignificant, { locale: "ko" });

  expect(textOutsideNum(screen.getByRole("article"))).not.toMatch(/\d/);
});

test("should render only numbers that the downloaded result file holds", () => {
  renderCard(trendSignificant);

  expect(numbersMissingFrom(FILES[META.sourceUrl])).toEqual([]);
});

test("should open the provenance of a number with the request facts", async () => {
  renderCard(trendSignificant);

  await userEvent.click(
    screen.getByRole("button", { name: "Source of 3.3 days per decade" }),
  );

  expect(screen.getByRole("dialog")).toHaveTextContent(META.requestId ?? "");
});
