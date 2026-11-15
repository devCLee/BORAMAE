import { expect, test } from "vitest";

import type { DraftSpec, TrendResult } from "@/contracts/types";
import {
  caseBoard,
  catalog,
  trendSignificant,
  trendZeroInside,
} from "@/test/fixtures";

import {
  buildAllowed,
  checkText,
  type GuardResult,
  type GuardState,
} from "./number-guard";

const TREND_KEY = "b5bae5463e95eff888bca78a896bf62a";
const BOARD_KEY = "85fb6675de50f5c9424c2aa158a0dbd6";
const APP_STATE: GuardState = {
  area: { pin: { lat: 37.5665, lon: 126.978 }, radiusKm: 25 },
  window: { start: 1981, end: "latest" },
  cellPreview: null,
};
const { stats } = trendSignificant;
/** A temperature trend whose Sen rate shows as 0.31 or 0.3. */
const RATE_TREND: TrendResult = {
  ...trendSignificant,
  unit: "C",
  rate_unit: "C",
  stats: { ...stats, rates: { ...stats.rates, sen: 0.3149 } },
};
/** A lower interval bound below zero, in days, which no unit converts. */
const NEGATIVE_TREND: TrendResult = {
  ...trendSignificant,
  stats: { ...stats, rates: { ...stats.rates, sen_ci_low: -1.5 } },
};
/** A soil-wetness trend: a share of 1 whose Sen rate shows as 1.2 percentage points. */
const SHARE_TREND: TrendResult = {
  ...trendSignificant,
  unit: "1",
  rate_unit: "percent_points",
  stats: { ...stats, rates: { ...stats.rates, sen: 0.012 } },
};
/** A p-value whose cut form (0.32, as the cards show it) differs from its rounded form. */
const CUT_TREND: TrendResult = {
  ...trendSignificant,
  stats: { ...stats, mk: { ...stats.mk, p: 0.328 } },
};
const PHOENIX_SPEC: DraftSpec = {
  var: "T2M_MAX",
  metric: {
    id: "threshold_days",
    threshold: "43.3",
    op: ">=",
    months: [5, 6, 7, 8, 9, 10],
  },
};
const FIRST_SNOW_SPEC: DraftSpec = {
  var: "PRECSNO",
  metric: { id: "first_date", threshold: "0.1", op: ">=", season_start: "08-01" },
};

function trend(body: TrendResult): GuardResult[] {
  return [{ kind: "trend", key: TREND_KEY, body, meta: null }];
}

/** True when the guard keeps the one sentence. */
function isKept(
  sentence: string,
  results: GuardResult[],
  spec: DraftSpec | null = null,
): boolean {
  const allowed = buildAllowed(results, spec, APP_STATE, catalog);
  return checkText(sentence, allowed).kept.length === 1;
}

test.each(["0.31", "0.3"])(
  "should pass %s for a rate of 0.3149 rounded to the decimals shown",
  (shown) => {
    expect(isKept(`The air warmed ${shown} °C per decade.`, trend(RATE_TREND))).toBe(
      true,
    );
  },
);

test.each(["0.32", "0.30", "0.4"])(
  "should withhold %s, one unit off in the last digit shown",
  (shown) => {
    expect(isKept(`The air warmed ${shown} °C per decade.`, trend(RATE_TREND))).toBe(
      false,
    );
  },
);

test.each(["43.3 °C", "110 °F"])(
  "should pass the threshold of 43.3 °C written as %s",
  (shown) => {
    expect(isKept(`It counts days at or above ${shown}.`, [], PHOENIX_SPEC)).toBe(
      true,
    );
  },
);

test("should convert a rate without the offset of a temperature", () => {
  expect(isKept("The air warmed 0.57 °F per decade.", trend(RATE_TREND))).toBe(true);
});

test("should withhold a rate shifted by the offset of a temperature", () => {
  expect(isKept("The air warmed 32.6 °F per decade.", trend(RATE_TREND))).toBe(false);
});

test.each([
  "The test uses the 0.05 level.",
  "The interval is a 95% interval.",
  "A verdict needs 20 years.",
])("should pass the method constant in '%s'", (sentence) => {
  expect(isKept(sentence, trend(trendZeroInside))).toBe(true);
});

test("should withhold a series value that no card shows", () => {
  expect(isKept("The first snow came on day 110.", trend(trendSignificant))).toBe(
    false,
  );
});

test.each([
  { sentence: "Snow came late in 1995.", expected: true },
  { sentence: "Snow will come late in 2031.", expected: false },
  { sentence: "Snow reached 1995 mm.", expected: false },
])("should judge the year in '$sentence' as $expected", ({ sentence, expected }) => {
  expect(isKept(sentence, trend(trendSignificant))).toBe(expected);
});

test.each([
  { shown: "-1.5", expected: true },
  { shown: "1.5", expected: true },
  { shown: "+1.5", expected: false },
])(
  "should judge $shown for a bound of -1.5 as $expected",
  ({ shown, expected }) => {
    expect(isKept(`The interval starts at ${shown} days.`, trend(NEGATIVE_TREND))).toBe(
      expected,
    );
  },
);

test.each([
  { shown: "0.32", expected: true },
  { shown: "0.33", expected: true },
  { shown: "0.31", expected: false },
  { shown: "0.34", expected: false },
])(
  "should judge $shown for a p-value of 0.328 as $expected",
  ({ shown, expected }) => {
    expect(isKept(`The p-value is ${shown}.`, trend(CUT_TREND))).toBe(expected);
  },
);

test.each([
  "The boundary layer rose 2000 m.",
  "The boundary layer rose 2000m.",
  "The top sits at 1995 meters.",
  "Seoul got 2012 millimeters of rain.",
  "It lasted 2000 hours.",
  "It happened 2000 times.",
  "The area holds 2000 cells.",
  "경계층은 2000 미터 올랐어요.",
  "2000시간 동안 이어졌어요.",
  "2000번 일어났어요.",
])("should withhold the 4-digit value with a unit in '%s'", (sentence) => {
  expect(isKept(sentence, trend(trendSignificant))).toBe(false);
});

test("should keep a year before a word that starts with m", () => {
  expect(isKept("In 2000 more snow fell.", trend(trendSignificant))).toBe(true);
});

test.each([
  "The interval is a 95 percent interval.",
  "It is a 95-percent interval.",
  "신뢰구간은 95퍼센트예요.",
])("should pass the constant 95 in '%s'", (sentence) => {
  expect(isKept(sentence, trend(trendZeroInside))).toBe(true);
});

test.each([
  { shown: "1.2 percentage points", expected: true },
  { shown: "1.2%", expected: true },
  { shown: "0.012%", expected: false },
])("should judge $shown for a share rate of 0.012 as $expected", ({ shown, expected }) => {
  expect(isKept(`Soil wetness rose ${shown} per decade.`, trend(SHARE_TREND))).toBe(expected);
});

test.each([
  {
    name: "a link r of 0.52 as 52%",
    sentence: "The first link explains 52% of it.",
    results: [{ kind: "caseboard", key: BOARD_KEY, body: caseBoard, meta: null }],
  },
  {
    name: "a level of 0.95 as 0.95%",
    sentence: "It is a 0.95% interval.",
    results: trend(trendZeroInside),
  },
] satisfies { name: string; sentence: string; results: GuardResult[] }[])(
  "should withhold $name",
  ({ sentence, results }) => {
    expect(isKept(sentence, results)).toBe(false);
  },
);

test.each([
  {
    name: "months of the spec",
    sentence: "It counts days from month 5 to month 10.",
    results: [],
    spec: PHOENIX_SPEC,
  },
  {
    name: "season start day and month",
    sentence: "The season starts on day 1 of month 8.",
    results: [],
    spec: FIRST_SNOW_SPEC,
  },
  {
    name: "list size of a board",
    sentence: "The board tests 5 links.",
    results: [{ kind: "caseboard", key: BOARD_KEY, body: caseBoard, meta: null }],
    spec: null,
  },
] satisfies { name: string; sentence: string; results: GuardResult[]; spec: DraftSpec | null }[])(
  "should pass the $name",
  ({ sentence, results, spec }) => {
    expect(isKept(sentence, results, spec)).toBe(true);
  },
);
