import { expect, test } from "vitest";

import type { Catalog, DraftSpec } from "@/contracts/types";
import { catalog, scanNearby, trendSignificant } from "@/test/fixtures";

import {
  buildAllowed,
  checkText,
  extractNumbers,
  type GuardResult,
  type GuardState,
  maskIdentifiers,
} from "./number-guard";

const APP_STATE: GuardState = {
  area: { pin: { lat: 37.5665, lon: 126.978 }, radiusKm: 25 },
  window: { start: 1981, end: "latest" },
  cellPreview: null,
};
/** The scan holds a T2M hit at 0.31 °C per decade. */
const SCAN: GuardResult[] = [
  { kind: "scan", key: "ec8994c5f690fd0c314da0e4ffbcd3b3", body: scanNearby, meta: null },
];
/** A catalog that names T2M with a digit, as "2m 기온". */
const DIGIT_NAME_CATALOG: Catalog = {
  ...catalog,
  variables: catalog.variables.map((variable) =>
    variable.id === "T2M"
      ? { ...variable, name: { en: "2m air temperature", ko: "2m 기온" } }
      : variable,
  ),
};

function valuesIn(text: string): number[] {
  return extractNumbers(maskIdentifiers(text, [])).map(({ value }) => value);
}

test.each([
  "T2M_MAX",
  "WS10M",
  "CDD18_3",
  "CB-01",
  "doi:10.5555/boramae.sample.1",
  "https://power.larc.nasa.gov/docs/v2/",
  "[power_merra2_daily_temporal_utc]",
  "[1]",
])("should find no number in the identifier %s", (identifier) => {
  expect(valuesIn(`See ${identifier} here.`)).toEqual([]);
});

test.each([
  { lang: "en", sentence: "T2M rose 0.31 C per decade (MERRA-2)." },
  { lang: "ko", sentence: "2m 기온은 10년당 0.31 °C 올랐어요 (MERRA-2)." },
])(
  "should keep the $lang statement that names the variable and the dataset",
  ({ sentence }) => {
    const allowed = buildAllowed(SCAN, null, APP_STATE, DIGIT_NAME_CATALOG);

    expect(checkText(sentence, allowed).kept).toHaveLength(1);
  },
);

test.each(["Snow came on 2026.09.15.", "It rose 3.3.5 days."])(
  "should withhold '%s', whose digits read as no number",
  (sentence) => {
    const allowed = buildAllowed(SCAN, null, APP_STATE, catalog);

    expect(checkText(sentence, allowed).withheld).toEqual([sentence]);
  },
);

test.each([
  { text: "It fell -1.5 days.", values: [-1.5] },
  { text: "It rose +1.491 days.", values: [1.491] },
  { text: "It read 30,412,800 bytes.", values: [30412800] },
  { text: "Here p = .05 holds.", values: [0.05] },
  { text: "It uses a 95% interval.", values: [95] },
  { text: "The data run through 2026-09.", values: [2026, 9] },
  { text: "6,7,8월의 평균이에요.", values: [6, 7, 8] },
  { text: "１２일 늦었어요.", values: [12] },
])("should read $values from '$text'", ({ text, values }) => {
  expect(valuesIn(text)).toEqual(values);
});

test("should mark a number with a percent sign", () => {
  expect(extractNumbers("It uses a 95% interval.")[0].isPercent).toBe(true);
});

test("should count the decimals that the text shows", () => {
  expect(extractNumbers("It rose 0.310 days.")[0].decimals).toBe(3);
});

const TREND_KEY = "b5bae5463e95eff888bca78a896bf62a";
const TREND: GuardResult[] = [{ kind: "trend", key: TREND_KEY, body: trendSignificant, meta: null }];
/** The first-snow trend, with the version that the POWER stores give. */
const VERSIONED: GuardResult[] = [
  {
    kind: "trend",
    key: TREND_KEY,
    body: {
      ...trendSignificant,
      provenance: { ...trendSignificant.provenance, dataset_version: "10.0.0" },
    },
    meta: null,
  },
];
const PHOENIX_SPEC: DraftSpec = {
  var: "T2M_MAX",
  metric: { id: "threshold_days", threshold: "43.3", op: ">=", months: [5, 6, 7, 8, 9, 10] },
};
const CATALOG_IDS = [...catalog.variables, ...catalog.metrics].map(({ id }) => id);

function isKept(sentence: string, results: GuardResult[], spec: DraftSpec | null = null): boolean {
  return checkText(sentence, buildAllowed(results, spec, APP_STATE, catalog)).kept.length === 1;
}

test.each(CATALOG_IDS)("should find no number in the catalog ID %s", (id) => {
  expect(valuesIn(`See ${id} here.`)).toEqual([]);
});

test.each([
  "Water vapour (TQV) rose 0.42 kg/m^2 per decade.",
  "Cooling degree-days (CDD18_3) rose with T2M_MAX on board CB-01.",
  "The wettest day (Rx1day) and SPI-3 come from MERRA-2.",
])("should keep '%s', whose digits sit in IDs and unit powers", (sentence) => {
  expect(isKept(sentence, SCAN)).toBe(true);
});

test("should keep a sentence that cites the dataset version 10.0.0", () => {
  expect(isKept("The data are NASA POWER (MERRA-2), version 10.0.0.", VERSIONED)).toBe(true);
});

test.each([
  { sentence: "Highs of 110°F-115°F became more common.", results: [], spec: PHOENIX_SPEC },
  { sentence: "Highs ran 43.3 C-49 C.", results: [], spec: PHOENIX_SPEC },
  { sentence: "최고기온은 43.3°C-45°C 범위였어요.", results: [], spec: PHOENIX_SPEC },
  { sentence: "It ran 9 AM-11 AM.", results: [], spec: PHOENIX_SPEC },
  { sentence: "The Top7 variables changed.", results: SCAN, spec: null },
  { sentence: "It came x99 days late.", results: TREND, spec: null },
] satisfies { sentence: string; results: GuardResult[]; spec: DraftSpec | null }[])(
  "should withhold '$sentence', whose number touches a word",
  ({ sentence, results, spec }) => {
    expect(isKept(sentence, results, spec)).toBe(false);
  },
);

test.each([
  { sentence: "It rose 43.3 x 10^6 days.", results: [], spec: PHOENIX_SPEC },
  { sentence: "It rose 43.3 × 10⁶ days.", results: [], spec: PHOENIX_SPEC },
  { sentence: "It rose 3.3 million days.", results: TREND, spec: null },
  { sentence: "첫눈은 3.3만 일 늦어졌어요.", results: TREND, spec: null },
] satisfies { sentence: string; results: GuardResult[]; spec: DraftSpec | null }[])(
  "should withhold '$sentence', whose number a power or a multiplier scales",
  ({ sentence, results, spec }) => {
    expect(isKept(sentence, results, spec)).toBe(false);
  },
);

test("should read digits that an invisible character splits as one number", () => {
  expect(isKept("It came 9​9 days late.", TREND)).toBe(false);
});

test("should drop a citation marker in full-width brackets from a kept sentence", () => {
  const { kept } = checkText(
    "Snow came ［99］ days late.",
    buildAllowed(TREND, null, APP_STATE, catalog),
  );

  expect(kept[0].text).toBe("Snow came days late.");
});
