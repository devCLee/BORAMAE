/**
 * Writes the bundled base layer of the map (DEC-004): land and country borders
 * from Natural Earth 1:50m, as redistributed by world-atlas, converted to GeoJSON.
 * The files hold no place names, so the map can draw no text, and the export
 * needs no tile request.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

import { feature, mesh } from "topojson-client";

const OUT_DIR = path.join(import.meta.dirname, "../public/basemap");
const COORDINATE_DECIMALS = 3;
const SCALE = 10 ** COORDINATE_DECIMALS;

const require = createRequire(import.meta.url);
const topology = JSON.parse(
  readFileSync(require.resolve("world-atlas/countries-50m.json"), "utf8"),
);

const land = feature(topology, topology.objects.land);
// A border is an arc that two different countries share; the coastline is drawn by the land fill.
const borders = mesh(topology, topology.objects.countries, (a, b) => a !== b);

mkdirSync(OUT_DIR, { recursive: true });
// The export must hold the map worker at a fixed path: in the Next bundle maplibre-gl
// cannot find the worker file next to itself (BSD-3-Clause, self-contained). The
// first line keeps eslint off the vendor code, because the lint does not skip public/.
const WORKER_FILE = "maplibre-gl-worker.mjs";
writeFileSync(
  path.join(OUT_DIR, WORKER_FILE),
  Buffer.concat([
    Buffer.from("/* eslint-disable */\n"),
    readFileSync(require.resolve(`maplibre-gl/dist/${WORKER_FILE}`)),
  ]),
);
writeGeoJson("land.json", {
  type: "FeatureCollection",
  features: land.features.map(({ geometry }) => toFeature(geometry)),
});
writeGeoJson("borders.json", {
  type: "FeatureCollection",
  features: [toFeature(borders)],
});

function toFeature(geometry) {
  return {
    type: "Feature",
    properties: {},
    geometry: {
      type: geometry.type,
      coordinates: roundCoordinates(geometry.coordinates),
    },
  };
}

function roundCoordinates(value) {
  return typeof value === "number"
    ? Math.round(value * SCALE) / SCALE
    : value.map(roundCoordinates);
}

function writeGeoJson(name, collection) {
  writeFileSync(path.join(OUT_DIR, name), `${JSON.stringify(collection)}\n`);
}
