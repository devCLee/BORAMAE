/**
 * The cell preview of the map (TR-F-007, TDD Flow B). It repeats the cell rule of
 * api/boramae/spec/cells.py on the grid of the catalog file, so the map can draw
 * the cells before the run. The result of the service stays authoritative, and
 * content/golden/cells.json holds the cases that both sides reproduce.
 */
import type { Feature, FeatureCollection, Polygon, Position } from "geojson";

import type { GridDef } from "@/contracts/types";
import type { CellPreview, Point } from "@/state/types";

/** The Earth radius of the service (EARTH_RADIUS_KM in api/boramae/constants.py). */
export const EARTH_RADIUS_KM = 6371;
/** The smallest radius of an area (FR-04, RADIUS_MIN_KM in api/boramae/constants.py). */
export const RADIUS_MIN_KM = 10;

type Cell = [latIndex: number, lonIndex: number];

const DEGREES_PER_RADIAN = 180 / Math.PI;
const MAX_LAT_DEG = 90;
// ponytail: 64 vertices keep a 300 km circle within about 0.4 km of the true
// outline. Raise it if a larger radius ever draws a visible polygon.
const CIRCLE_VERTICES = 64;

/**
 * The sorted cells whose centers lie in the circle, edges included. If the circle
 * holds no center, the cell that contains the point takes their place and the
 * flag is set.
 */
export function cellsInCircle(
  grid: GridDef,
  lat: number,
  lon: number,
  radiusKm: number,
): CellPreview {
  const reachDeg = (radiusKm / EARTH_RADIUS_KM) * DEGREES_PER_RADIAN;
  const firstRow = Math.max(
    Math.floor((lat - reachDeg - grid.lat0) / grid.dlat),
    0,
  );
  const lastRow = Math.min(
    Math.ceil((lat + reachDeg - grid.lat0) / grid.dlat),
    grid.n_lat - 1,
  );
  const cells: Cell[] = [];
  // Every column of a row is tested, so a circle across the 180 meridian or over
  // a pole needs no special case, as in the service.
  for (let row = firstRow; row <= lastRow; row += 1) {
    const rowLat = grid.lat0 + grid.dlat * row;
    for (let col = 0; col < grid.n_lon; col += 1) {
      const colLon = grid.lon0 + grid.dlon * col;
      if (haversineKm(lat, lon, rowLat, colLon) <= radiusKm) {
        cells.push([row, col]);
      }
    }
  }
  if (cells.length > 0) {
    return { cells, count: cells.length, usedContainingCell: false };
  }
  return {
    cells: [containingCell(grid, lat, lon)],
    count: 1,
    usedContainingCell: true,
  };
}

/** One polygon for each cell: the box of the grid steps around its center. */
export function cellPolygons(
  grid: GridDef,
  cells: readonly (readonly [number, number])[],
): FeatureCollection<Polygon> {
  return {
    type: "FeatureCollection",
    features: cells.map(([row, col]) => {
      const lat = grid.lat0 + grid.dlat * row;
      const lon = grid.lon0 + grid.dlon * col;
      const south = clampLat(lat - grid.dlat / 2);
      const north = clampLat(lat + grid.dlat / 2);
      const west = lon - grid.dlon / 2;
      const east = lon + grid.dlon / 2;
      return toPolygon([
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ]);
    }),
  };
}

/**
 * The outline of the pinned circle on the sphere. The longitudes are not wrapped,
 * so a circle across the 180 meridian stays one ring.
 */
export function circlePolygon(center: Point, radiusKm: number): Feature<Polygon> {
  const angular = radiusKm / EARTH_RADIUS_KM;
  const lat1 = center.lat / DEGREES_PER_RADIAN;
  const ring = Array.from({ length: CIRCLE_VERTICES + 1 }, (_, index) => {
    const bearing = (index % CIRCLE_VERTICES) * ((2 * Math.PI) / CIRCLE_VERTICES);
    const lat2 = Math.asin(
      Math.sin(lat1) * Math.cos(angular) +
        Math.cos(lat1) * Math.sin(angular) * Math.cos(bearing),
    );
    const dLon = Math.atan2(
      Math.sin(bearing) * Math.sin(angular) * Math.cos(lat1),
      Math.cos(angular) - Math.sin(lat1) * Math.sin(lat2),
    );
    return [center.lon + dLon * DEGREES_PER_RADIAN, lat2 * DEGREES_PER_RADIAN];
  });
  return toPolygon(ring);
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number) {
  const phi1 = lat1 / DEGREES_PER_RADIAN;
  const phi2 = lat2 / DEGREES_PER_RADIAN;
  const halfDphi = (phi2 - phi1) / 2;
  const halfDlambda = (lon2 - lon1) / DEGREES_PER_RADIAN / 2;
  const chord =
    Math.sin(halfDphi) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(halfDlambda) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(Math.min(chord, 1)));
}

// floor(x + 0.5) is Math.round: a point on a cell edge takes the upper or
// eastern cell, as the service does.
function containingCell(grid: GridDef, lat: number, lon: number): Cell {
  const row = Math.round((lat - grid.lat0) / grid.dlat);
  const col = Math.round((lon - grid.lon0) / grid.dlon);
  return [
    Math.min(Math.max(row, 0), grid.n_lat - 1),
    ((col % grid.n_lon) + grid.n_lon) % grid.n_lon,
  ];
}

function clampLat(lat: number) {
  return Math.min(Math.max(lat, -MAX_LAT_DEG), MAX_LAT_DEG);
}

function toPolygon(ring: Position[]): Feature<Polygon> {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: [ring] },
  };
}
