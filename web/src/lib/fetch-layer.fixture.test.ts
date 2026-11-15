import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { API_BASE } from "@/config/flags";
import { TIMEOUT_MS } from "@/config/timeouts";
import type { ParseRequest } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";
import {
  fetchAnalysis,
  fetchCatalog,
  fetchDemoFile,
  fetchManifest,
  fetchParse,
  fetchResult,
} from "@/lib/fetch-layer";
import {
  hang,
  inTurn,
  problemResponse,
  serve,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { actions, resetStore } from "@/state/store";
import {
  caseBoard,
  catalog,
  manifest,
  parseInput1En,
  parseInput1Ko,
  trendNotYet,
  trendSignificant,
} from "@/test/fixtures";
import goldenVectors from "@content/golden/request-spec.json";

const MANIFEST_URL = "/demo/manifest.json";
const CATALOG_URL = `${API_BASE}/meta/catalog.json`;
const CASE = manifest.cases[0];
const TREND = CASE.kinds.trend;
/** The trend of a board node: the manifest lists it by key only. */
const NODE_KEY = Object.keys(CASE.referenced.trend)[0];
const NODE_FILE = CASE.referenced.trend[NODE_KEY];
/** A valid request that no demo case holds: another place and another window. */
const OTHER_S = goldenVectors[7].s;
const OTHER_KEY = "0".repeat(32);
const BUNDLED_CATALOG = { ...catalog, version: "bundled" };
const BUNDLE = {
  [MANIFEST_URL]: manifest,
  "/demo/catalog.json": BUNDLED_CATALOG,
  [`/demo/${TREND.file}`]: trendSignificant,
  [`/demo/${CASE.kinds.caseboard.file}`]: caseBoard,
  [`/demo/${NODE_FILE}`]: trendNotYet,
  [`/demo/${CASE.parse.ko}`]: parseInput1Ko,
  [`/demo/${CASE.parse.en}`]: parseInput1En,
};
const QUESTION: ParseRequest = {
  text: "Is the first snow in Seoul coming later?",
  lang: "en",
  session_id: "0f8fad5b-d9cb-469f-a165-70867728950e",
};

function unavailable(): Response {
  return problemResponse(503, "power_unavailable");
}

function notFound(): Response {
  return problemResponse(404, "not_found");
}

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("should answer a request whose encoded spec equals a manifest entry", async () => {
  stubFetch(serve(BUNDLE));

  const { body } = await fetchAnalysis("fixture", "trend", TREND.s);

  expect(body).toEqual(trendSignificant);
});

test("should name the bundled file as the source of the answer", async () => {
  stubFetch(serve(BUNDLE));

  const { meta } = await fetchAnalysis("fixture", "trend", TREND.s);

  expect(meta).toEqual({
    resultKey: TREND.key,
    requestId: null,
    cache: null,
    bytesFetched: null,
    serverTiming: null,
    usedContainingCell: false,
    sourceUrl: `/demo/${TREND.file}`,
  });
});

test("should read only bundled files for a manifest entry", async () => {
  const calls = stubFetch(serve(BUNDLE));

  await fetchAnalysis("fixture", "trend", TREND.s);

  expect(calls.map((call) => call.url)).toEqual([
    MANIFEST_URL,
    `/demo/${TREND.file}`,
  ]);
});

test.each([
  ["a spec outside the manifest", "trend", OTHER_S],
  ["a manifest spec under another kind", "scan", TREND.s],
] as const)("should reject %s as not in the offline demo", async (_name, kind, s) => {
  stubFetch(serve(BUNDLE));

  const error = await fetchAnalysis("fixture", kind, s).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({
    name: "FetchError",
    code: "not_in_offline_demo",
  });
});

test("should send no request for a spec outside the manifest", async () => {
  const calls = stubFetch(serve(BUNDLE));

  await fetchAnalysis("fixture", "trend", OTHER_S).catch(() => null);

  expect(calls.map((call) => call.url)).toEqual([MANIFEST_URL]);
});

test("should answer a stored result whose key a manifest entry holds", async () => {
  stubFetch(serve(BUNDLE));

  const { body } = await fetchResult("fixture", "trend", TREND.key);

  expect(body).toEqual(trendSignificant);
});

test("should answer a stored result that the manifest lists by key only", async () => {
  stubFetch(serve(BUNDLE));

  const { meta } = await fetchResult("fixture", "trend", NODE_KEY);

  expect(meta).toMatchObject({
    resultKey: NODE_KEY,
    sourceUrl: `/demo/${NODE_FILE}`,
  });
});

test("should reject a stored result with a key outside the manifest", async () => {
  stubFetch(serve(BUNDLE));

  const error = await fetchResult("fixture", "trend", OTHER_KEY).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({
    name: "FetchError",
    code: "not_in_offline_demo",
  });
});

test("should load the manifest one time", async () => {
  const calls = stubFetch(serve(BUNDLE));

  await fetchAnalysis("fixture", "trend", TREND.s);
  await fetchResult("fixture", "trend", NODE_KEY);

  expect(calls.filter((call) => call.url === MANIFEST_URL)).toHaveLength(1);
});

test("should load the manifest again after a failed load", async () => {
  stubFetch(inTurn(notFound, serve(BUNDLE)));
  await fetchManifest().catch(() => null);

  const loaded = await fetchManifest();

  expect(loaded).toEqual(manifest);
});

test("should read a bundled file by its manifest path", async () => {
  stubFetch(serve(BUNDLE));

  const proposal = await fetchDemoFile(CASE.parse.ko);

  expect(proposal).toEqual(parseInput1Ko);
});

test.each([
  ["en", parseInput1En],
  ["ko", parseInput1Ko],
] as const)(
  "should answer a parse request in %s from the demo case",
  async (lang, proposal) => {
    stubFetch(serve(BUNDLE));

    const answered = await fetchParse(
      "fixture",
      { ...QUESTION, lang },
      CASE.case_id,
    );

    expect(answered).toEqual(proposal);
  },
);

test.each([
  ["no demo case", null],
  ["a case outside the manifest", "no-such-case"],
])("should reject a parse request with %s", async (_name, caseId) => {
  stubFetch(serve(BUNDLE));

  const error = await fetchParse("fixture", QUESTION, caseId).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({
    name: "FetchError",
    code: "not_in_offline_demo",
  });
});

test("should read the catalog of the bundle", async () => {
  stubFetch(serve(BUNDLE));

  const loaded = await fetchCatalog("fixture");

  expect(loaded).toEqual(BUNDLED_CATALOG);
});

test("should read the live catalog from the service", async () => {
  const calls = stubFetch(serve({ [CATALOG_URL]: catalog }));

  await fetchCatalog("live");

  expect(calls.map((call) => call.url)).toEqual([CATALOG_URL]);
});

test("should fall back to the bundled catalog when the live request fails", async () => {
  stubFetch(serve(BUNDLE));

  const loaded = await fetchCatalog("live");

  expect(loaded).toEqual(BUNDLED_CATALOG);
});

test("should fall back to the bundled catalog when the service gives no answer", async () => {
  vi.useFakeTimers();
  stubFetch(inTurn(hang, serve(BUNDLE)));
  const loading = fetchCatalog("live");

  await vi.advanceTimersByTimeAsync(TIMEOUT_MS.meta);

  expect(await loading).toEqual(BUNDLED_CATALOG);
});

test("should not retry the live catalog before the fallback", async () => {
  const calls = stubFetch(inTurn(unavailable, serve(BUNDLE)));

  await fetchCatalog("live");

  expect(calls.map((call) => call.url)).toEqual([
    CATALOG_URL,
    MANIFEST_URL,
    "/demo/catalog.json",
  ]);
});

test("should name the live error when the bundle holds no catalog either", async () => {
  stubFetch(inTurn(unavailable, notFound));

  const error = await fetchCatalog("live").catch((caught: unknown) => caught);

  expect(error).toMatchObject({ name: "FetchError", code: "unavailable" });
});

test("should read the catalog again when the source changes", async () => {
  stubFetch(serve({ ...BUNDLE, [CATALOG_URL]: catalog }));
  const { result } = renderHook(() => useCatalog(), { wrapper: Providers });

  act(() => actions.setFetchSource("fixture"));

  await waitFor(() => expect(result.current.data).toEqual(BUNDLED_CATALOG));
});
