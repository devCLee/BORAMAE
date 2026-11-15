import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { API_BASE } from "@/config/flags";
import type { Catalog } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import { serve, stubFetch } from "@/lib/fetch-layer.stub";
import { actions, getState, resetStore } from "@/state/store";
import { catalog } from "@/test/fixtures";

import { TimeSlider } from "./TimeSlider";

const CATALOG_URL = `${API_BASE}/meta/catalog.json`;
const START = "Start year";
const END = "End year";
// A variable whose record starts and ends inside the track of 1981 to 2026-09.
const SHORT_RECORD: Catalog = {
  ...catalog,
  variables: catalog.variables.map((variable) =>
    variable.id === "T2M"
      ? { ...variable, record_start: "2001-01", record_end: "2020-12" }
      : variable,
  ),
};
// jsdom lays nothing out. 450 px over the 45 years of the track is 10 px a year.
const TRACK_RECT = { x: 0, y: 0, width: 450, height: 16 };

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function renderSlider(served: Catalog = catalog) {
  stubFetch(serve({ [CATALOG_URL]: served }));
  return render(
    <NextIntlClientProvider locale="en" messages={messages.en} timeZone="UTC">
      <Providers>
        <TimeSlider />
      </Providers>
    </NextIntlClientProvider>,
  );
}

async function focusT2M() {
  actions.editDraft({ var: "T2M", metric: { id: "annual_mean" } }, "user");
  renderSlider(SHORT_RECORD);
  return screen.findByRole("slider", { name: START });
}

/** Drags with the pointer on the track, as a hand does: down, two moves, up. */
async function dragTrack(fromX: number, toX: number) {
  await screen.findByRole("slider", { name: START });
  const track = screen.getByTestId("window-slider");
  vi.spyOn(track, "getBoundingClientRect").mockReturnValue(
    DOMRect.fromRect(TRACK_RECT),
  );
  track.setPointerCapture = () => {};
  track.releasePointerCapture = () => {};
  track.hasPointerCapture = () => true;
  fireEvent.pointerDown(track, { pointerId: 1, clientX: fromX });
  fireEvent.pointerMove(track, { pointerId: 1, clientX: (fromX + toX) / 2 });
  fireEvent.pointerMove(track, { pointerId: 1, clientX: toX });
  fireEvent.pointerUp(track, { pointerId: 1, clientX: toX });
}

test.each([
  { name: START, bound: "aria-valuemin", year: "2001" },
  { name: END, bound: "aria-valuemax", year: "2020" },
])(
  "should keep the $name inside the record of the focus variable",
  async ({ name, bound, year }) => {
    await focusT2M();

    expect(screen.getByRole("slider", { name })).toHaveAttribute(bound, year);
  },
);

test("should call setWindow once with the source user when a drag ends", async () => {
  const setWindow = vi.spyOn(actions, "setWindow");
  renderSlider();

  await dragTrack(0, 200);

  expect(setWindow.mock.calls).toEqual([
    [{ start: 2001, end: "latest" }, "user"],
  ]);
});

test("should store latest when the end thumb reaches its maximum", async () => {
  actions.setWindow({ start: 1981, end: 2020 }, "user");
  renderSlider();
  const end = await screen.findByRole("slider", { name: END });

  end.focus();
  await userEvent.keyboard("{End}");

  expect(getState().window).toEqual({ start: 1981, end: "latest" });
});

test.each([
  { name: START, key: "{ArrowRight}", window: { start: 1982, end: "latest" } },
  { name: END, key: "{ArrowLeft}", window: { start: 1981, end: 2025 } },
])(
  "should move the $name by keyboard with $key",
  async ({ name, key, window }) => {
    renderSlider();
    const thumb = await screen.findByRole("slider", { name });

    thumb.focus();
    await userEvent.keyboard(key);

    expect(getState().window).toEqual(window);
  },
);

test("should show the pinned end month as the end label", async () => {
  renderSlider();

  expect(await screen.findByText("Sep 2026 (latest)")).toBeInTheDocument();
});

test("should show the end year as the end label of an earlier end", async () => {
  actions.setWindow({ start: 1981, end: 2020 }, "user");
  renderSlider();

  expect(await screen.findByText("2020")).toBeInTheDocument();
});

test("should show the record-guard notice for a window under 20 years", async () => {
  actions.setWindow({ start: 2011, end: 2020 }, "user");
  renderSlider();

  expect(await screen.findByRole("status")).toHaveTextContent(
    "This window holds 10 years. A trend needs at least 20, so the result shows the statistics and gives no verdict.",
  );
});

test("should show no record-guard notice for the full record", async () => {
  renderSlider();
  await screen.findByRole("slider", { name: START });

  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test.each(["coverage-gap-start", "coverage-gap-end"])(
  "should draw the %s beyond the record muted",
  async (testId) => {
    await focusT2M();

    expect(screen.getByTestId(testId)).toHaveClass("bg-coverage-muted");
  },
);

test("should say in words which years lie beyond the record", async () => {
  await focusT2M();

  expect(
    screen.getByText("Years outside 2001 to 2020 have no data for this variable and are grayed out."),
  ).toBeInTheDocument();
});

test("should keep the slot test ID while the catalog loads", () => {
  renderSlider();

  expect(screen.getByTestId("slot-window")).toBeInTheDocument();
});
