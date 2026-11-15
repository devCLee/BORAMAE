"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { Map, setWorkerUrl } from "maplibre-gl";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { useCatalog, useScan, useTrend } from "@/hooks/queries";
import { cellPolygons, cellsInCircle, circlePolygon } from "@/lib/cells";
import { MARK_MAP_INTERACTIVE, markPerf } from "@/lib/perf";
import { actions, getState, useAppStore } from "@/state/store";
import type { CellPreview, Point } from "@/state/types";

import {
  addOverlay,
  createBaseStyle,
  EMPTY_COLLECTION,
  readMapColors,
  readView,
  setSourceData,
  SOURCE_AREA,
  SOURCE_CELLS,
} from "./map-style";
import { runAtCell, useMapMarkers } from "./use-map-markers";

// ponytail: the first view faces Korea, where both demo cases sit. No document
// gives a start view; the rail reads the country in view from it.
const START_CENTER: [lon: number, lat: number] = [127.8, 36.5];
const START_ZOOM = 2;
const NO_CELLS: CellPreview["cells"] = [];
// gen-basemap copies the worker here, because the bundle gives maplibre-gl no URL for it.
const WORKER_URL = "/basemap/maplibre-gl-worker.mjs";

/**
 * The map (DES-019): a globe on the bundled outlines with the pin, the circle and
 * its grid cells before any run (TR-F-007). It reports its view to the store, so
 * a window with no pin uses it (FR-09). The cells of a result replace the preview,
 * because the service is authoritative.
 */
export function MapView() {
  const t = useTranslations("map");
  const containerRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<Map | null>(null);
  const grid = useCatalog().data?.grid ?? null;
  const trend = useTrend();
  const nearby = useScan().data?.body.nearby ?? null;
  const pin = useAppStore((state) => state.area.pin);
  const radiusKm = useAppStore((state) => state.area.radiusKm);
  const preview = useAppStore((state) => state.cellPreview);
  const mapTarget = useAppStore((state) => state.mapTarget);

  const cells = trend.data?.body.provenance.cells ?? preview?.cells ?? NO_CELLS;
  const usedContainingCell =
    preview?.usedContainingCell === true ||
    trend.data?.meta.usedContainingCell === true;

  useEffect(() => {
    const container = containerRef.current;
    if (container === null) {
      return;
    }
    const colors = readMapColors();
    setWorkerUrl(WORKER_URL);
    const instance = new Map({
      container,
      style: createBaseStyle(colors),
      center: START_CENTER,
      zoom: START_ZOOM,
    });
    instance.on("load", () => {
      addOverlay(instance, colors);
      actions.setMapView(readView(instance));
      markPerf(MARK_MAP_INTERACTIVE);
      setMap(instance);
    });
    instance.on("moveend", () => actions.setMapView(readView(instance)));
    instance.on("click", (event) =>
      handleMapClick({ lat: event.lngLat.lat, lon: event.lngLat.lng }),
    );
    return () => instance.remove();
  }, []);

  useEffect(() => {
    map?.getCanvas().setAttribute("aria-label", t("canvas"));
  }, [map, t]);

  useEffect(() => {
    if (grid === null) {
      return;
    }
    actions.setCellPreview(
      pin === null ? null : cellsInCircle(grid, pin.lat, pin.lon, radiusKm),
    );
  }, [grid, pin, radiusKm]);

  useEffect(() => {
    if (map !== null && grid !== null) {
      setSourceData(map, SOURCE_CELLS, cellPolygons(grid, cells));
    }
  }, [map, grid, cells]);

  useEffect(() => {
    if (map !== null) {
      setSourceData(
        map,
        SOURCE_AREA,
        pin === null ? EMPTY_COLLECTION : circlePolygon(pin, radiusKm),
      );
    }
  }, [map, pin, radiusKm]);

  useEffect(() => {
    if (map !== null && mapTarget !== null) {
      map.flyTo({
        center: [mapTarget.center.lon, mapTarget.center.lat],
        ...(mapTarget.zoom === null ? {} : { zoom: mapTarget.zoom }),
      });
    }
  }, [map, mapTarget]);

  useMapMarkers(map, pin, nearby);

  return (
    <div
      data-testid="slot-map"
      role="region"
      aria-label={t("label")}
      className="relative size-full bg-background"
    >
      {/* maplibre-gl.css makes this element position: relative, so a size fills the slot, not an inset. */}
      <div ref={containerRef} className="size-full" />
      <p
        role="status"
        className="pointer-events-none absolute bottom-3 left-1/2 max-w-xs -translate-x-1/2 text-center text-xs"
      >
        {cells.length > 0 && (
          <span className="block rounded-md bg-background/90 px-3 py-1.5 shadow">
            {t("cell_count", { count: cells.length })}
            {usedContainingCell && (
              <span className="block text-muted-foreground">
                {t("containing_cell")}
              </span>
            )}
          </span>
        )}
      </p>
      {trend.error?.code === "zoom_in_or_pin" && (
        <div className="absolute inset-x-3 top-1/3 mx-auto max-w-sm rounded-md bg-background shadow-lg">
          <EmptyState messageKey="zoom_in_or_pin" />
        </div>
      )}
    </div>
  );
}

// A click starts a run only in Explore. In the guided steps it places the pin,
// and the demo and the door screen keep the map for looking.
function handleMapClick(point: Point) {
  const { mode } = getState();
  if (mode === "explore") {
    runAtCell(point);
  }
  if (mode === "guided") {
    actions.setPin(point, "user");
  }
}
