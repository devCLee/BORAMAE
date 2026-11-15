import { act, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { API_BASE } from "@/config/flags";
import { RETRY_DELAYS_MS } from "@/config/timeouts";
import { type DraftSpec, HEADER_RESULT_KEY } from "@/contracts/types";
import { jsonResponse, problemResponse, serve, stubFetch } from "@/lib/fetch-layer.stub";
import { actions, resetStore } from "@/state/store";
import { caseBoard, catalog, manifest, trendSignificant } from "@/test/fixtures";

import {
  BADGE,
  CATALOG_URL,
  renderAiText,
  serveFiles,
  TREND_KEY,
  TREND_URL,
  WITHHELD,
} from "./AiText.test-kit";

const BOARD_KEY = "85fb6675de50f5c9424c2aa158a0dbd6";
const BOARD_URL = `${API_BASE}/r/caseboard/${BOARD_KEY}.json`;
const BOARD_TEXT = "The board tests 5 links, and the first has r 0.52.";
const DOI = "10.5555/boramae.sample.1";
const FIRST_SNOW: DraftSpec = {
  var: "PRECSNO",
  metric: { id: "first_date", threshold: "0.1", op: ">=", season_start: "08-01" },
};
const DEMO = manifest.cases[0];
const DEMO_TREND_URL = `/demo/${DEMO.kinds.trend.file}`;
const DEMO_FILES = {
  "/demo/manifest.json": manifest,
  "/demo/catalog.json": catalog,
  [DEMO_TREND_URL]: trendSignificant,
};
const ALL_RETRIES_MS = RETRY_DELAYS_MS.reduce((sum, ms) => sum + ms, 0);
const SETTLE_MS = 100;

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function openTrendPanel(): void {
  actions.editDraft(FIRST_SNOW, "user");
  actions.setPin({ lat: 37.5665, lon: 126.978 }, "user");
  actions.confirmSpec();
  actions.openPanel("trend");
}

test("should read the result of an open panel without asking for it by key", async () => {
  const files = serve({ [CATALOG_URL]: catalog });
  const calls = stubFetch((call) =>
    call.url.includes("/api/v1/trend?")
      ? jsonResponse(trendSignificant, { headers: { [HEADER_RESULT_KEY]: TREND_KEY } })
      : files(call),
  );
  openTrendPanel();
  renderAiText();
  await screen.findAllByText(BADGE);

  expect(calls.map(({ url }) => url)).not.toContain(TREND_URL);
});

test("should load a result of another kind by its key", async () => {
  serveFiles({ [BOARD_URL]: caseBoard });
  const { container } = renderAiText({ text: BOARD_TEXT, resultKeys: [BOARD_KEY] });
  await screen.findAllByText(BADGE);

  expect(container).toHaveTextContent(BOARD_TEXT);
});

test("should link a board number to the trend of its focus that the answer does not name", async () => {
  serveFiles({ [BOARD_URL]: caseBoard, [TREND_URL]: trendSignificant });
  renderAiText({ text: BOARD_TEXT, resultKeys: [BOARD_KEY] });

  expect(await screen.findByRole("button", { name: "Source of 0.52" })).toBeInTheDocument();
});

test("should ask no other kind after the service is unavailable", async () => {
  vi.useFakeTimers();
  const calls = stubFetch(({ url }) =>
    url === CATALOG_URL ? jsonResponse(catalog) : problemResponse(503, "power_unavailable"),
  );
  renderAiText();
  await act(() => vi.advanceTimersByTimeAsync(ALL_RETRIES_MS + SETTLE_MS));
  vi.useRealTimers();
  await screen.findByText(WITHHELD);

  expect(calls.map(({ url }) => url)).not.toContain(`${API_BASE}/r/caseboard/${TREND_KEY}.json`);
});

test("should load a bundled result by its key in the demo", async () => {
  const calls = stubFetch(serve(DEMO_FILES));
  actions.setFetchSource("fixture");
  renderAiText();
  await screen.findAllByText(BADGE);

  expect(calls.map(({ url }) => url)).toContain(DEMO_TREND_URL);
});

test("should send no request outside the bundle in the demo", async () => {
  const calls = stubFetch(serve(DEMO_FILES));
  actions.setFetchSource("fixture");
  renderAiText();
  await screen.findAllByText(BADGE);

  expect(calls.filter(({ url }) => !url.startsWith("/demo/"))).toEqual([]);
});

test("should list a glossary citation as a source", async () => {
  serveFiles();
  renderAiText({ citations: ["sen_slope", "no-such-source"] });

  expect(await screen.findByRole("button", { name: "Sen slope" })).toBeInTheDocument();
});

test("should drop a citation that does not resolve", async () => {
  serveFiles();
  const { container } = renderAiText({ citations: ["sen_slope", "no-such-source"] });
  await screen.findAllByText(BADGE);

  expect(container).not.toHaveTextContent("no-such-source");
});

test("should list the dataset of a loaded result as a source", async () => {
  serveFiles();
  renderAiText({ citations: [trendSignificant.provenance.dataset_id] });

  expect(await screen.findByRole("list", { name: "Sources" })).toHaveTextContent(
    trendSignificant.provenance.dataset_id,
  );
});

test("should link a registry citation of a loaded board to its DOI", async () => {
  serveFiles({ [BOARD_URL]: caseBoard });
  renderAiText({ text: BOARD_TEXT, resultKeys: [BOARD_KEY], citations: [DOI] });

  expect(await screen.findByRole("link", { name: /Sample source 1/ })).toHaveAttribute(
    "href",
    `https://doi.org/${DOI}`,
  );
});
