import { screen } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";

import { actions, resetStore } from "@/state/store";

import { renderRail, SEOUL } from "./rail-test-utils";

beforeEach(() => {
  resetStore();
  actions.chooseDoor("guided");
});

test.each([
  { preview: { cells: [], count: 12, usedContainingCell: false }, text: "12 grid cells inside the circle" },
  { preview: { cells: [], count: 1, usedContainingCell: true }, text: "No cell center falls inside the circle, so the app uses the cell that holds the pin." },
])("should say '$text' from the cell preview", ({ preview, text }) => {
  actions.setPin(SEOUL, "user");
  actions.setCellPreview(preview);
  actions.goToStep(3);
  renderRail();

  expect(screen.getByRole("status")).toHaveTextContent(text);
});

test.each(["Pin at 37.57, 126.98", "Radius 25 km"])(
  "should show '%s' on the place step",
  (text) => {
    actions.setPin(SEOUL, "user");
    actions.goToStep(3);
    renderRail();

    expect(screen.getByText(text)).toBeInTheDocument();
  },
);

test("should ask for a pin while no place is pinned", () => {
  actions.goToStep(3);
  renderRail();

  expect(screen.getByText(/No place is pinned yet/)).toBeInTheDocument();
});

test.each([
  { window: { start: 1981, end: "latest" as const }, text: "1981 to the latest valid month" },
  { window: { start: 1991, end: 2020 }, text: "1991 to 2020" },
])("should show the window as '$text'", ({ window, text }) => {
  actions.setWindow(window, "user");
  actions.goToStep(4);
  renderRail();

  expect(screen.getByText(text)).toBeInTheDocument();
});
