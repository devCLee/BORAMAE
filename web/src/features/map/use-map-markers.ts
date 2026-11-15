"use client";

import { type Map, Marker } from "maplibre-gl";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";

import type { NearbyArea, Verdict } from "@/contracts/types";
import { RADIUS_MIN_KM } from "@/lib/cells";
import { actions, getState } from "@/state/store";
import type { Point } from "@/state/types";

import { movePoint } from "./map-style";

const ARROW_KEYS = "ArrowUp ArrowDown ArrowLeft ArrowRight";
// The button keeps a 44 px target around the small dot that the map shows.
const MARKER_BUTTON_CLASS =
  "flex size-11 items-center justify-center rounded-full";
const PIN_DOT_CLASS =
  "size-4 rounded-full border-2 border-background bg-foreground shadow";
const NEARBY_DOT_CLASS =
  "flex size-7 items-center justify-center rounded-full border-2 border-background text-xs text-primary-foreground shadow";

interface NearbyLook {
  verdict: Verdict;
  className: string;
  /** The shape repeats the color, so the sign never rests on color alone. */
  glyph: string;
}

const RISE: NearbyLook = {
  verdict: "significant_rise",
  className: "bg-trend-rise",
  glyph: "▲",
};
const FALL: NearbyLook = {
  verdict: "significant_fall",
  className: "bg-trend-fall",
  glyph: "▼",
};
const FLAT: NearbyLook = {
  verdict: "no_trend",
  className: "bg-no-trend",
  glyph: "●",
};

/**
 * Runs the draft, or the Explore default, at one point with the smallest
 * radius, so the area is the cell at the point (TR-F-040). It counts as the
 * confirmation (working value under TDD Q-016).
 */
export function runAtCell(point: Point): void {
  actions.setRadius(RADIUS_MIN_KM, "user");
  actions.runAtPoint(point);
}

/** The pin of the area and the nearby pins of a scan result, as marker buttons. */
export function useMapMarkers(
  map: Map | null,
  pin: Point | null,
  nearby: NearbyArea[] | null,
): void {
  const t = useTranslations("map");
  const tGlossary = useTranslations("glossary");
  const pinMarkerRef = useRef<Marker | null>(null);
  const isPinFocusDueRef = useRef(false);

  useEffect(() => {
    if (map === null) {
      return;
    }
    const element = createMarkerButton(PIN_DOT_CLASS);
    element.setAttribute("aria-keyshortcuts", ARROW_KEYS);
    element.addEventListener("keydown", handlePinKey);
    const marker = new Marker({ element });
    pinMarkerRef.current = marker;
    return () => {
      marker.remove();
      pinMarkerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    pinMarkerRef.current?.getElement().setAttribute("aria-label", t("pin"));
  }, [map, t]);

  useEffect(() => {
    const marker = pinMarkerRef.current;
    if (map === null || marker === null) {
      return;
    }
    if (pin === null) {
      marker.remove();
      return;
    }
    marker.setLngLat([pin.lon, pin.lat]);
    const element = marker.getElement();
    // Adding again would take the element out of the page and drop its focus.
    if (!element.isConnected) {
      marker.addTo(map);
    }
    if (isPinFocusDueRef.current) {
      isPinFocusDueRef.current = false;
      element.focus();
    }
  }, [map, pin]);

  useEffect(() => {
    if (map === null || nearby === null) {
      return;
    }
    const markers = nearby.map((area) => {
      const look = toNearbyLook(area.sign);
      const element = createMarkerButton(
        `${NEARBY_DOT_CLASS} ${look.className}`,
        look.glyph,
      );
      element.setAttribute(
        "aria-label",
        t("nearby", {
          verdict: tGlossary(`verdicts.${look.verdict}`),
          distance: area.distance_km,
        }),
      );
      element.addEventListener("click", (event) => {
        // The map would take the same click as a click on the globe.
        event.stopPropagation();
        // The nearby pins leave with the scan panel, so the focus goes to the new pin.
        isPinFocusDueRef.current = true;
        runAtCell({ lat: area.lat, lon: area.lon });
      });
      return new Marker({ element })
        .setLngLat([area.lon, area.lat])
        .addTo(map);
    });
    return () => markers.forEach((marker) => marker.remove());
  }, [map, nearby, t, tGlossary]);
}

function handlePinKey(event: KeyboardEvent) {
  const { pin } = getState().area;
  const moved = pin === null ? null : movePoint(pin, event.key);
  if (moved === null) {
    return;
  }
  // The marker sits inside the canvas container, and the map pans on the same keys.
  event.preventDefault();
  event.stopPropagation();
  actions.setPin(moved, "user");
}

function toNearbyLook(sign: NearbyArea["sign"]): NearbyLook {
  if (sign > 0) {
    return RISE;
  }
  return sign < 0 ? FALL : FLAT;
}

function createMarkerButton(dotClassName: string, glyph = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = MARKER_BUTTON_CLASS;
  const dot = document.createElement("span");
  dot.className = dotClassName;
  dot.setAttribute("aria-hidden", "true");
  dot.textContent = glyph;
  button.append(dot);
  return button;
}
