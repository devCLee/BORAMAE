import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { API_BASE } from "@/config/flags";
import type { ParseProposal } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import { resetStore } from "@/state/store";
import { parseInput1En, trendNoTrend } from "@/test/fixtures";

import {
  analysisKinds,
  areasOf,
  clickMap,
  confirmAgain,
  MAP_VIEW_AREA,
  moveWindowStart,
  openJudgeLink,
  urlsOf,
  urlsWith,
  walkToBoard,
  walkToConfirm,
  walkToVerdict,
  widenRadius,
  windowsOf,
} from "./app-test-kit";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));

// The gate on the root route uses the Next.js router (TESTING.md).
vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  useRouter: () => router,
}));
// The language switch and the demo player use the next-intl router of the locale routes.
vi.mock("@/i18n/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/i18n/navigation")>()),
  useRouter: () => router,
  usePathname: () => "/",
}));

const EN = messages.en;
/** One ArrowRight on the start thumb moves the full record one year later. */
const LATER_WINDOW = { start: 1982, end: "latest" };
/** One ArrowRight on the radius thumb moves the default 25 km one step up. */
const WIDER_RADIUS_KM = 26;
const JEJU = { lat: 33.4996, lon: 126.5312 };
/** The bucket of the POWER Zarr stores (STORE_URL in api/boramae/power/reader.py). */
const POWER_BUCKET = "nasa-power";
const CATALOG_URL = `${API_BASE}/meta/catalog.json`;
const PLACELESS: ParseProposal = {
  ...parseInput1En,
  spec: { ...parseInput1En.spec, place: null },
};
const RULES: ParseProposal = { ...parseInput1En, source: "rules" };

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should send no analysis request between the parse answer and Confirm", async () => {
  const calls = await walkToConfirm();

  expect(analysisKinds(calls)).toEqual([]);
});

test("should ask for the trend of the new window when the window moves with the board open", async () => {
  const calls = await walkToBoard();

  await moveWindowStart();

  await waitFor(() =>
    expect(windowsOf(calls, "trend")).toContainEqual(LATER_WINDOW),
  );
});

test("should ask for the board of the new window when the window moves with the board open", async () => {
  const calls = await walkToBoard();

  await moveWindowStart();

  await waitFor(() =>
    expect(windowsOf(calls, "caseboard")).toContainEqual(LATER_WINDOW),
  );
});

test("should keep the spec confirmed when the window moves", async () => {
  await walkToBoard();

  await moveWindowStart();

  expect(screen.getByText(EN.rail.read_back.confirmed)).toBeInTheDocument();
});

test("should send no request after a pin move on a confirmed spec", async () => {
  const calls = await walkToBoard();

  const sent = await clickMap(calls, JEJU);

  expect(urlsOf(sent)).toEqual([]);
});

test("should ask for the trend of the moved pin once Confirm is pressed again", async () => {
  const calls = await walkToBoard();
  await clickMap(calls, JEJU);

  const sent = await confirmAgain(calls);

  expect(areasOf(sent, "trend")).toContainEqual({ ...JEJU, radius_km: 25 });
});

test("should send no request after a radius change on a confirmed spec", async () => {
  const calls = await walkToBoard();

  const sent = await widenRadius(calls);

  expect(urlsOf(sent)).toEqual([]);
});

test("should ask for the trend of the new radius once Confirm is pressed again", async () => {
  const calls = await walkToBoard();
  await widenRadius(calls);

  const sent = await confirmAgain(calls);

  expect(areasOf(sent, "trend")).toContainEqual(
    expect.objectContaining({ radius_km: WIDER_RADIUS_KM }),
  );
});

test("should send the map view as the area when no place is pinned", async () => {
  const calls = await walkToVerdict({ proposal: PLACELESS, isPinned: false });

  expect(areasOf(calls, "trend")).toContainEqual(MAP_VIEW_AREA);
});

test("should send no request to the POWER bucket", async () => {
  const calls = await walkToBoard();

  expect(urlsWith(calls, POWER_BUCKET)).toEqual([]);
});

test("should reach the verdict with a rules proposal while the LLM is off", async () => {
  await walkToVerdict({ proposal: RULES });

  expect(
    await screen.findByText(EN.verdict.sentences.significant_rise),
  ).toBeInTheDocument();
});

test("should read no catalog from the API at the judge link", async () => {
  const calls = await openJudgeLink("first-snow-seoul", "ko", trendNoTrend);

  expect(urlsWith(calls, CATALOG_URL)).toEqual([]);
});
