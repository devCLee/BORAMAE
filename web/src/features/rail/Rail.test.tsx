import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import {
  hang,
  inTurn,
  jsonResponse,
  serve,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { MARK_SKIP_ACTIVATED } from "@/lib/perf";
import { actions, getState, resetStore } from "@/state/store";
import type { Step } from "@/state/types";
import { catalog, parseInput1En, parseInput1Ko } from "@/test/fixtures";

import {
  ask,
  CATALOG_URL,
  openVariables,
  QUESTION_EN,
  renderRail,
  SEOUL,
  TREND_PATH,
} from "./rail-test-utils";

const JEJU = { lat: 33.4996, lon: 126.5312 };

beforeEach(() => {
  resetStore();
  performance.clearMarks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function urlsOf(calls: { url: string }[]): string[] {
  return calls.map((call) => call.url);
}

async function confirmSpec() {
  await userEvent.click(
    await screen.findByRole("button", { name: "Confirm and run" }),
  );
}

test.each([
  { door: "Start investigating", mode: "guided" },
  { door: "Explore freely", mode: "explore" },
  { door: "Watch a demo", mode: "demo" },
])("should set the mode $mode from the door $door", async ({ door, mode }) => {
  renderRail();

  await userEvent.click(screen.getByRole("button", { name: door }));

  expect(getState().mode).toBe(mode);
});

test("should choose a door with the keyboard", async () => {
  renderRail();

  await userEvent.tab();
  await userEvent.keyboard("{Enter}");

  expect(getState().mode).toBe("guided");
});

test("should open the question step after the guided door", async () => {
  renderRail();

  await userEvent.click(
    screen.getByRole("button", { name: "Start investigating" }),
  );

  expect(
    screen.getByRole("heading", { name: "What to investigate" }),
  ).toBeInTheDocument();
});

test("should move to the variables step when parse answers", async () => {
  await openVariables();

  expect(getState().step).toBe(2);
});

test("should move to the place step when a variable is confirmed", async () => {
  await openVariables();

  await userEvent.click((await screen.findByRole("button", { name: "Confirm Snowfall" })));

  expect(screen.getByRole("heading", { name: "Place" })).toBeInTheDocument();
});

test("should move to the time window step with Next", async () => {
  actions.chooseDoor("guided");
  actions.goToStep(3);
  renderRail();

  await userEvent.click(screen.getByRole("button", { name: "Next" }));

  expect(getState().step).toBe(4);
});

test("should focus the heading of the new step", async () => {
  actions.chooseDoor("guided");
  actions.goToStep(3);
  renderRail();

  await userEvent.click(screen.getByRole("button", { name: "Next" }));

  expect(screen.getByRole("heading", { name: "Time window" })).toHaveFocus();
});

test.each([2, 3, 4] as Step[])(
  "should return from step %i to the step before with Back",
  async (step) => {
    actions.chooseDoor("guided");
    actions.goToStep(step);
    renderRail();

    await userEvent.click(screen.getByRole("button", { name: "Back" }));

    expect(getState().step).toBe(step - 1);
  },
);

test("should return to the doors with Back on the first step", async () => {
  actions.chooseDoor("guided");
  renderRail();

  await userEvent.click(screen.getByRole("button", { name: "Back" }));

  expect(getState().mode).toBeNull();
});

test.each([1, 2, 3, 4] as Step[])(
  "should open explore mode with Skip on step %i",
  async (step) => {
    actions.chooseDoor("guided");
    actions.goToStep(step);
    renderRail();

    await userEvent.click(screen.getByRole("button", { name: "Skip to explore" }));

    expect(getState().mode).toBe("explore");
  },
);

test.each([1, 2, 3, 4] as Step[])(
  "should set the skip mark with Skip on step %i",
  async (step) => {
    actions.chooseDoor("guided");
    actions.goToStep(step);
    renderRail();

    await userEvent.click(screen.getByRole("button", { name: "Skip to explore" }));

    expect(performance.getEntriesByName(MARK_SKIP_ACTIVATED)).toHaveLength(1);
  },
);

test.each([1, 2, 3, 4] as Step[])(
  "should send no request with Skip on step %i",
  async (step) => {
    const calls = stubFetch(serve({}));
    actions.chooseDoor("guided");
    actions.goToStep(step);
    renderRail();

    await userEvent.click(screen.getByRole("button", { name: "Skip to explore" }));

    expect(calls).toEqual([]);
  },
);

test("should show the explore hint after Skip", async () => {
  actions.chooseDoor("guided");
  renderRail();

  await userEvent.click(screen.getByRole("button", { name: "Skip to explore" }));

  expect(screen.getByText(/Explore mode/)).toBeInTheDocument();
});

test("should send the question to parse once", async () => {
  const calls = await openVariables();

  expect(calls.filter((call) => call.method === "POST")).toHaveLength(1);
});

test("should abort the first parse when a second question follows", async () => {
  const answerParse = inTurn(hang, () => jsonResponse(parseInput1En));
  const calls = stubFetch((call) =>
    call.url === CATALOG_URL ? jsonResponse(catalog) : answerParse(call),
  );
  actions.chooseDoor("guided");
  renderRail();

  await ask("Is it snowing less in Gangwon?");
  await ask(QUESTION_EN);

  expect(calls[0].signal?.aborted).toBe(true);
});

test("should show the error of a failed parse", async () => {
  stubFetch(serve({ [CATALOG_URL]: catalog }));
  actions.chooseDoor("guided");
  renderRail();

  await ask();

  expect(
    await screen.findByText("The server could not answer this request."),
  ).toBeInTheDocument();
});

test("should send no analysis request before Confirm", async () => {
  const calls = await openVariables();
  act(() => actions.setPin(SEOUL, "user"));

  await userEvent.click((await screen.findByRole("button", { name: "Confirm Snowfall" })));

  expect(urlsOf(calls)).not.toContainEqual(expect.stringContaining(TREND_PATH));
});

test("should send the trend request on Confirm", async () => {
  const calls = await openVariables();
  act(() => actions.setPin(SEOUL, "user"));

  await confirmSpec();

  expect(urlsOf(calls)).toContainEqual(expect.stringContaining(TREND_PATH));
});

test("should hold the draft as the confirmed spec after Confirm", async () => {
  await openVariables();
  act(() => actions.setPin(SEOUL, "user"));

  await confirmSpec();

  expect(getState().confirmedSpec).toEqual(getState().draftSpec);
});

test("should show Confirm again after a pin change", async () => {
  await openVariables();
  act(() => actions.setPin(SEOUL, "user"));
  await confirmSpec();

  act(() => actions.setPin(JEJU, "user"));

  expect(
    screen.getByRole("button", { name: "Confirm and run" }),
  ).toBeInTheDocument();
});

test("should read the spec back in one sentence", async () => {
  await openVariables();

  act(() => actions.setPin(SEOUL, "user"));

  expect(
    await screen.findByText(
      "Seoul within 25 km: First date of Snowfall, at or above 0.1 mm/day, 1981 onward?",
    ),
  ).toBeInTheDocument();
});

test("should read the spec back in Korean", async () => {
  await openVariables(parseInput1Ko, "ko");

  act(() => actions.setPin(SEOUL, "user"));

  expect(
    await screen.findByText(
      "서울 반경 25 km, 1981년 이후 강설량 첫 날짜(0.1 mm/일 이상)의 추세를 볼까요?",
    ),
  ).toBeInTheDocument();
});

test("should read back the map view when no place is pinned", async () => {
  await openVariables();

  expect(
    await screen.findByText(
      "The current map view: First date of Snowfall, at or above 0.1 mm/day, 1981 onward?",
    ),
  ).toBeInTheDocument();
});
