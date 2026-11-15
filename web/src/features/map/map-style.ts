/**
 * The style of the map (DEC-004): the bundled land and border outlines, with no
 * tile, glyph or sprite request, so the offline demo loads no map file from
 * outside the export. The overlay draws the pinned circle and its grid cells.
 */
import type {
  AddLayerObject,
  GeoJSONSource,
  Map,
  MapOptions,
} from "maplibre-gl";

import type { MapView, Point } from "@/state/types";

type StyleObject = Exclude<MapOptions["style"], string | undefined>;
type GeoJsonData = Parameters<GeoJSONSource["setData"]>[0];

export const SOURCE_AREA = "area";
export const SOURCE_CELLS = "cells";
export const EMPTY_COLLECTION: GeoJsonData = {
  type: "FeatureCollection",
  features: [],
};

const LAND_URL = "/basemap/land.json";
const BORDERS_URL = "/basemap/borders.json";
const MAX_LAT_DEG = 90;
const HALF_TURN_DEG = 180;
const FULL_TURN_DEG = 360;
const BORDER_WIDTH_PX = 0.5;
const AREA_WIDTH_PX = 2;
const CELL_OUTLINE_WIDTH_PX = 1;
const CELL_FILL_OPACITY = 0.2;
// ponytail: one key press moves the pin 0.1 degrees, about 11 km, a fifth of a
// cell row. No document gives a step; a modifier for larger steps can come later.
const PIN_STEP_DEG = 0.1;
const ARROW_STEPS: Partial<Record<string, [dLat: number, dLon: number]>> = {
  ArrowUp: [1, 0],
  ArrowDown: [-1, 0],
  ArrowLeft: [0, -1],
  ArrowRight: [0, 1],
};

/** The design roles that the map paints. WebGL takes no utility class, so the map reads the role values. */
export interface MapColors {
  sea: string;
  land: string;
  border: string;
  area: string;
  cell: string;
}

export function readMapColors(): MapColors {
  const style = getComputedStyle(document.documentElement);
  const role = (name: string) =>
    toRgb(style.getPropertyValue(`--${name}`).trim());
  return {
    sea: role("muted"),
    land: role("border"),
    border: role("muted-foreground"),
    area: role("foreground"),
    cell: role("primary"),
  };
}

/**
 * The built CSS holds each role as a lab() color, which the map style cannot parse.
 * The browser paints the color on a canvas, and the map gets the pixel as rgb().
 */
function toRgb(color: string): string {
  if (color === "") {
    return color;
  }
  const context = document.createElement("canvas").getContext("2d");
  if (!context) {
    return color;
  }
  context.fillStyle = color;
  context.fillRect(0, 0, 1, 1);
  const [red, green, blue] = context.getImageData(0, 0, 1, 1).data;
  return `rgb(${red}, ${green}, ${blue})`;
}

export function createBaseStyle(colors: MapColors): StyleObject {
  return {
    version: 8,
    projection: { type: "globe" },
    sources: {
      land: { type: "geojson", data: LAND_URL },
      borders: { type: "geojson", data: BORDERS_URL },
    },
    layers: [
      {
        id: "sea",
        type: "background",
        paint: { "background-color": colors.sea },
      },
      {
        id: "land",
        type: "fill",
        source: "land",
        paint: { "fill-color": colors.land },
      },
      {
        id: "borders",
        type: "line",
        source: "borders",
        paint: { "line-color": colors.border, "line-width": BORDER_WIDTH_PX },
      },
    ],
  };
}

/** Adds the empty sources and the layers of the circle and its cells. */
export function addOverlay(map: Map, colors: MapColors): void {
  map.addSource(SOURCE_CELLS, { type: "geojson", data: EMPTY_COLLECTION });
  map.addSource(SOURCE_AREA, { type: "geojson", data: EMPTY_COLLECTION });
  const layers: AddLayerObject[] = [
    {
      id: "cells-fill",
      type: "fill",
      source: SOURCE_CELLS,
      paint: { "fill-color": colors.cell, "fill-opacity": CELL_FILL_OPACITY },
    },
    {
      id: "cells-outline",
      type: "line",
      source: SOURCE_CELLS,
      paint: { "line-color": colors.cell, "line-width": CELL_OUTLINE_WIDTH_PX },
    },
    {
      id: "area-outline",
      type: "line",
      source: SOURCE_AREA,
      paint: { "line-color": colors.area, "line-width": AREA_WIDTH_PX },
    },
  ];
  layers.forEach((layer) => map.addLayer(layer));
}

export function setSourceData(map: Map, id: string, data: GeoJsonData): void {
  void map.getSource<GeoJSONSource>(id)?.setData(data);
}

/**
 * The view for the store. A bbox request reads west above east as a box across
 * the 180 meridian, so the bounds are wrapped into -180 to 180.
 */
export function readView(map: Map): MapView {
  const center = map.getCenter();
  const bounds = map.getBounds();
  const west = bounds.getWest();
  const east = bounds.getEast();
  const isWholeTurn = east - west >= FULL_TURN_DEG;
  return {
    center: { lat: center.lat, lon: wrapLon(center.lng) },
    zoom: map.getZoom(),
    bounds: [
      isWholeTurn ? -HALF_TURN_DEG : wrapLon(west),
      bounds.getSouth(),
      isWholeTurn ? HALF_TURN_DEG : wrapLon(east),
      bounds.getNorth(),
    ],
  };
}

/** The point one step away in the direction of an arrow key, or null for another key. */
export function movePoint(point: Point, key: string): Point | null {
  const step = ARROW_STEPS[key];
  if (step === undefined) {
    return null;
  }
  const lat = point.lat + step[0] * PIN_STEP_DEG;
  return {
    lat: Math.min(Math.max(lat, -MAX_LAT_DEG), MAX_LAT_DEG),
    lon: wrapLon(point.lon + step[1] * PIN_STEP_DEG),
  };
}

// ponytail: one turn of wrapping, which covers the world copies next to the
// first one. A map with more world copies would need a modulo.
function wrapLon(lon: number) {
  if (lon > HALF_TURN_DEG) {
    return lon - FULL_TURN_DEG;
  }
  return lon < -HALF_TURN_DEG ? lon + FULL_TURN_DEG : lon;
}
