import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { API_BASE } from "@/config/flags";
import {
  type DraftSpec,
  HEADER_RESULT_KEY,
  type RequestSpec,
} from "@/contracts/types";
import { useCaseBoard, useScan, useTrend } from "@/hooks/queries";
import {
  jsonResponse,
  problemResponse,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { MARK_ANALYSIS_STARTED } from "@/lib/perf";
import { encodeSpec } from "@/lib/spec-codec";
import { manifest, trendSignificant } from "@/test/fixtures";
import goldenVectors from "@content/golden/request-spec.json";

import { runAnalysis, sendAnalysis } from "./run-analysis";
import { actions, getState, resetStore } from "./store";
import type { MapView, PanelKind } from "./types";

/** The request of demo case 1: first snow in Seoul, 25 km, the full record. */
const SNOW_S = goldenVectors[0].s;
/** T2M annual mean over a map view, 1991 to 2020, with no pin. */
const MAP_VIEW_S = goldenVectors[6].s;
const SNOW: DraftSpec = {
  var: "PRECSNO",
  metric: {
    id: "first_date",
    op: ">=",
    season_start: "08-01",
    threshold: "0.1",
  },
};
const SEOUL = { lat: 37.5665, lon: 126.978 };
const JEJU = { lat: 33.4996, lon: 126.5312 };
const KOREA_VIEW: MapView = {
  center: { lat: 35.875, lon: 128.1875 },
  zoom: 6,
  bounds: [124.5, 33, 131.875, 38.75],
};
const LAST_30_YEARS = { start: 1991, end: 2020 };
const RESULT_KEY = manifest.cases[0].kinds.trend.key;

function answer(): Response {
  return jsonResponse(trendSignificant, {
    headers: { [HEADER_RESULT_KEY]: RESULT_KEY },
  });
}

function confirmSeoulSnow(): void {
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
}

function snowUrl(kind: PanelKind, window = LAST_30_YEARS): string {
  const spec: RequestSpec = {
    v: 1,
    kind,
    var: SNOW.var,
    metric: SNOW.metric,
    area: { ...SEOUL, radius_km: 25 },
    window,
  };
  return `${API_BASE}/api/v1/${kind}?s=${encodeSpec(spec)}`;
}

function renderPanels() {
  return renderHook(
    () => ({ trend: useTrend(), caseboard: useCaseBoard(), scan: useScan() }),
    { wrapper: Providers },
  );
}

beforeEach(() => {
  performance.clearMarks();
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should send no request for an unconfirmed spec", async () => {
  const calls = stubFetch(answer);
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");

  await runAnalysis("trend");

  expect(calls).toHaveLength(0);
});

test("should refuse an unconfirmed spec", async () => {
  stubFetch(answer);
  actions.editDraft(SNOW, "user");

  const outcome = await runAnalysis("trend");

  expect(outcome).toEqual({ status: "refused" });
});

test("should send the confirmed spec with a circle from the pin and the radius", async () => {
  const calls = stubFetch(answer);
  confirmSeoulSnow();

  await runAnalysis("trend");

  expect(calls.map((call) => call.url)).toEqual([
    `${API_BASE}/api/v1/trend?s=${SNOW_S}`,
  ]);
});

test("should send the bounds of the map view as a bbox when no pin is set", async () => {
  const calls = stubFetch(answer);
  actions.editDraft({ var: "T2M", metric: { id: "annual_mean" } }, "user");
  actions.setWindow(LAST_30_YEARS, "user");
  actions.setMapView(KOREA_VIEW);
  actions.confirmSpec();

  await runAnalysis("trend");

  expect(calls.map((call) => call.url)).toEqual([
    `${API_BASE}/api/v1/trend?s=${MAP_VIEW_S}`,
  ]);
});

test("should send no request with no pin and no map view", async () => {
  const calls = stubFetch(answer);
  actions.editDraft(SNOW, "user");
  actions.confirmSpec();

  await runAnalysis("trend");

  expect(calls).toHaveLength(0);
});

test.each([
  ["moves the pin", () => actions.setPin(JEJU, "user")],
  ["changes the radius", () => actions.setRadius(100, "user")],
  ["edits the draft", () => actions.editDraft({ var: "T2M" }, "user")],
])("should send no request after the user %s", async (_name, change) => {
  const calls = stubFetch(answer);
  confirmSeoulSnow();
  change();

  await runAnalysis("trend");

  expect(calls).toHaveLength(0);
});

test("should return the result with its request facts", async () => {
  stubFetch(answer);
  confirmSeoulSnow();

  const outcome = await runAnalysis("trend");

  expect(outcome).toMatchObject({
    status: "done",
    body: trendSignificant,
    meta: { resultKey: RESULT_KEY },
  });
});

test("should turn the problem area_too_large into the error zoom_in_or_pin", async () => {
  stubFetch(() => problemResponse(400, "area_too_large"));
  confirmSeoulSnow();

  const outcome = await runAnalysis("trend");

  expect(outcome).toMatchObject({
    status: "failed",
    error: { name: "FetchError", code: "zoom_in_or_pin" },
  });
});

test("should set the mark analysis-started", async () => {
  stubFetch(answer);
  confirmSeoulSnow();

  await runAnalysis("trend");

  expect(performance.getEntriesByName(MARK_ANALYSIS_STARTED)).toHaveLength(1);
});

test("should open the panel of the kind", async () => {
  stubFetch(answer);
  confirmSeoulSnow();

  await runAnalysis("caseboard");

  expect(getState().openPanels).toEqual(["caseboard"]);
});

test("should send nothing for a request that is not the confirmed one", async () => {
  const calls = stubFetch(answer);
  confirmSeoulSnow();

  await sendAnalysis("trend", MAP_VIEW_S).catch(() => null);

  expect(calls).toHaveLength(0);
});

test("should send no request from a panel of an unconfirmed spec", () => {
  const calls = stubFetch(answer);
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  actions.openPanel("trend");

  renderPanels();

  expect(calls).toHaveLength(0);
});

test("should send one request for each open panel of a confirmed spec", () => {
  const calls = stubFetch(answer);
  confirmSeoulSnow();
  actions.setWindow(LAST_30_YEARS, "user");
  actions.openPanel("trend");
  actions.openPanel("scan");

  renderPanels();

  expect(calls.map((call) => call.url)).toEqual([
    snowUrl("trend"),
    snowUrl("scan"),
  ]);
});

test("should send one new request for each open panel when the user changes the window", () => {
  const calls = stubFetch(answer);
  confirmSeoulSnow();
  actions.openPanel("trend");
  actions.openPanel("caseboard");
  renderPanels();
  const sentBefore = calls.length;

  act(() => actions.setWindow(LAST_30_YEARS, "user"));

  expect(calls.slice(sentBefore).map((call) => call.url)).toEqual([
    snowUrl("trend"),
    snowUrl("caseboard"),
  ]);
});

test("should send one request when Confirm runs the analysis under an open panel", () => {
  const calls = stubFetch(answer);
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  renderPanels();

  act(() => {
    actions.confirmSpec();
    void runAnalysis("trend");
  });

  expect(calls).toHaveLength(1);
});

test("should send no request after a panel edit clears the confirmation", () => {
  const calls = stubFetch(answer);
  confirmSeoulSnow();
  actions.openPanel("trend");
  renderPanels();
  const sentBefore = calls.length;

  act(() => actions.setRadius(100, "user"));

  expect(calls).toHaveLength(sentBefore);
});
