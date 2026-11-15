import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { TrendResult } from "@/contracts/types";
import { cellPolygons, circlePolygon } from "@/lib/cells";
import { problemResponse, stubFetch } from "@/lib/fetch-layer.stub";
import { MARK_MAP_INTERACTIVE } from "@/lib/perf";
import { actions, getState, resetStore } from "@/state/store";
import { catalog, trendSignificant } from "@/test/fixtures";

import {
  lastData,
  renderLoadedMap,
  renderMap,
  SEOUL,
  serveApi,
} from "./map-test-kit";

const NO_CENTER_POINT = { lat: 37.7, lon: 127.2 };
const RESULT_CELLS: [number, number][] = [
  [255, 491],
  [255, 492],
];
const TREND_WITH_OTHER_CELLS: TrendResult = {
  ...trendSignificant,
  provenance: { ...trendSignificant.provenance, cells: RESULT_CELLS },
};

beforeEach(() => {
  resetStore();
  performance.clearMarks();
  stubFetch(serveApi());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should keep the slot element", () => {
  renderMap();

  expect(screen.getByTestId("slot-map")).toBeInTheDocument();
});

test("should give the map an accessible name", () => {
  renderMap();

  expect(screen.getByRole("region", { name: "Map" })).toBeInTheDocument();
});

test("should draw the globe projection", () => {
  const map = renderMap();

  expect(map.options.style).toMatchObject({ projection: { type: "globe" } });
});

test("should read its sources only from the bundled outline files", () => {
  const map = renderMap();

  expect(map.options.style).toHaveProperty("sources", {
    land: { type: "geojson", data: "/basemap/land.json" },
    borders: { type: "geojson", data: "/basemap/borders.json" },
  });
});

test.each(["glyphs", "sprite"])("should request no %s", (property) => {
  const map = renderMap();

  expect(map.options.style).not.toHaveProperty(property);
});

test("should add no text layer", () => {
  const map = renderLoadedMap();

  expect(map.addLayer.mock.calls.map(([layer]) => layer.type)).not.toContain(
    "symbol",
  );
});

test("should set the mark map-interactive on load", () => {
  renderLoadedMap();

  expect(performance.getEntriesByName(MARK_MAP_INTERACTIVE)).toHaveLength(1);
});

test("should not set the mark map-interactive before load", () => {
  renderMap();

  expect(performance.getEntriesByName(MARK_MAP_INTERACTIVE)).toHaveLength(0);
});

test("should write the center, zoom and bounds to the store on moveend", () => {
  const map = renderLoadedMap();
  map.getCenter.mockReturnValue({ lng: 127.5, lat: 36.5 });
  map.getZoom.mockReturnValue(5);
  map.getBounds.mockReturnValue({
    getWest: () => 120,
    getSouth: () => 30,
    getEast: () => 135,
    getNorth: () => 43,
  });

  act(() => {
    map.fire("moveend");
  });

  expect(getState().mapView).toEqual({
    center: { lat: 36.5, lon: 127.5 },
    zoom: 5,
    bounds: [120, 30, 135, 43],
  });
});

test("should write a view across the 180 meridian with west above east", () => {
  const map = renderLoadedMap();
  map.getBounds.mockReturnValue({
    getWest: () => 170,
    getSouth: () => -10,
    getEast: () => 190,
    getNorth: () => 10,
  });

  act(() => {
    map.fire("moveend");
  });

  expect(getState().mapView?.bounds).toEqual([170, -10, -170, 10]);
});

test("should write the view to the store on load", () => {
  renderLoadedMap();

  expect(getState().mapView).toEqual({
    center: { lat: 0, lon: 0 },
    zoom: 0,
    bounds: [-180, -90, 180, 90],
  });
});

test("should write the cell preview of a new pin to the store", async () => {
  renderLoadedMap();

  act(() => actions.setPin(SEOUL, "user"));

  await waitFor(() =>
    expect(getState().cellPreview).toEqual({
      cells: [[255, 491]],
      count: 1,
      usedContainingCell: false,
    }),
  );
});

test("should write the cell preview again after a radius change", async () => {
  renderLoadedMap();
  act(() => actions.setPin(SEOUL, "user"));

  act(() => actions.setRadius(300, "user"));

  await waitFor(() => expect(getState().cellPreview?.count).toBe(94));
});

test("should write the containing cell and its flag when no cell center is inside", async () => {
  renderLoadedMap();
  act(() => actions.setRadius(10, "user"));

  act(() => actions.setPin(NO_CENTER_POINT, "user"));

  await waitFor(() =>
    expect(getState().cellPreview).toEqual({
      cells: [[255, 492]],
      count: 1,
      usedContainingCell: true,
    }),
  );
});

test("should clear the cell preview when the pin is removed", async () => {
  renderLoadedMap();
  act(() => actions.setPin(SEOUL, "user"));
  await waitFor(() => expect(getState().cellPreview).not.toBeNull());

  act(() => actions.setPin(null, "user"));

  await waitFor(() => expect(getState().cellPreview).toBeNull());
});

test("should draw the cells of the preview", async () => {
  const map = renderLoadedMap();

  act(() => actions.setPin(SEOUL, "user"));

  await waitFor(() =>
    expect(lastData(map, "cells")).toEqual(
      cellPolygons(catalog.grid, [[255, 491]]),
    ),
  );
});

test("should redraw the cells from the result when its cell list differs from the preview", async () => {
  stubFetch(serveApi(TREND_WITH_OTHER_CELLS));
  const map = renderLoadedMap();

  act(() => actions.runAtPoint(SEOUL));

  await waitFor(() =>
    expect(lastData(map, "cells")).toEqual(
      cellPolygons(catalog.grid, RESULT_CELLS),
    ),
  );
});

test("should draw the outline of the pinned circle", async () => {
  const map = renderLoadedMap();

  act(() => actions.setPin(SEOUL, "user"));

  await waitFor(() =>
    expect(lastData(map, "area")).toEqual(circlePolygon(SEOUL, 25)),
  );
});

test("should show the cell count of the area", async () => {
  renderLoadedMap();

  act(() => actions.setPin(SEOUL, "user"));

  expect(await screen.findByText("1 grid cell in the area")).toBeInTheDocument();
});

test("should show the notice when the containing cell takes the place of the area", async () => {
  renderLoadedMap();
  act(() => actions.setRadius(10, "user"));

  act(() => actions.setPin(NO_CENTER_POINT, "user"));

  expect(
    await screen.findByText(
      "No grid cell center falls inside the area, so the app uses the cell that contains it.",
    ),
  ).toBeInTheDocument();
});

test("should show the zoom-in-or-pin state when the view is too large", async () => {
  stubFetch(serveApi(problemResponse(400, "area_too_large")));
  renderLoadedMap();

  act(() => {
    actions.editDraft({ var: "T2M", metric: { id: "annual_mean" } }, "user");
    actions.confirmSpec();
    actions.openPanel("trend");
  });

  expect(
    await screen.findByText(
      "This view covers too large an area. Zoom in, or pin a place on the map.",
    ),
  ).toBeInTheDocument();
});
