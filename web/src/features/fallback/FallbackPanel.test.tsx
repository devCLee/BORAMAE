import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { hang } from "@/lib/fetch-layer.stub";
import { getState, resetStore } from "@/state/store";
import {
  scanNearby,
  scanNote,
  trendNoData,
  trendNoTrend,
  trendNotYet,
  trendSignificant,
  trendTooShort,
  trendZeroInside,
} from "@/test/fixtures";

import {
  answer,
  CHECKED,
  failure,
  findList,
  HITS,
  openFocusTrend,
  renderPanel,
  SCAN_PATH,
  serve,
  showScan,
  YEARS,
} from "./fallback-test-kit";

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test.each([
  { name: "before a result", trend: hang, scan: hang },
  { name: "while the scan loads", trend: answer(trendNoTrend), scan: hang },
  { name: "after the scan failed", trend: answer(trendNoTrend), scan: failure },
  { name: "with a scan result", trend: answer(trendNoTrend), scan: answer(scanNearby) },
  { name: "with nothing found", trend: answer(trendNoTrend), scan: answer(scanNote) },
  { name: "for a significant verdict", trend: answer(trendSignificant), scan: hang },
])("should keep the slot test ID $name", async ({ trend, scan }) => {
  serve(trend, scan);
  openFocusTrend();
  renderPanel();

  expect(await screen.findByTestId("slot-fallback")).toBeInTheDocument();
});

test.each([
  { name: "not yet", result: trendNotYet },
  { name: "zero inside", result: trendZeroInside },
  { name: "no trend", result: trendNoTrend },
])("should request the scan for a $name verdict", async ({ result }) => {
  const calls = serve(answer(result));
  openFocusTrend();
  renderPanel();

  await waitFor(() => expect(calls.some(({ url }) => url.includes(SCAN_PATH))).toBe(true));
});

test.each([
  { name: "significant", result: trendSignificant },
  { name: "too-short", result: trendTooShort },
  { name: "no-data", result: trendNoData },
])("should not open the scan for a $name result", async ({ result }) => {
  serve(answer(result));
  openFocusTrend();
  renderPanel();
  await waitFor(() => expect(getState().meta.trend).not.toBeNull());

  expect(getState().openPanels).toEqual(["trend"]);
});

test("should show a skeleton while the scan loads", async () => {
  serve(answer(trendNoTrend));
  openFocusTrend();
  renderPanel();

  expect(
    await screen.findByRole("status", { name: "Scanning other variables and nearby areas" }),
  ).toBeInTheDocument();
});

test("should offer a retry when the scan fails", async () => {
  serve(answer(trendNoTrend), failure);
  openFocusTrend();
  renderPanel();

  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("should show the scan after a retry", async () => {
  serve(answer(trendNoTrend), failure, answer(scanNearby));
  openFocusTrend();
  renderPanel();

  await userEvent.click(await screen.findByRole("button", { name: "Try again" }));

  expect(await findList(HITS)).toBeInTheDocument();
});

test("should show the years still needed", async () => {
  await showScan(scanNearby);

  expect(
    within(screen.getByRole("region", { name: YEARS })).getByText(
      String(trendNoTrend.years_needed?.more),
    ),
  ).toBeInTheDocument();
});

test("should call the years needed a detection estimate", async () => {
  await showScan(scanNearby);

  expect(
    within(screen.getByRole("region", { name: YEARS })).getByText(
      "A detection estimate, not a forecast.",
    ),
  ).toBeInTheDocument();
});

test("should show the fixed sentence when the record is long enough", async () => {
  await showScan(scanNearby, trendZeroInside);

  expect(
    screen.getByText(
      "The record is already as long as the estimate needs, so more years alone may not settle it.",
    ),
  ).toBeInTheDocument();
});

test("should show no number when the record is long enough", async () => {
  await showScan(scanNearby, trendZeroInside);

  expect(screen.getByRole("region", { name: YEARS }).textContent).not.toMatch(/\d/);
});

test("should say that nothing was found", async () => {
  await showScan(scanNote);

  expect(screen.getByText("Nothing found")).toBeInTheDocument();
});

test("should list every variable that the scan checked", async () => {
  await showScan(scanNote);

  expect(within(await findList(CHECKED)).getAllByRole("listitem")).toHaveLength(
    scanNote.checked.length,
  );
});

test("should give the reason of a variable that was not testable", async () => {
  await showScan(scanNote);
  const list = await findList(CHECKED);

  expect(
    within(list).getByRole("button", { name: "Sea-ice fraction" }).closest("li"),
  ).toHaveTextContent("Sea-ice fraction: not testable here, no data for this area and window");
});

test("should list no checked variables when the scan found something", async () => {
  await showScan(scanNearby);

  expect(screen.queryByRole("list", { name: CHECKED })).toBeNull();
});

test.each([
  {
    note: "no_grid",
    text: "No trend grid exists for this variable yet, so the app checked no nearby areas.",
  },
  {
    note: "outside_grid",
    text: "This area lies outside the East Asia trend grid, so the app checked no nearby areas.",
  },
  {
    note: "grid_window_differs",
    text: "The trend grid covers another time window, so the app checked no nearby areas for this one.",
  },
] as const)("should explain the note $note", async ({ note, text }) => {
  await showScan({ ...scanNote, nearby_note: note });

  expect(screen.getByText(text)).toBeInTheDocument();
});

test("should say that no other variable trends when the hit list is empty", async () => {
  await showScan({ ...scanNearby, hits: [] });

  expect(
    screen.getByText("No other variable here passes the scan's correction for multiple tests."),
  ).toBeInTheDocument();
});

test("should say that no nearby area trends when the list is empty with no note", async () => {
  await showScan({ ...scanNearby, nearby: [] });

  expect(screen.getByText("No nearby area trends significantly.")).toBeInTheDocument();
});

test("should title the panel in Korean", async () => {
  serve(answer(trendNoTrend), answer(scanNote));
  openFocusTrend();
  renderPanel("ko");

  expect(await screen.findByRole("heading", { name: "다음에 살펴볼 곳" })).toBeInTheDocument();
});
