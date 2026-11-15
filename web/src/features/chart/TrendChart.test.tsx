import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { TrendResult } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import { hang, problemResponse, stubFetch } from "@/lib/fetch-layer.stub";
import { resetStore } from "@/state/store";
import {
  trendNoData,
  trendNoTrend,
  trendSignificant,
  trendTooShort,
} from "@/test/fixtures";

import {
  EN,
  openTrendPanel,
  renderChart,
  serveTrend,
  showChart,
} from "./chart-test-kit";

const CENSORED_YEAR = "2019";
const EMPTY_STATS: TrendResult = {
  ...trendTooShort,
  stats: {
    ...trendTooShort.stats,
    sen: { slope: null, intercept: null, ci_low: null, ci_high: null },
  },
};

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should keep the slot element while no trend panel is open", () => {
  serveTrend(trendSignificant);

  renderChart();

  expect(screen.getByTestId("slot-chart")).toBeInTheDocument();
});

test("should keep the slot element while the result loads", () => {
  stubFetch(hang);
  openTrendPanel();

  renderChart();

  expect(screen.getByTestId("slot-chart")).toBeInTheDocument();
});

test("should show a loading state while the result loads", () => {
  stubFetch(hang);
  openTrendPanel();

  renderChart();

  expect(screen.getByRole("status", { name: EN.loading })).toBeInTheDocument();
});

test("should keep the slot element with a result", async () => {
  await showChart(trendSignificant);

  expect(screen.getByTestId("slot-chart")).toBeInTheDocument();
});

test("should draw one point per year", async () => {
  await showChart(trendSignificant);

  expect(screen.getAllByTestId("chart-point")).toHaveLength(
    trendSignificant.series.yearly.years.length,
  );
});

test("should draw the trend line of a tested series", async () => {
  await showChart(trendSignificant);

  expect(screen.getByTestId("chart-trend-line")).toBeInTheDocument();
});

test("should draw the band of a tested series", async () => {
  await showChart(trendSignificant);

  expect(screen.getByTestId("chart-band")).toBeInTheDocument();
});

test("should draw the points of a result with empty statistics", async () => {
  await showChart(EMPTY_STATS);

  expect(screen.getAllByTestId("chart-point")).toHaveLength(
    EMPTY_STATS.series.yearly.years.length,
  );
});

test("should draw no trend line for a result with empty statistics", async () => {
  await showChart(EMPTY_STATS);

  expect(screen.queryByTestId("chart-trend-line")).not.toBeInTheDocument();
});

test("should draw no band for a result with empty statistics", async () => {
  await showChart(EMPTY_STATS);

  expect(screen.queryByTestId("chart-band")).not.toBeInTheDocument();
});

test("should list the three forms of a file with a monthly form", async () => {
  await showChart(trendNoTrend);

  expect(
    screen.getAllByRole("radio").map((radio) => radio.textContent),
  ).toEqual([EN.forms.yearly, EN.forms.monthly, EN.forms.anomalies]);
});

test("should offer no form switch for a file with only the yearly form", async () => {
  await showChart(trendSignificant);

  expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
});

test("should name the form switch", async () => {
  await showChart(trendNoTrend);

  expect(
    screen.getByRole("radiogroup", { name: EN.forms.label }),
  ).toBeInTheDocument();
});

test("should draw the monthly values after a switch to the monthly form", async () => {
  await showChart(trendNoTrend);

  await userEvent.click(screen.getByRole("radio", { name: EN.forms.monthly }));

  expect(screen.getByTestId("chart-monthly-line")).toBeInTheDocument();
});

test("should describe the anomalies after a switch to the anomaly form", async () => {
  await showChart(trendNoTrend);

  await userEvent.click(
    screen.getByRole("radio", { name: EN.forms.anomalies }),
  );

  expect(screen.getByRole("img")).toHaveAccessibleDescription(
    EN.description.anomalies,
  );
});

test("should switch the form by keyboard", async () => {
  await showChart(trendNoTrend);
  screen.getByRole("radio", { name: EN.forms.yearly }).focus();

  await userEvent.keyboard("{ArrowRight}{Enter}");

  expect(
    screen.getByRole("radio", { name: EN.forms.monthly }),
  ).toBeChecked();
});

test("should mark a censored year in the table of values", async () => {
  await showChart(trendSignificant);

  expect(
    screen.getByRole("row", { name: new RegExp(CENSORED_YEAR) }),
  ).toHaveTextContent(EN.table.censored);
});

test("should name the censored mark in the legend", async () => {
  await showChart(trendSignificant);

  expect(screen.getByText(EN.legend.censored)).toBeInTheDocument();
});

test("should give the chart a title from the catalog", async () => {
  await showChart(trendSignificant);

  expect(
    await screen.findByRole("figure", { name: "Snowfall: First date" }),
  ).toBeInTheDocument();
});

test("should give the chart its title in Korean", async () => {
  await showChart(trendSignificant, "ko");

  expect(
    await screen.findByRole("figure", { name: "강설량: 첫 날짜" }),
  ).toBeInTheDocument();
});

test("should describe the yearly form of a tested series", async () => {
  await showChart(trendSignificant);

  expect(screen.getByRole("img")).toHaveAccessibleDescription(
    EN.description.yearly,
  );
});

test("should give a screen-reader table with one row per year", async () => {
  await showChart(trendSignificant);

  expect(screen.getAllByRole("row")).toHaveLength(
    trendSignificant.series.yearly.years.length + 1,
  );
});

test("should name the screen-reader table", async () => {
  await showChart(trendSignificant);

  expect(
    screen.getByRole("table", { name: EN.table.caption }),
  ).toBeInTheDocument();
});

test("should say that no value exists for a result with no data", async () => {
  serveTrend(trendNoData);
  openTrendPanel();

  renderChart();

  expect(await screen.findByText(EN.no_values)).toBeInTheDocument();
});

test("should show the empty state of a failed request", async () => {
  stubFetch(() => problemResponse(400, "invalid_spec"));
  openTrendPanel();

  renderChart();

  expect(
    await screen.findByText(messages.en.errors.messages.server),
  ).toBeInTheDocument();
});

test("should ask again on a retry after a failed request", async () => {
  const calls = stubFetch(() => problemResponse(400, "invalid_spec"));
  openTrendPanel();
  renderChart();
  const retry = await screen.findByRole("button", {
    name: messages.en.errors.retry,
  });
  const sentBefore = calls.length;

  await userEvent.click(retry);

  await waitFor(() => expect(calls.length).toBeGreaterThan(sentBefore));
});
