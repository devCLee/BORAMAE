/** Shared setup of the chart tests. fetch is the only stand-in, as in every frontend test. */
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { HEADER_RESULT_KEY, type TrendResult } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import { jsonResponse, stubFetch } from "@/lib/fetch-layer.stub";
import { actions } from "@/state/store";
import { catalog } from "@/test/fixtures";

import { TrendChart } from "./TrendChart";

export const EN = messages.en.chart;
const SEOUL = { lat: 37.5665, lon: 126.978 };
const RESULT_KEY = "b5bae5463e95eff888bca78a896bf62a";

/** Answers the catalog and the trend request, as the service does. */
export function serveTrend(result: TrendResult) {
  return stubFetch(({ url }) =>
    url.endsWith("/meta/catalog.json")
      ? jsonResponse(catalog)
      : jsonResponse(result, { headers: { [HEADER_RESULT_KEY]: RESULT_KEY } }),
  );
}

/** The state after Confirm: the trend panel is open on a confirmed spec. */
export function openTrendPanel(): void {
  actions.editDraft({ var: "PRECSNO", metric: { id: "first_date" } }, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
  actions.openPanel("trend");
}

export function renderChart(locale: "en" | "ko" = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <Providers>
        <TrendChart />
      </Providers>
    </NextIntlClientProvider>,
  );
}

/** Renders the chart of the result and waits for it. Returns the requests that fetch saw. */
export async function showChart(
  result: TrendResult,
  locale: "en" | "ko" = "en",
) {
  const calls = serveTrend(result);
  openTrendPanel();
  renderChart(locale);
  await screen.findByRole("figure");
  return calls;
}

/** A device set to reduced motion, until vi.unstubAllGlobals(). */
export function reduceMotion(): void {
  const matchNothing = window.matchMedia;
  vi.stubGlobal(
    "matchMedia",
    (query: string): MediaQueryList => ({
      ...matchNothing(query),
      matches: query === "(prefers-reduced-motion: reduce)",
    }),
  );
}
