import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { hang, stubFetch } from "@/lib/fetch-layer.stub";
import { MARK_FIRST_CHART_RENDERED } from "@/lib/perf";
import { actions, getState, resetStore } from "@/state/store";
import { trendSignificant } from "@/test/fixtures";

import {
  EN,
  openTrendPanel,
  reduceMotion,
  renderChart,
  showChart,
} from "./chart-test-kit";

beforeEach(() => {
  resetStore();
  performance.clearMarks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should show the tap before the verdict gate opens", async () => {
  await showChart(trendSignificant);

  expect(
    screen.getByRole("group", { name: EN.tap.question }),
  ).toBeInTheDocument();
});

test("should hide the tap once the verdict is revealed", async () => {
  await showChart(trendSignificant);
  act(() => actions.revealVerdict());

  expect(
    screen.queryByRole("group", { name: EN.tap.question }),
  ).not.toBeInTheDocument();
});

test.each([EN.tap.yes, EN.tap.no, EN.tap.skip])(
  "should reveal the verdict on the answer %s",
  async (answer) => {
    await showChart(trendSignificant);

    await userEvent.click(screen.getByRole("button", { name: answer }));

    expect(getState().verdictGate).toBe("revealed");
  },
);

test("should send no request with the answer", async () => {
  const calls = await showChart(trendSignificant);
  const sentBefore = calls.length;

  await userEvent.click(screen.getByRole("button", { name: EN.tap.yes }));

  expect(calls).toHaveLength(sentBefore);
});

test("should take an answer by keyboard", async () => {
  await showChart(trendSignificant);
  screen.getByRole("button", { name: EN.tap.no }).focus();

  await userEvent.keyboard("{Enter}");

  expect(getState().verdictGate).toBe("revealed");
});

test("should return the focus to the chart after the answer", async () => {
  await showChart(trendSignificant);

  await userEvent.click(screen.getByRole("button", { name: EN.tap.skip }));

  expect(screen.getByRole("figure")).toHaveFocus();
});

test("should draw the trend line in the neutral role before the verdict shows", async () => {
  await showChart(trendSignificant);

  expect(screen.getByTestId("chart-trend-line")).toHaveClass("stroke-not-yet");
});

test("should draw the trend line in the role of the verdict once it shows", async () => {
  await showChart(trendSignificant);
  act(() => actions.revealVerdict());

  expect(screen.getByTestId("chart-trend-line")).toHaveClass(
    "stroke-trend-rise",
  );
});

test("should draw the series in", async () => {
  await showChart(trendSignificant);

  expect(screen.getByTestId("chart-series")).toHaveClass("animate-in");
});

test("should not draw the series in with reduced motion", async () => {
  reduceMotion();
  await showChart(trendSignificant);

  expect(screen.getByTestId("chart-series")).not.toHaveClass("animate-in");
});

test("should set the first-chart mark after the chart shows its data", async () => {
  await showChart(trendSignificant);

  await waitFor(() =>
    expect(
      performance.getEntriesByName(MARK_FIRST_CHART_RENDERED),
    ).toHaveLength(1),
  );
});

test("should not set the first-chart mark while the result loads", () => {
  stubFetch(hang);
  openTrendPanel();

  renderChart();

  expect(performance.getEntriesByName(MARK_FIRST_CHART_RENDERED)).toHaveLength(
    0,
  );
});
