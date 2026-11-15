import { expect, test } from "vitest";

import { caseBoard, catalog, trendSignificant } from "@/test/fixtures";

import {
  buildAllowed,
  buildAllowedFromText,
  buildCitations,
  checkText,
  type GuardResult,
  type GuardState,
  resolveCitations,
} from "./number-guard";

const APP_STATE: GuardState = {
  area: { pin: { lat: 37.5665, lon: 126.978 }, radiusKm: 25 },
  window: { start: 1981, end: "latest" },
  cellPreview: null,
};
const RESULTS: GuardResult[] = [
  { kind: "trend", key: "b5bae5463e95eff888bca78a896bf62a", body: trendSignificant, meta: null },
  { kind: "caseboard", key: "85fb6675de50f5c9424c2aa158a0dbd6", body: caseBoard, meta: null },
];
const ALLOWED = buildAllowed(RESULTS, null, APP_STATE, catalog);
const RATE = "Snow comes 3.3 days later per decade.";
const INVENTED = "It came 9.99 days late.";
const P_VALUE = "The p-value is 0.000025.";
const KO_RATE = "서울 첫눈은 10년당 3.3일씩 늦어졌어요.";
const KO_INTERVAL = "95% 신뢰구간은 2일에서 5일이에요.";
const KO_INVENTED = "1995년 첫눈은 99일 늦었어요.";
/** A cited news item (TR-F-034 acceptance 4). */
const ITEM = "Seoul saw 12 snow days in 2023, 3 fewer than in 2022.";

test("should withhold the sentence with an unmatched number and keep its neighbors", () => {
  const { kept } = checkText(`${RATE} ${INVENTED} ${P_VALUE}`, ALLOWED);

  expect(kept.map(({ text }) => text)).toEqual([RATE, P_VALUE]);
});

test("should list the sentence with an unmatched number as withheld", () => {
  const { withheld } = checkText(`${RATE} ${INVENTED} ${P_VALUE}`, ALLOWED);

  expect(withheld).toEqual([INVENTED]);
});

test("should keep no sentence when every sentence fails", () => {
  expect(checkText(`${INVENTED} It came 7.77 days late.`, ALLOWED).kept).toEqual([]);
});

test("should split and keep Korean sentences with digits and units", () => {
  const { kept } = checkText(`${KO_RATE} ${KO_INTERVAL} ${KO_INVENTED}`, ALLOWED);

  expect(kept.map(({ text }) => text)).toEqual([KO_RATE, KO_INTERVAL]);
});

test("should withhold the Korean sentence with an unmatched number", () => {
  const { withheld } = checkText(`${KO_RATE} ${KO_INTERVAL} ${KO_INVENTED}`, ALLOWED);

  expect(withheld).toEqual([KO_INVENTED]);
});

test("should drop a citation marker from a kept sentence", () => {
  const { kept } = checkText("Snow comes 3.3 days later [power_merra2].", ALLOWED);

  expect(kept[0].text).toBe("Snow comes 3.3 days later.");
});

test("should keep a citation marker after the period with its own sentence", () => {
  const { kept } = checkText(`${RATE} [power_merra2] ${P_VALUE}`, ALLOWED);

  expect(kept.map(({ text }) => text)).toEqual([RATE, P_VALUE]);
});

test("should link a matched rate to the provenance of its result", () => {
  const { kept } = checkText(RATE, ALLOWED);

  expect(kept[0].parts[1]).toEqual({
    text: "3.3",
    source: { provenance: trendSignificant.provenance, footprint: trendSignificant.footprint, meta: null },
  });
});

test.each([
  { id: "sen_slope", kind: "glossary" },
  { id: trendSignificant.provenance.dataset_id, kind: "dataset" },
  { id: "10.5555/boramae.sample.1", kind: "registry" },
  { id: "sample-link-3", kind: "registry" },
])("should resolve the citation $id as a $kind source", ({ id, kind }) => {
  expect(resolveCitations([id], buildCitations(RESULTS))[0].kind).toBe(kind);
});

test("should drop a citation ID that does not resolve", () => {
  const resolved = resolveCitations(["sen_slope", "no-such-source"], buildCitations(RESULTS));

  expect(resolved.map(({ id }) => id)).toEqual(["sen_slope"]);
});

test("should withhold a summary number that the cited item lacks", () => {
  const { withheld } = checkText(
    "Seoul saw 12 snow days in 2023. That was 40 fewer.",
    buildAllowedFromText(ITEM),
  );

  expect(withheld).toEqual(["That was 40 fewer."]);
});

test("should keep a summary sentence whose numbers the cited item holds", () => {
  const { kept } = checkText("Seoul had 3 fewer snow days in 2023.", buildAllowedFromText(ITEM));

  expect(kept).toHaveLength(1);
});
