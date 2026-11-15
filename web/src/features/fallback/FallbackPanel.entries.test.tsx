import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { getState, resetStore } from "@/state/store";
import { scanNearby } from "@/test/fixtures";

import {
  CASE_ROOT,
  findList,
  FOCUS,
  FOUND_BY_SCAN,
  HITS,
  NEARBY,
  nearbyItem,
  showScan,
} from "./fallback-test-kit";

const OPPOSITE_AREA = scanNearby.nearby[1];
const OPPOSITE_RUN = "Run the analysis in the area 198.4 km away";

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test.each(["Air temperature", "Water vapour", "Skin temperature"])(
  "should name the hit %s",
  async (name) => {
    await showScan(scanNearby);

    expect(within(await findList(HITS)).getByRole("button", { name })).toBeInTheDocument();
  },
);

test.each(["0.31 °C per decade", "0.42 kg/m² per decade", "0.27 °C per decade"])(
  "should show the hit rate %s",
  async (rate) => {
    await showScan(scanNearby);

    expect(await within(await findList(HITS)).findByText(rate)).toBeInTheDocument();
  },
);

test("should open the provenance of a hit rate", async () => {
  await showScan(scanNearby);

  expect(
    await screen.findByRole("button", { name: "Source of 0.31 °C per decade" }),
  ).toBeInTheDocument();
});

test("should label each hit as found by a scan", async () => {
  await showScan(scanNearby);

  expect(
    within(await findList(HITS)).getAllByRole("button", { name: FOUND_BY_SCAN }),
  ).toHaveLength(3);
});

test("should show the direction of a hit", async () => {
  await showScan(scanNearby);

  expect(within(await findList(HITS)).getAllByText("Rising, significant")).toHaveLength(3);
});

test.each([
  {
    name: "put the variable in the draft",
    read: () => getState().draftSpec,
    expected: { var: "TQV", metric: { id: "annual_mean" } },
  },
  { name: "ask for confirmation again", read: () => getState().confirmedSpec, expected: null },
])("should $name when a hit is chosen", async ({ read, expected }) => {
  await showScan(scanNearby);

  await userEvent.click(screen.getByRole("button", { name: "Test Water vapour here" }));

  expect(read()).toEqual(expected);
});

test("should choose a hit from the keyboard", async () => {
  await showScan(scanNearby);
  screen.getByRole("button", { name: "Test Water vapour here" }).focus();

  await userEvent.keyboard("{Enter}");

  expect(getState().draftSpec?.var).toBe("TQV");
});

test("should hand the focus to the case panel when a chosen hit leaves", async () => {
  await showScan(scanNearby);

  await userEvent.click(screen.getByRole("button", { name: "Test Water vapour here" }));

  expect(screen.getByTestId(CASE_ROOT)).toHaveFocus();
});

test.each([
  { index: 0, text: "156.3 km away" },
  { index: 1, text: "198.4 km away" },
  { index: 2, text: "393.4 km away" },
])("should show the distance of nearby area $index", async ({ index, text }) => {
  await showScan(scanNearby);

  expect(within(await nearbyItem(index)).getByText(text)).toBeInTheDocument();
});

test.each([
  { index: 0, text: "Rising, significant" },
  { index: 1, text: "Falling, significant" },
  { index: 2, text: "Rising, significant" },
])("should show the direction of nearby area $index", async ({ index, text }) => {
  await showScan(scanNearby);

  expect(within(await nearbyItem(index)).getByText(text)).toBeInTheDocument();
});

test("should show the grid window of each nearby area", async () => {
  await showScan(scanNearby);

  expect(
    within(await findList(NEARBY)).getAllByText("Grid trend 1981 to Sep 2026"),
  ).toHaveLength(3);
});

test("should label each nearby area as found by a scan", async () => {
  await showScan(scanNearby);

  expect(
    within(await findList(NEARBY)).getAllByRole("button", { name: FOUND_BY_SCAN }),
  ).toHaveLength(3);
});

test.each([
  { name: "the opposite case", text: "Same process, opposite directions" },
  { name: "the mechanism", text: OPPOSITE_AREA.mechanism?.en ?? "" },
])("should name $name for an area with the opposite sign", async ({ text }) => {
  await showScan(scanNearby);

  expect(within(await nearbyItem(1)).getByText(text)).toBeInTheDocument();
});

test("should not mark an area with the same sign as opposite", async () => {
  await showScan(scanNearby);

  expect(
    within(await nearbyItem(0)).queryByText("Same process, opposite directions"),
  ).toBeNull();
});

test.each([
  {
    name: "pin the area",
    read: () => getState().area.pin,
    expected: { lat: OPPOSITE_AREA.lat, lon: OPPOSITE_AREA.lon },
  },
  { name: "use the smallest radius", read: () => getState().area.radiusKm, expected: 10 },
  { name: "confirm the run", read: () => getState().confirmedSpec, expected: FOCUS },
  {
    name: "move the map there",
    read: () => getState().mapTarget,
    expected: { center: { lat: OPPOSITE_AREA.lat, lon: OPPOSITE_AREA.lon }, zoom: null },
  },
])("should $name when a nearby area is chosen", async ({ read, expected }) => {
  await showScan(scanNearby);

  await userEvent.click(screen.getByRole("button", { name: OPPOSITE_RUN }));

  expect(read()).toEqual(expected);
});

test("should choose a nearby area from the keyboard", async () => {
  await showScan(scanNearby);
  screen.getByRole("button", { name: OPPOSITE_RUN }).focus();

  await userEvent.keyboard("{Enter}");

  expect(getState().area.pin).toEqual({ lat: OPPOSITE_AREA.lat, lon: OPPOSITE_AREA.lon });
});

test("should hand the focus to the case panel when a chosen area leaves", async () => {
  await showScan(scanNearby);

  await userEvent.click(screen.getByRole("button", { name: OPPOSITE_RUN }));

  expect(screen.getByTestId(CASE_ROOT)).toHaveFocus();
});
