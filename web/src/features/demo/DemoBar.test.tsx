import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { DemoStep } from "@/contracts/types";
import { reduceMotion } from "@/features/chart/chart-test-kit";
import { messages } from "@/i18n/messages";
import { serve, stubFetch } from "@/lib/fetch-layer.stub";
import { actions, getState, resetStore } from "@/state/store";
import type { AppState } from "@/state/types";
import { parseInput1Ko } from "@/test/fixtures";
import goldenVectors from "@content/golden/request-spec.json";

import { verdictIndexOf } from "./demo-content";
import {
  bundle,
  indexOfAction,
  manifestWithTrendS,
  pressNext,
  Screen,
  SNOW,
  SNOW_SCRIPT,
  startSnowDemo,
} from "./demo-test-kit";
import { STEP_MS } from "./play-step";

const router = vi.hoisted(() => ({ replace: vi.fn() }));

// The player navigates with the next-intl router, which needs the app router of Next.js.
vi.mock("@/i18n/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/i18n/navigation")>()),
  useRouter: () => router,
  usePathname: () => "/",
}));
// The overlay is LanguageGate, which holds the Next.js router even when onChoose navigates.
vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const VERDICT_INDEX = verdictIndexOf(SNOW_SCRIPT);
const LAST_INDEX = SNOW_SCRIPT.steps.length - 1;
const SNOW_DRAFT = { var: SNOW.specs.trend.var, metric: SNOW.specs.trend.metric };
const JUDGE_LINK = `/ko/?demo=${SNOW.id}&at=result`;
/** A valid request that no demo case holds. */
const OTHER_S = goldenVectors[7].s;

type Select = (state: AppState) => unknown;

function chooseKorean(): void {
  const overlay = screen.getByRole("dialog", { name: "Choose a language" });
  fireEvent.click(within(overlay).getByRole("button", { name: "한국어" }));
}

function captionIn(regionName: string, caption: string): HTMLElement {
  return within(screen.getByRole("region", { name: regionName })).getByText(caption);
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  router.replace.mockClear();
  resetStore();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("should switch the fetch layer to the fixture source when a demo starts", async () => {
  await startSnowDemo();

  expect(getState().fetchSource).toBe("fixture");
});

test.each(["English", "한국어"])(
  "should offer %s in the overlay of the first step",
  async (language) => {
    await startSnowDemo();

    const overlay = screen.getByRole("dialog", { name: "Choose a language" });

    expect(within(overlay).getByRole("button", { name: language })).toBeInTheDocument();
  },
);

test("should open the route of the script's language after the choice", async () => {
  await startSnowDemo();

  chooseKorean();

  expect(router.replace).toHaveBeenCalledWith("/", { locale: SNOW.lang });
});

test("should show step 2 after the choice", async () => {
  await startSnowDemo();

  chooseKorean();

  expect(
    screen.getByText(`Step 2 of ${SNOW_SCRIPT.steps.length}`),
  ).toBeInTheDocument();
});

test("should caption the next step in the script's language after the route change", async () => {
  const { view } = await startSnowDemo();
  chooseKorean();

  view.rerender(<Screen key="ko" locale="ko" />);

  expect(captionIn("데모 플레이어", SNOW_SCRIPT.steps[1].caption.ko)).toBeInTheDocument();
});

test.each<[DemoStep["action"], Select, unknown]>([
  ["type_question", (state) => state.question, SNOW.question.ko],
  ["submit_question", (state) => state.proposal, parseInput1Ko],
  ["confirm_variables", (state) => state.draftSpec, SNOW_DRAFT],
  [
    "set_pin",
    (state) => state.area,
    { pin: { lat: SNOW.area.lat, lon: SNOW.area.lon }, radiusKm: SNOW.area.radius_km },
  ],
  ["set_window", (state) => state.window, SNOW.window],
  ["confirm_spec", (state) => state.confirmedSpec, SNOW_DRAFT],
  ["show_verdict", (state) => state.verdictGate, "revealed"],
  ["open_fallback", (state) => state.openPanels.includes("scan"), true],
])("should run the store action of the %s step", async (action, select, expected) => {
  await startSnowDemo();

  pressNext(indexOfAction(action));

  await waitFor(() => expect(select(getState())).toEqual(expected));
});

test("should move to the next step by itself while playing", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  await startSnowDemo();

  act(() => vi.advanceTimersByTime(STEP_MS));

  expect(getState().demo?.stepIndex).toBe(1);
});

test("should hold the step while paused", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  await startSnowDemo();
  fireEvent.click(screen.getByRole("button", { name: "Pause" }));

  act(() => vi.advanceTimersByTime(STEP_MS * 3));

  expect(getState().demo?.stepIndex).toBe(0);
});

test("should not move by itself with reduced motion", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  reduceMotion();
  await startSnowDemo();

  act(() => vi.advanceTimersByTime(STEP_MS * 3));

  expect(getState().demo?.stepIndex).toBe(0);
});

test("should move exactly one step with the step control", async () => {
  await startSnowDemo();
  pressNext(3);

  fireEvent.click(screen.getByRole("button", { name: "Next step" }));

  expect(getState().demo?.stepIndex).toBe(4);
});

test("should jump to the verdict step with Skip to the result", async () => {
  await startSnowDemo();

  fireEvent.click(screen.getByRole("button", { name: "Skip to the result" }));

  expect(getState().demo?.stepIndex).toBe(VERDICT_INDEX);
});

test("should show the verdict card of the bundle after Skip to the result", async () => {
  await startSnowDemo();

  fireEvent.click(screen.getByRole("button", { name: "Skip to the result" }));

  expect(await screen.findByText(messages.en.verdict.sentences.no_trend)).toBeInTheDocument();
});

test("should show the offline state for a request that the manifest does not hold", async () => {
  await startSnowDemo("en", manifestWithTrendS(OTHER_S));

  fireEvent.click(screen.getByRole("button", { name: "Skip to the result" }));

  expect(
    await screen.findByText(messages.en.errors.messages.not_in_offline_demo),
  ).toBeInTheDocument();
});

test("should restore the live source when the demo ends", async () => {
  await startSnowDemo();

  fireEvent.click(screen.getByRole("button", { name: "Leave the demo" }));

  expect(getState().fetchSource).toBe("live");
});

test.each(SNOW_SCRIPT.steps.map((step, index) => [index, step.caption.en]))(
  "should caption step %i in the UI language",
  async (index, caption) => {
    await startSnowDemo();

    pressNext(index);

    expect(captionIn("Demo player", caption)).toBeInTheDocument();
  },
);

test("should show the closing card on the last step", async () => {
  await startSnowDemo();

  pressNext(LAST_INDEX);

  expect(screen.getByRole("dialog", { name: "About BORAMAE" })).toBeInTheDocument();
});

test("should render the verdict card from bundled files at the judge link", async () => {
  window.history.replaceState(null, "", JUDGE_LINK);
  stubFetch(serve(bundle()));

  render(<Screen locale="ko" />);

  expect(await screen.findByText(messages.ko.verdict.sentences.no_trend)).toBeInTheDocument();
});

test("should send no live request at the judge link", async () => {
  window.history.replaceState(null, "", JUDGE_LINK);
  const calls = stubFetch(serve(bundle()));
  render(<Screen locale="ko" />);

  await screen.findByText(messages.ko.verdict.sentences.no_trend);

  expect(calls.map(({ url }) => url).filter((url) => !url.startsWith("/demo/"))).toEqual([]);
});

test("should hold the verdict step at the judge link", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  window.history.replaceState(null, "", JUDGE_LINK);
  stubFetch(serve(bundle()));
  render(<Screen locale="ko" />);
  await screen.findByText(messages.ko.verdict.sentences.no_trend);

  act(() => vi.advanceTimersByTime(STEP_MS * 3));

  expect(getState().demo?.stepIndex).toBe(VERDICT_INDEX);
});

test.each<[string, Select, unknown]>([
  ["Pause", (state) => state.demo?.isPaused, true],
  ["Next step", (state) => state.demo?.stepIndex, 1],
  ["Skip to the result", (state) => state.demo?.stepIndex, VERDICT_INDEX],
  ["Leave the demo", (state) => state.demo, null],
])("should work the %s control from the keyboard", async (name, select, expected) => {
  await startSnowDemo();
  screen.getByRole("button", { name }).focus();

  await userEvent.keyboard("{Enter}");

  expect(select(getState())).toBe(expected);
});

test("should move the focus to the player when a demo starts", async () => {
  await startSnowDemo();

  expect(screen.getByRole("button", { name: "Pause" })).toHaveFocus();
});

test("should return the focus to the demo list when the demo ends", async () => {
  await startSnowDemo();

  fireEvent.click(screen.getByRole("button", { name: "Leave the demo" }));

  expect(screen.getByRole("heading", { name: "Watch a demo" })).toHaveFocus();
});

test("should list the two demo cases behind the demo door", async () => {
  stubFetch(serve(bundle()));
  actions.chooseDoor("demo");

  render(<Screen locale="en" />);

  expect(await screen.findAllByRole("button", { name: /Plays in/ })).toHaveLength(2);
});

test("should say so when the build holds no demo files", async () => {
  stubFetch(serve({}));
  actions.chooseDoor("demo");

  render(<Screen locale="en" />);

  expect(await screen.findByText(messages.en.demo.cases.missing)).toBeInTheDocument();
});
