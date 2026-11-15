import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import {
  type DraftSpec,
  HEADER_RESULT_KEY,
  type TrendResult,
} from "@/contracts/types";
import { messages } from "@/i18n/messages";
import {
  hang,
  inTurn,
  jsonResponse,
  problemResponse,
  type Respond,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { actions, resetStore } from "@/state/store";
import {
  catalog,
  trendNoData,
  trendNoTrend,
  trendNotYet,
  trendSignificant,
  trendTooShort,
  trendZeroInside,
} from "@/test/fixtures";

import { CasePanel } from "./CasePanel";

const SNOW: DraftSpec = {
  var: "PRECSNO",
  metric: { id: "first_date", op: ">=", season_start: "08-01", threshold: "0.1" },
};
const SEOUL = { lat: 37.5665, lon: 126.978 };
const LAST_30_YEARS = { start: 1991, end: "latest" } as const;
const RESULT_KEY = "b5bae5463e95eff888bca78a896bf62a";
const CATALOG_PATH = "/meta/catalog.json";
const TREND_PATH = "/api/v1/trend?";
const RETRY = "Try again";

function answer(result: TrendResult): Respond {
  return () =>
    jsonResponse(result, { headers: { [HEADER_RESULT_KEY]: RESULT_KEY } });
}

const failure: Respond = () => problemResponse(500, "internal");

/** Serves the catalog, and the trend requests in turn. Every other path is not found. */
function serve(...trendTurns: Respond[]): void {
  const trend = inTurn(...trendTurns);
  stubFetch((call) => {
    if (call.url.endsWith(CATALOG_PATH)) {
      return jsonResponse(catalog);
    }
    if (call.url.includes(TREND_PATH)) {
      return trend(call);
    }
    return problemResponse(404, "not_found");
  });
}

/** The state after Confirm on the first-snow question: the trend panel is open. */
function openSeoulSnowTrend(): void {
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
  actions.openPanel("trend");
}

function renderPanel() {
  return render(
    <Providers>
      <NextIntlClientProvider locale="en" messages={messages.en} timeZone="UTC">
        <CasePanel />
      </NextIntlClientProvider>
    </Providers>,
  );
}

/** A revealed verdict on the screen, then a new window whose request answers in turn. */
async function showVerdictThenChangeWindow(): Promise<void> {
  openSeoulSnowTrend();
  actions.revealVerdict();
  renderPanel();
  await screen.findByRole("article");
  act(() => actions.setWindow(LAST_30_YEARS, "user"));
}

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should keep the slot test ID before a run", () => {
  renderPanel();

  expect(screen.getByTestId("slot-case")).toBeInTheDocument();
});

test("should invite a run before the first result", () => {
  renderPanel();

  expect(
    screen.getByText("Pick a place on the map, or ask a question, to see a tested trend here."),
  ).toBeInTheDocument();
});

test("should show a skeleton while the result loads", async () => {
  serve(hang);
  openSeoulSnowTrend();
  renderPanel();

  expect(
    await screen.findByRole("status", { name: "Loading the result" }),
  ).toBeInTheDocument();
});

test("should keep the slot test ID while the result loads", () => {
  serve(hang);
  openSeoulSnowTrend();
  renderPanel();

  expect(screen.getByTestId("slot-case")).toBeInTheDocument();
});

test.each([
  { name: "significant", result: trendSignificant, slot: "slot-board" },
  { name: "not yet", result: trendNotYet, slot: "slot-fallback" },
  { name: "zero inside", result: trendZeroInside, slot: "slot-fallback" },
  { name: "no trend", result: trendNoTrend, slot: "slot-fallback" },
])("should route a $name verdict to $slot", async ({ result, slot }) => {
  serve(answer(result));
  openSeoulSnowTrend();
  actions.revealVerdict();
  renderPanel();

  expect(await screen.findByTestId(slot)).toBeInTheDocument();
});

test.each([
  { name: "too-short", result: trendTooShort },
  { name: "no-data", result: trendNoData },
])("should open neither the board nor the fallback for a $name result", async ({ result }) => {
  serve(answer(result));
  openSeoulSnowTrend();
  actions.revealVerdict();
  renderPanel();
  await screen.findByRole("article");

  expect([
    screen.queryByTestId("slot-board"),
    screen.queryByTestId("slot-fallback"),
  ]).toEqual([null, null]);
});

test("should hide the verdict card while the verdict gate is pending", async () => {
  serve(answer(trendSignificant));
  openSeoulSnowTrend();
  renderPanel();
  await screen.findByTestId("slot-chart");

  expect(screen.queryByRole("article")).toBeNull();
});

test("should hide the board while the verdict gate is pending", async () => {
  serve(answer(trendSignificant));
  openSeoulSnowTrend();
  renderPanel();
  await screen.findByTestId("slot-chart");

  expect(screen.queryByTestId("slot-board")).toBeNull();
});

test("should show the verdict card after the verdict gate opens", async () => {
  serve(answer(trendSignificant));
  openSeoulSnowTrend();
  renderPanel();
  await screen.findByTestId("slot-chart");

  act(() => actions.revealVerdict());

  expect(await screen.findByRole("article")).toBeInTheDocument();
});

test("should show a no-data result without the verdict gate", async () => {
  serve(answer(trendNoData));
  openSeoulSnowTrend();
  renderPanel();

  expect(await screen.findByRole("article")).toBeInTheDocument();
});

test("should show the next steps with the verdict", async () => {
  serve(answer(trendSignificant));
  openSeoulSnowTrend();
  actions.revealVerdict();
  renderPanel();

  expect(
    await screen.findByRole("region", { name: "Next steps" }),
  ).toBeInTheDocument();
});

test("should show the message of a failed request", async () => {
  serve(failure);
  openSeoulSnowTrend();
  renderPanel();

  expect(
    await screen.findByText("The server could not answer this request."),
  ).toBeInTheDocument();
});

test("should offer a retry after a failed request", async () => {
  serve(failure);
  openSeoulSnowTrend();
  renderPanel();

  expect(await screen.findByRole("button", { name: RETRY })).toBeInTheDocument();
});

test("should keep the last verdict when the next request fails", async () => {
  serve(answer(trendSignificant), failure);
  await showVerdictThenChangeWindow();
  await screen.findByRole("button", { name: RETRY });

  expect(screen.getByRole("article")).toBeInTheDocument();
});

test("should say that a new request loads while the last verdict stays", async () => {
  serve(answer(trendSignificant), hang);
  await showVerdictThenChangeWindow();

  expect(
    await screen.findByText("Loading the result of the new request"),
  ).toBeInTheDocument();
});

test("should ask again on a retry", async () => {
  serve(failure, answer(trendSignificant));
  openSeoulSnowTrend();
  actions.revealVerdict();
  renderPanel();

  await userEvent.click(await screen.findByRole("button", { name: RETRY }));

  expect(await screen.findByRole("article")).toBeInTheDocument();
});

test("should ask again on a retry from the keyboard", async () => {
  serve(failure, answer(trendSignificant));
  openSeoulSnowTrend();
  actions.revealVerdict();
  renderPanel();
  (await screen.findByRole("button", { name: RETRY })).focus();

  await userEvent.keyboard("{Enter}");

  expect(await screen.findByRole("article")).toBeInTheDocument();
});

test("should move the focus to the panel when the retry button leaves", async () => {
  serve(failure, hang);
  openSeoulSnowTrend();
  renderPanel();

  await userEvent.click(await screen.findByRole("button", { name: RETRY }));

  expect(screen.getByTestId("slot-case")).toHaveFocus();
});

test("should give every control of the panel an accessible name", async () => {
  serve(answer(trendSignificant));
  openSeoulSnowTrend();
  actions.revealVerdict();
  renderPanel();
  await screen.findByRole("region", { name: "Next steps" });

  expect(screen.queryAllByRole("button", { name: "" })).toEqual([]);
});
