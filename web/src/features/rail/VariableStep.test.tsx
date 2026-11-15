import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { ParseProposal } from "@/contracts/types";
import { actions, getState, resetStore } from "@/state/store";
import { parseInput1En } from "@/test/fixtures";

import {
  decodeRequest,
  openVariables,
  SEOUL,
  TREND_PATH,
} from "./rail-test-utils";

const EMPTY: ParseProposal = { ...parseInput1En, variables: [] };
const FINE_DUST: ParseProposal = {
  ...parseInput1En,
  unavailable: { requested: "PM2.5", nearest_var: "PBLTOP" },
};

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function firstCard() {
  const list = await screen.findByRole("list", { name: "Proposed variables" });
  return within(list).getAllByRole("listitem")[0];
}

async function confirmSpec() {
  act(() => actions.setPin(SEOUL, "user"));
  await userEvent.click(screen.getByRole("button", { name: "Confirm and run" }));
}

async function pickInCatalog(trigger: HTMLElement, name: string) {
  await userEvent.click(trigger);
  const dialog = await screen.findByRole("dialog", {
    name: "Pick a variable from the catalog",
  });
  await userEvent.click(within(dialog).getByRole("button", { name }));
}

test.each(["mm/day", "NASA POWER (MERRA-2)", "1981–2026", "Trend-ready", "Model data"])(
  "should show %s on a variable card",
  async (fact) => {
    await openVariables();

    expect(within(await firstCard()).getByText(fact)).toBeInTheDocument();
  },
);

test("should show the catalog definition on a variable card", async () => {
  await openVariables();

  expect(
    within(await firstCard()).getByText(
      "The part of precipitation that falls as snow",
    ),
  ).toBeInTheDocument();
});

test("should give the reason of the proposal from its template", async () => {
  await openVariables();

  expect(
    within(await firstCard()).getByText("Your question names this quantity."),
  ).toBeInTheDocument();
});

test("should show one card for each proposed variable", async () => {
  await openVariables();
  const list = screen.getByRole("list", { name: "Proposed variables" });

  expect(within(list).getAllByRole("listitem")).toHaveLength(3);
});

test("should still offer the catalog picker for an empty proposal", async () => {
  await openVariables(EMPTY);

  expect(
    screen.getByRole("button", { name: "Add from the catalog" }),
  ).toBeInTheDocument();
});

test("should say that no variable matched an empty proposal", async () => {
  await openVariables(EMPTY);

  expect(
    screen.getByText(
      "No variable matched your question. Pick one from the catalog.",
    ),
  ).toBeInTheDocument();
});

test.each([
  "PM2.5 is not in this version.",
  "The nearest variable is Boundary-layer top.",
])("should show '%s' for an unavailable variable", async (text) => {
  await openVariables(FINE_DUST);

  expect(await screen.findByText(text)).toBeInTheDocument();
});

test("should put a swapped variable in the draft", async () => {
  await openVariables();

  await pickInCatalog(
    await screen.findByRole("button", { name: "Swap Snowfall" }),
    "Air temperature",
  );

  expect(getState().draftSpec).toEqual({
    var: "T2M",
    metric: { id: "annual_mean" },
  });
});

test("should clear the confirmation on a swap after confirm", async () => {
  await openVariables();
  await confirmSpec();

  await pickInCatalog(
    await screen.findByRole("button", { name: "Swap Snowfall" }),
    "Air temperature",
  );

  expect(getState().confirmedSpec).toBeNull();
});

test("should return focus to Swap after a pick", async () => {
  await openVariables();
  const swap = await screen.findByRole("button", { name: "Swap Snowfall" });

  await pickInCatalog(swap, "Air temperature");

  await waitFor(() => expect(swap).toHaveFocus());
});

test("should return focus to Swap when the picker closes on Escape", async () => {
  await openVariables();
  const swap = await screen.findByRole("button", { name: "Swap Snowfall" });
  await userEvent.click(swap);
  await screen.findByRole("dialog");

  await userEvent.keyboard("{Escape}");

  await waitFor(() => expect(swap).toHaveFocus());
});

test("should add a card from the catalog", async () => {
  await openVariables(EMPTY);

  await pickInCatalog(
    screen.getByRole("button", { name: "Add from the catalog" }),
    "Wind speed",
  );

  expect(await firstCard()).toHaveTextContent("Wind speed");
});

test("should show the definition of the metric", async () => {
  await openVariables();

  expect(
    await screen.findByText(
      "The day of the season year on which a threshold is first crossed",
    ),
  ).toBeInTheDocument();
});

test("should clear the confirmation when the threshold changes", async () => {
  await openVariables();
  await confirmSpec();
  const threshold = await screen.findByRole("spinbutton", {
    name: "Threshold (mm/day)",
  });

  await userEvent.clear(threshold);
  await userEvent.type(threshold, "1");

  expect(getState().confirmedSpec).toBeNull();
});

test("should send the new threshold with the next request", async () => {
  const calls = await openVariables();
  await confirmSpec();
  const threshold = await screen.findByRole("spinbutton", {
    name: "Threshold (mm/day)",
  });
  await userEvent.clear(threshold);
  await userEvent.type(threshold, "1");

  await userEvent.click(screen.getByRole("button", { name: "Confirm and run" }));

  const trendCalls = calls.filter((call) => call.url.includes(TREND_PATH));
  expect(decodeRequest(trendCalls[1].url).metric.threshold).toBe("1");
});

test("should confirm a card with the keyboard", async () => {
  await openVariables();
  (await screen.findByRole("button", { name: "Confirm Snowfall" })).focus();

  await userEvent.keyboard("{Enter}");

  expect(getState().step).toBe(3);
});

test("should leave no control of the variables step without a name", async () => {
  await openVariables();
  await screen.findByRole("spinbutton", { name: "Threshold (mm/day)" });

  expect(screen.queryAllByRole("button", { name: "" })).toEqual([]);
});
