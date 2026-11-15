"use client";

import { useEffect } from "react";

import { actions, getState, useAppStore } from "@/state/store";

import { PlaceSearch } from "./PlaceSearch";
import { RadiusControl } from "./RadiusControl";

/**
 * The place search and the radius over the map (FR-04). A new parse proposal
 * that names a place pins it when no pin exists yet, and never moves a pin the
 * user set (user decision for wave 4).
 */
export function PlaceControls() {
  const proposal = useAppStore((state) => state.proposal);

  useEffect(() => {
    const place = proposal?.spec.place ?? null;
    if (place === null || getState().area.pin !== null) {
      return;
    }
    const point = { lat: place.lat, lon: place.lon };
    actions.setPin(point, "user");
    actions.setMapTarget({ center: point, zoom: null });
  }, [proposal]);

  return (
    <div
      data-testid="slot-places"
      className="flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2 rounded-md bg-background/95 p-3 shadow-md"
    >
      <PlaceSearch />
      <RadiusControl />
    </div>
  );
}
