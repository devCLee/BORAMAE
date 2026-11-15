import { afterEach, expect, test, vi } from "vitest";

import { API_BASE } from "@/config/flags";
import { RETRY_DELAYS_MS, TIMEOUT_MS } from "@/config/timeouts";
import {
  HEADER_BYTES_FETCHED,
  HEADER_CACHE,
  HEADER_CONTAINING_CELL,
  HEADER_REQUEST_ID,
  HEADER_RESULT_KEY,
  HEADER_SERVER_TIMING,
  type ParseRequest,
} from "@/contracts/types";
import { fetchAnalysis, fetchParse, fetchResult } from "@/lib/fetch-layer";
import {
  hang,
  inTurn,
  jsonResponse,
  problemResponse,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { manifest, parseInput1Ko, trendSignificant } from "@/test/fixtures";

const KEY = manifest.cases[0].kinds.trend.key;
const S = manifest.cases[0].kinds.trend.s;
const TREND_URL = `${API_BASE}/api/v1/trend?s=${S}`;
const QUESTION: ParseRequest = {
  text: "서울 첫눈이 늦어지고 있나요?",
  lang: "ko",
  session_id: "0f8fad5b-d9cb-469f-a165-70867728950e",
};
const ALL_RETRIES_MS = RETRY_DELAYS_MS.reduce((sum, ms) => sum + ms, 0);
const RETRY_LIMIT = 3;

function trendAnswer(): Response {
  return jsonResponse(trendSignificant, {
    headers: {
      [HEADER_RESULT_KEY]: KEY,
      [HEADER_REQUEST_ID]: "req-7f3a9c",
      [HEADER_CACHE]: "miss",
      [HEADER_BYTES_FETCHED]: "87000000",
      [HEADER_SERVER_TIMING]: "read;dur=812.5, total;dur=901.2",
      [HEADER_CONTAINING_CELL]: "true",
    },
  });
}

function unavailable(): Response {
  return problemResponse(503, "power_unavailable");
}

function failNetwork(): never {
  throw new TypeError("Failed to fetch");
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("should ask the analysis path of the kind with the encoded spec", async () => {
  const calls = stubFetch(trendAnswer);

  await fetchAnalysis("live", "trend", S);

  expect(calls.map((call) => call.url)).toEqual([TREND_URL]);
});

test("should return the body of the answer", async () => {
  stubFetch(trendAnswer);

  const { body } = await fetchAnalysis("live", "trend", S);

  expect(body).toEqual(trendSignificant);
});

test("should turn the response headers into the request facts", async () => {
  stubFetch(trendAnswer);

  const { meta } = await fetchAnalysis("live", "trend", S);

  expect(meta).toEqual({
    resultKey: KEY,
    requestId: "req-7f3a9c",
    cache: "miss",
    bytesFetched: 87000000,
    serverTiming: "read;dur=812.5, total;dur=901.2",
    usedContainingCell: true,
    sourceUrl: `/r/trend/${KEY}.json`,
  });
});

test("should read an absent containing-cell header as false", async () => {
  stubFetch(() =>
    jsonResponse(trendSignificant, { headers: { [HEADER_RESULT_KEY]: KEY } }),
  );

  const { meta } = await fetchAnalysis("live", "trend", S);

  expect(meta.usedContainingCell).toBe(false);
});

test("should share one request between equal analysis requests in flight", async () => {
  const calls = stubFetch(trendAnswer);

  await Promise.all([
    fetchAnalysis("live", "trend", S),
    fetchAnalysis("live", "trend", S),
  ]);

  expect(calls).toHaveLength(1);
});

test("should read a stored result by its key", async () => {
  const calls = stubFetch(() => jsonResponse(trendSignificant));

  await fetchResult("live", "trend", KEY);

  expect(calls.map((call) => call.url)).toEqual([
    `${API_BASE}/r/trend/${KEY}.json`,
  ]);
});

test("should name the key of a stored result that carries no key header", async () => {
  stubFetch(() => jsonResponse(trendSignificant));

  const { meta } = await fetchResult("live", "trend", KEY);

  expect(meta.resultKey).toBe(KEY);
});

test.each([
  ["an HTTP 503 answer", unavailable],
  ["a network error", failNetwork],
])("should retry %s three times", async (_name, fail) => {
  vi.useFakeTimers();
  const calls = stubFetch(fail);
  const settled = fetchResult("live", "trend", KEY).catch(() => null);

  await vi.advanceTimersByTimeAsync(ALL_RETRIES_MS);
  await settled;

  expect(calls).toHaveLength(1 + RETRY_LIMIT);
});

test.each([
  ["an HTTP 503 answer", unavailable, "unavailable"],
  ["a network error", failNetwork, "network"],
])("should name %s after the last retry", async (_name, fail, code) => {
  vi.useFakeTimers();
  stubFetch(fail);
  const settled = fetchResult("live", "trend", KEY).catch(
    (error: unknown) => error,
  );

  await vi.advanceTimersByTimeAsync(ALL_RETRIES_MS);

  expect(await settled).toMatchObject({ name: "FetchError", code });
});

test("should return the answer that follows an HTTP 503 answer", async () => {
  vi.useFakeTimers();
  stubFetch(inTurn(unavailable, trendAnswer));
  const answered = fetchResult("live", "trend", KEY);

  await vi.advanceTimersByTimeAsync(RETRY_DELAYS_MS[0]);

  expect((await answered).body).toEqual(trendSignificant);
});

test.each([
  [400, "invalid_spec"],
  [404, "not_found"],
  [500, "internal"],
  [501, "not_built"],
])("should not retry an HTTP %i answer", async (status, problemCode) => {
  vi.useFakeTimers();
  const calls = stubFetch(() => problemResponse(status, problemCode));
  const settled = fetchResult("live", "trend", KEY).catch(() => null);

  await vi.advanceTimersByTimeAsync(ALL_RETRIES_MS);
  await settled;

  expect(calls).toHaveLength(1);
});

test("should name an error answer of the service server", async () => {
  stubFetch(() => problemResponse(400, "invalid_spec"));

  const error = await fetchAnalysis("live", "trend", S).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({ name: "FetchError", code: "server" });
});

test("should name an error answer with no problem body server", async () => {
  stubFetch(() => new Response("<html>Bad Gateway</html>", { status: 502 }));

  const error = await fetchAnalysis("live", "trend", S).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({ name: "FetchError", code: "server" });
});

test("should turn the problem area_too_large into the error zoom_in_or_pin", async () => {
  stubFetch(() => problemResponse(400, "area_too_large"));

  const error = await fetchAnalysis("live", "trend", S).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({ name: "FetchError", code: "zoom_in_or_pin" });
});

test("should reject an analysis answer that carries no result key", async () => {
  stubFetch(() => jsonResponse(trendSignificant));

  const error = await fetchAnalysis("live", "trend", S).catch(
    (caught: unknown) => caught,
  );

  expect(error).toMatchObject({ name: "FetchError", code: "server" });
});

test.each([
  ["an analysis", () => fetchAnalysis("live", "trend", S), TIMEOUT_MS.analysis],
  ["a stored result", () => fetchResult("live", "trend", KEY), TIMEOUT_MS.stored],
  ["a parse", () => fetchParse("live", QUESTION), TIMEOUT_MS.parse],
])(
  "should end %s with the error timeout when no answer comes",
  async (_name, send, timeoutMs) => {
    vi.useFakeTimers();
    stubFetch(hang);
    const settled = send().catch((error: unknown) => error);

    await vi.advanceTimersByTimeAsync(timeoutMs);

    expect(await settled).toMatchObject({ name: "FetchError", code: "timeout" });
  },
);

test("should not retry after a timeout", async () => {
  vi.useFakeTimers();
  const calls = stubFetch(hang);
  const settled = fetchAnalysis("live", "trend", S).catch(() => null);

  await vi.advanceTimersByTimeAsync(TIMEOUT_MS.analysis + ALL_RETRIES_MS);
  await settled;

  expect(calls).toHaveLength(1);
});

test("should post the question to the parse path", async () => {
  const calls = stubFetch(() => jsonResponse(parseInput1Ko));

  await fetchParse("live", QUESTION);

  expect(calls).toMatchObject([
    { url: `${API_BASE}/api/v1/parse`, method: "POST", body: QUESTION },
  ]);
});

test("should return the proposal of the parse answer", async () => {
  stubFetch(() => jsonResponse(parseInput1Ko));

  const proposal = await fetchParse("live", QUESTION);

  expect(proposal).toEqual(parseInput1Ko);
});

test("should abort the earlier parse request when a new one starts", async () => {
  const calls = stubFetch(inTurn(hang, () => jsonResponse(parseInput1Ko)));
  const earlier = fetchParse("live", QUESTION).catch(() => null);

  await fetchParse("live", QUESTION);
  await earlier;

  expect(calls[0].signal?.aborted).toBe(true);
});

test("should end the earlier parse with an abort and no typed error", async () => {
  stubFetch(inTurn(hang, () => jsonResponse(parseInput1Ko)));
  const earlier = fetchParse("live", QUESTION).catch((error: unknown) => error);

  await fetchParse("live", QUESTION);

  expect(await earlier).toMatchObject({ name: "AbortError" });
});
