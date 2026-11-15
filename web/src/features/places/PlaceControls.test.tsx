import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { Lang } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import { actions, getState, resetStore } from "@/state/store";
import { parseInput1En } from "@/test/fixtures";

import { PlaceControls } from "./PlaceControls";

const SEARCH = "Find a place";
const RADIUS = "Radius";
// The kr-seoul and kr-busan rows of content/gazetteer.json.
const SEOUL = { lat: 37.568295, lon: 126.997785 };
const BUSAN = { lat: 35.096999, lon: 129.008102 };
const SEORAKSAN = { lat: 38.119, lon: 128.465 };
const PARSED = { lat: 37.5665, lon: 126.978 };
// jsdom lays nothing out. 290 px over 10 to 300 km is 1 px a kilometer.
const TRACK_RECT = { x: 0, y: 0, width: 290, height: 16 };

beforeEach(() => {
  resetStore();
  actions.chooseDoor("guided");
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderControls(locale: Lang = "en") {
  return render(
    <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
      <PlaceControls />
    </NextIntlClientProvider>,
  );
}

async function search(text: string, locale: Lang = "en") {
  await userEvent.type(
    screen.getByRole("combobox", { name: messages[locale].places.search.label }),
    text,
  );
}

test("should keep the slot test ID", () => {
  renderControls();

  expect(screen.getByTestId("slot-places")).toBeInTheDocument();
});

test("should set the pin with the source user when a place is chosen", async () => {
  const setPin = vi.spyOn(actions, "setPin");
  renderControls();
  await search("Seoul");

  await userEvent.click(screen.getByRole("option", { name: /^Seoul/ }));

  expect(setPin.mock.calls).toEqual([[SEOUL, "user"]]);
});

test("should set the map target to the chosen place", async () => {
  renderControls();
  await search("Busan");

  await userEvent.click(screen.getByRole("option", { name: /^Busan/ }));

  expect(getState().mapTarget).toEqual({ center: BUSAN, zoom: null });
});

test("should find a place by its Korean name in the Korean UI", async () => {
  actions.setLang("ko");
  renderControls("ko");
  await search("부산", "ko");

  await userEvent.click(screen.getByRole("option", { name: /^부산/ }));

  expect(getState().area.pin).toEqual(BUSAN);
});

test.each([
  { keys: "{ArrowDown}{Enter}", pin: SEOUL },
  { keys: "{ArrowDown}{ArrowDown}{Enter}", pin: SEORAKSAN },
  { keys: "{ArrowDown}{ArrowDown}{ArrowUp}{Enter}", pin: SEOUL },
  { keys: "{Enter}", pin: SEOUL },
])("should pin with the keys $keys in the search list", async ({ keys, pin }) => {
  renderControls();
  await search("Seo");

  await userEvent.keyboard(keys);

  expect(getState().area.pin).toEqual(pin);
});

test("should close the search list with Escape", async () => {
  renderControls();
  await search("Seo");

  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

test("should return the focus to the search field after a click on a place", async () => {
  renderControls();
  await search("Seoul");

  await userEvent.click(screen.getByRole("option", { name: /^Seoul/ }));

  expect(screen.getByRole("combobox", { name: SEARCH })).toHaveFocus();
});

test("should say so when no place matches the name", async () => {
  renderControls();
  await search("Atlantis");

  expect(screen.getByRole("status")).toHaveTextContent(
    "No place in the list is called “Atlantis”. Click the map to pin the place instead.",
  );
});

test("should keep the map pin when no place matches the name", async () => {
  actions.setPin(BUSAN, "user");
  renderControls();
  await search("Atlantis{Enter}");

  expect(getState().area.pin).toEqual(BUSAN);
});

test("should start the radius at 25 km", () => {
  renderControls();

  expect(screen.getByRole("slider", { name: RADIUS })).toHaveAttribute(
    "aria-valuenow",
    "25",
  );
});

test.each([
  { key: "{Home}", radius: 10 },
  { key: "{End}", radius: 300 },
  { key: "{ArrowRight}", radius: 26 },
])("should keep the radius inside 10 to 300 km with $key", async ({ key, radius }) => {
  renderControls();

  screen.getByRole("slider", { name: RADIUS }).focus();
  await userEvent.keyboard(key);

  expect(getState().area.radiusKm).toBe(radius);
});

test("should call setRadius once with the source user when a drag ends", async () => {
  const setRadius = vi.spyOn(actions, "setRadius");
  renderControls();
  const track = screen.getByTestId("radius-slider");
  vi.spyOn(track, "getBoundingClientRect").mockReturnValue(
    DOMRect.fromRect(TRACK_RECT),
  );
  track.setPointerCapture = () => {};
  track.releasePointerCapture = () => {};
  track.hasPointerCapture = () => true;

  fireEvent.pointerDown(track, { pointerId: 1, clientX: 15 });
  fireEvent.pointerMove(track, { pointerId: 1, clientX: 40 });
  fireEvent.pointerMove(track, { pointerId: 1, clientX: 90 });
  fireEvent.pointerUp(track, { pointerId: 1, clientX: 90 });

  expect(setRadius.mock.calls).toEqual([[100, "user"]]);
});

test("should pin the parsed place when no pin exists", () => {
  renderControls();

  act(() => actions.setProposal(parseInput1En));

  expect(getState().area.pin).toEqual(PARSED);
});

test("should fly the map to the parsed place", () => {
  renderControls();

  act(() => actions.setProposal(parseInput1En));

  expect(getState().mapTarget).toEqual({ center: PARSED, zoom: null });
});

test("should never move a manual pin for a later proposal", () => {
  renderControls();
  act(() => actions.setProposal(parseInput1En));
  act(() => actions.setPin(BUSAN, "user"));

  act(() => actions.setProposal({ ...parseInput1En }));

  expect(getState().area.pin).toEqual(BUSAN);
});
