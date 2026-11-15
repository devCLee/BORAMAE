import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { stubFetch } from "@/lib/fetch-layer.stub";
import { actions, getState, resetStore } from "@/state/store";

import { renderLoadedMap, SEOUL, serveApi } from "./map-test-kit";

const CLICKED_POINT = { lat: 37.7, lon: 127.2 };
const KEY_POINT = { lat: 37.5, lon: 127 };
const NEARBY_RISE_NAME =
  "Nearby area: Rising, significant, 156.3 km away. Select it to run the analysis there.";
const PIN_NAME = "Pinned place. Use the arrow keys to move it.";

beforeEach(() => {
  resetStore();
  stubFetch(serveApi());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should run at the clicked point with the smallest radius in explore mode", () => {
  const map = renderLoadedMap();
  act(() => actions.skipToExplore());

  act(() => {
    map.fire("click", { lngLat: { lng: 127.2, lat: 37.7 } });
  });

  expect(getState().area).toEqual({ pin: CLICKED_POINT, radiusKm: 10 });
});

test("should confirm the Explore default and open the trend panel on a click in explore mode", () => {
  const map = renderLoadedMap();
  act(() => actions.skipToExplore());

  act(() => {
    map.fire("click", { lngLat: { lng: 127.2, lat: 37.7 } });
  });

  expect(getState()).toMatchObject({
    confirmedSpec: { var: "T2M", metric: { id: "annual_mean" } },
    openPanels: ["trend"],
  });
});

test("should pin the clicked point without a confirmation in guided mode", () => {
  const map = renderLoadedMap();
  act(() => actions.chooseDoor("guided"));

  act(() => {
    map.fire("click", { lngLat: { lng: 127.2, lat: 37.7 } });
  });

  expect(getState()).toMatchObject({
    area: { pin: CLICKED_POINT, radiusKm: 25 },
    confirmedSpec: null,
  });
});

test("should ignore a click before a door is chosen", () => {
  const map = renderLoadedMap();

  act(() => {
    map.fire("click", { lngLat: { lng: 127.2, lat: 37.7 } });
  });

  expect(getState().area.pin).toBeNull();
});

test("should name each nearby pin by its trend and distance", async () => {
  renderLoadedMap();

  act(() => {
    actions.runAtPoint(SEOUL);
    actions.openPanel("scan");
  });

  expect(
    await screen.findByRole("button", { name: NEARBY_RISE_NAME }),
  ).toBeInTheDocument();
});

test("should run at the cell of a nearby pin when it is clicked", async () => {
  const user = userEvent.setup();
  renderLoadedMap();
  act(() => {
    actions.runAtPoint(SEOUL);
    actions.openPanel("scan");
  });

  await user.click(await screen.findByRole("button", { name: NEARBY_RISE_NAME }));

  expect(getState().area).toEqual({
    pin: { lat: 36.5, lon: 128.125 },
    radiusKm: 10,
  });
});

test("should move the focus to the pin after a nearby pin is clicked", async () => {
  const user = userEvent.setup();
  renderLoadedMap();
  act(() => {
    actions.runAtPoint(SEOUL);
    actions.openPanel("scan");
  });

  await user.click(await screen.findByRole("button", { name: NEARBY_RISE_NAME }));

  await waitFor(() =>
    expect(screen.getByRole("button", { name: PIN_NAME })).toHaveFocus(),
  );
});

test.each([
  ["{ArrowUp}", { lat: 37.6, lon: 127 }],
  ["{ArrowDown}", { lat: 37.4, lon: 127 }],
  ["{ArrowLeft}", { lat: 37.5, lon: 126.9 }],
  ["{ArrowRight}", { lat: 37.5, lon: 127.1 }],
])("should move the pin with the key %s", async (key, moved) => {
  const user = userEvent.setup();
  renderLoadedMap();
  act(() => actions.setPin(KEY_POINT, "user"));
  screen.getByRole("button", { name: PIN_NAME }).focus();

  await user.keyboard(key);

  expect(getState().area.pin).toEqual(moved);
});

test("should keep the focus on the pin after an arrow key", async () => {
  const user = userEvent.setup();
  renderLoadedMap();
  act(() => actions.setPin(KEY_POINT, "user"));
  const pin = screen.getByRole("button", { name: PIN_NAME });
  pin.focus();

  await user.keyboard("{ArrowUp}");

  expect(pin).toHaveFocus();
});

test("should show no pin before a place is pinned", () => {
  renderLoadedMap();

  expect(screen.queryByRole("button", { name: PIN_NAME })).toBeNull();
});

test("should fly to the map target of the store", () => {
  const map = renderLoadedMap();

  act(() =>
    actions.setMapTarget({ center: { lat: 35.18, lon: 129.08 }, zoom: 6 }),
  );

  expect(map.flyTo).toHaveBeenCalledWith({ center: [129.08, 35.18], zoom: 6 });
});

test("should keep the zoom of the map when the target has none", () => {
  const map = renderLoadedMap();

  act(() =>
    actions.setMapTarget({ center: { lat: 35.18, lon: 129.08 }, zoom: null }),
  );

  expect(map.flyTo).toHaveBeenCalledWith({ center: [129.08, 35.18] });
});
