import golden from "@content/golden/cells.json";
import { expect, test } from "vitest";

import type { GridDef } from "@/contracts/types";

import {
  cellPolygons,
  cellsInCircle,
  circlePolygon,
  EARTH_RADIUS_KM,
} from "./cells";

const GRID: GridDef = golden.grid;
const SEOUL = { lat: 37.5665, lon: 126.978 };
const DEGREES_PER_RADIAN = 180 / Math.PI;

test.each(golden.cases)(
  "should give the cells of the golden case $name",
  ({ lat, lon, radius_km, cells }) => {
    expect(cellsInCircle(GRID, lat, lon, radius_km).cells).toEqual(cells);
  },
);

test.each(golden.cases)(
  "should give the containing-cell flag of the golden case $name",
  ({ lat, lon, radius_km, used_containing_cell }) => {
    expect(
      cellsInCircle(GRID, lat, lon, radius_km).usedContainingCell,
    ).toBe(used_containing_cell);
  },
);

test.each(golden.cases)(
  "should count the cells of the golden case $name",
  ({ lat, lon, radius_km, cells }) => {
    expect(cellsInCircle(GRID, lat, lon, radius_km).count).toBe(cells.length);
  },
);

test("should give the containing cell and the flag when the circle holds no cell center", () => {
  expect(cellsInCircle(GRID, 37.7, 127.2, 10)).toEqual({
    cells: [[255, 492]],
    count: 1,
    usedContainingCell: true,
  });
});

test("should give one polygon for each cell", () => {
  const polygons = cellPolygons(GRID, [
    [255, 491],
    [255, 492],
    [256, 491],
  ]);

  expect(polygons.features.map(({ geometry }) => geometry.type)).toEqual([
    "Polygon",
    "Polygon",
    "Polygon",
  ]);
});

test("should draw a cell as the closed box around its center", () => {
  const [cell] = cellPolygons(GRID, [[255, 491]]).features;

  expect(cell.geometry.coordinates).toEqual([
    [
      [126.5625, 37.25],
      [127.1875, 37.25],
      [127.1875, 37.75],
      [126.5625, 37.75],
      [126.5625, 37.25],
    ],
  ]);
});

test("should keep a polar cell inside the latitude range", () => {
  const [cell] = cellPolygons(GRID, [[360, 0]]).features;

  expect(cell.geometry.coordinates[0][2]).toEqual([-179.6875, 90]);
});

test("should give no polygon for no cell", () => {
  expect(cellPolygons(GRID, []).features).toEqual([]);
});

test("should start the circle due north of the pin at the radius", () => {
  const [ring] = circlePolygon(SEOUL, 25).geometry.coordinates;

  expect(ring[0][1] - SEOUL.lat).toBeCloseTo(
    (25 / EARTH_RADIUS_KM) * DEGREES_PER_RADIAN,
    9,
  );
});

test("should close the ring of the circle", () => {
  const [ring] = circlePolygon(SEOUL, 25).geometry.coordinates;

  expect(ring.at(-1)).toEqual(ring[0]);
});

test("should draw a circle across the 180 meridian with no jump in longitude", () => {
  const [ring] = circlePolygon({ lat: 0, lon: 179.9 }, 100).geometry.coordinates;

  expect(Math.max(...ring.map(([lon]) => lon))).toBeGreaterThan(180);
});
