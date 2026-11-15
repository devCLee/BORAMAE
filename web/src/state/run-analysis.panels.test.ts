import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { type DraftSpec, HEADER_RESULT_KEY } from "@/contracts/types";
import { useTrend } from "@/hooks/queries";
import {
  jsonResponse,
  problemResponse,
  serve,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { manifest, trendSignificant } from "@/test/fixtures";

import { actions, getState, resetStore } from "./store";

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
const LAST_30_YEARS = { start: 1991, end: 2020 };
const DEMO_CASE = manifest.cases[0];
const DEMO_TREND = DEMO_CASE.kinds.trend;
const RESULT_KEY = DEMO_TREND.key;
const BUNDLE = {
  "/demo/manifest.json": manifest,
  [`/demo/${DEMO_TREND.file}`]: trendSignificant,
};

function answer(): Response {
  return jsonResponse(trendSignificant, {
    headers: { [HEADER_RESULT_KEY]: RESULT_KEY },
  });
}

/** The state after Confirm on the first-snow question: the trend panel is open. */
function openSeoulSnowTrend(): void {
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
  actions.openPanel("trend");
}

function renderTrend() {
  return renderHook(() => useTrend(), { wrapper: Providers });
}

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should give a panel the result with its request facts", async () => {
  stubFetch(answer);
  openSeoulSnowTrend();

  const { result } = renderTrend();

  await waitFor(() =>
    expect(result.current.data).toMatchObject({
      body: trendSignificant,
      meta: { resultKey: RESULT_KEY },
    }),
  );
});

test("should keep the request facts of the shown result in the store", async () => {
  stubFetch(answer);
  openSeoulSnowTrend();

  renderTrend();

  await waitFor(() =>
    expect(getState().meta.trend?.resultKey).toBe(RESULT_KEY),
  );
});

test("should give a panel the typed error of a failed request", async () => {
  stubFetch(() => problemResponse(400, "area_too_large"));
  openSeoulSnowTrend();

  const { result } = renderTrend();

  await waitFor(() =>
    expect(result.current.error?.code).toBe("zoom_in_or_pin"),
  );
});

test("should show the bundled result of a demo case from the request that the store builds", async () => {
  stubFetch(serve(BUNDLE));
  actions.startDemo(DEMO_CASE.case_id);
  openSeoulSnowTrend();

  const { result } = renderTrend();

  await waitFor(() =>
    expect(result.current.data?.meta.sourceUrl).toBe(
      `/demo/${DEMO_TREND.file}`,
    ),
  );
});

test("should show the offline state when a demo viewer moves the window", async () => {
  stubFetch(serve(BUNDLE));
  actions.startDemo(DEMO_CASE.case_id);
  openSeoulSnowTrend();
  const { result } = renderTrend();

  act(() => actions.setWindow(LAST_30_YEARS, "user"));

  await waitFor(() =>
    expect(result.current.error?.code).toBe("not_in_offline_demo"),
  );
});
