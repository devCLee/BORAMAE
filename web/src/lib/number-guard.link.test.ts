import { expect, test } from "vitest";

import type { TrendResult } from "@/contracts/types";
import { caseBoard, catalog, scanNearby, trendSignificant } from "@/test/fixtures";

import {
  buildAllowed,
  checkText,
  type GuardResult,
  type GuardState,
  linkedKeys,
} from "./number-guard";

const APP_STATE: GuardState = {
  area: { pin: { lat: 37.5665, lon: 126.978 }, radiusKm: 25 },
  window: { start: 1981, end: "latest" },
  cellPreview: null,
};
const BOARD: GuardResult = {
  kind: "caseboard",
  key: "85fb6675de50f5c9424c2aa158a0dbd6",
  body: caseBoard,
  meta: null,
};
const SCAN: GuardResult = {
  kind: "scan",
  key: "ec8994c5f690fd0c314da0e4ffbcd3b3",
  body: scanNearby,
  meta: null,
};
/** The trend that the board grows from. */
const FOCUS: GuardResult = { kind: "trend", key: caseBoard.focus_key, body: trendSignificant, meta: null };
/** The stored trend of the first scan hit (T2M at 0.31 °C per decade), on its own cell. */
const HIT_BODY: TrendResult = {
  ...trendSignificant,
  provenance: { ...trendSignificant.provenance, cells: [[253, 493]] },
};
const HIT: GuardResult = { kind: "trend", key: scanNearby.hits[0].trend_key, body: HIT_BODY, meta: null };

/** The provenance of the first linked number of the one kept sentence. */
function sourceOf(sentence: string, named: GuardResult[], linked: GuardResult[]) {
  const { kept } = checkText(sentence, buildAllowed(named, null, APP_STATE, catalog, linked));
  return kept[0].parts.find(({ source }) => source !== null)?.source;
}

test("should link a board number to the provenance of its focus trend", () => {
  expect(sourceOf("The first link has r 0.52.", [BOARD], [FOCUS])).toEqual({
    provenance: trendSignificant.provenance,
    footprint: trendSignificant.footprint,
    meta: null,
  });
});

test("should link a scan hit rate to the provenance of its stored trend", () => {
  expect(sourceOf("Air temperature rose 0.31 °C per decade.", [SCAN], [HIT])).toEqual({
    provenance: HIT_BODY.provenance,
    footprint: HIT_BODY.footprint,
    meta: null,
  });
});

test("should allow no value of a trend that only gives a link", () => {
  const allowed = buildAllowed([BOARD], null, APP_STATE, catalog, [FOCUS]);

  expect(checkText("Snow comes 3.3 days later per decade.", allowed).kept).toEqual([]);
});

test("should name the focus of a board and the trends of the scan hits as linked keys", () => {
  expect(linkedKeys([BOARD, SCAN])).toEqual([
    caseBoard.focus_key,
    ...scanNearby.hits.map(({ trend_key: key }) => key),
  ]);
});
