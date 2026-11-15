/**
 * Helpers of the case board tests: the confirmed first-snow request, a stub
 * network for the live service and for the demo bundle, and the render.
 */
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { RETRY_DELAYS_MS } from "@/config/timeouts";
import { type DraftSpec, HEADER_RESULT_KEY } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import {
  jsonResponse,
  problemResponse,
  type Respond,
  serve,
  type StubCall,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { actions } from "@/state/store";
import {
  caseBoard,
  catalog,
  manifest,
  trendSignificant,
} from "@/test/fixtures";

import { CaseBoard } from "./CaseBoard";

const SNOW: DraftSpec = {
  var: "PRECSNO",
  metric: { id: "first_date", op: ">=", season_start: "08-01", threshold: "0.1" },
};
const SEOUL = { lat: 37.5665, lon: 126.978 };
const CASE = manifest.cases[0];
const ALL_RETRIES_MS = RETRY_DELAYS_MS.reduce((sum, ms) => sum + ms, 0);
const SETTLE_MS = 1_000;

/** The trend of every board node: any stored trend serves, the test reads its numbers. */
export const NODE_TREND = trendSignificant;

/** The state after Confirm on the first-snow question, with the trend panel open. */
export function confirmSeoulSnow(): void {
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
  actions.openPanel("trend");
}

/** The same request in a demo: a switch of the source clears the confirmation. */
export function confirmBundledSeoulSnow(): void {
  actions.setFetchSource("fixture");
  confirmSeoulSnow();
}

export function answer(body: unknown, key: string): Respond {
  return () => jsonResponse(body, { headers: { [HEADER_RESULT_KEY]: key } });
}

export const boardAnswer = answer(caseBoard, CASE.kinds.caseboard.key);
export const failure: Respond = () => problemResponse(500, "internal");
export const unavailable: Respond = () => problemResponse(503, "power_unavailable");

/** The live service: the catalog, the focus trend, the board and the stored node trends. */
export function serveLive(board: Respond = boardAnswer): StubCall[] {
  return stubFetch((call) => {
    if (call.url.endsWith("/meta/catalog.json")) {
      return jsonResponse(catalog);
    }
    if (call.url.includes("/api/v1/trend?")) {
      return answer(trendSignificant, CASE.kinds.trend.key)(call);
    }
    if (call.url.includes("/api/v1/caseboard?")) {
      return board(call);
    }
    if (call.url.includes("/r/trend/")) {
      return jsonResponse(NODE_TREND);
    }
    return problemResponse(404, "not_found");
  });
}

/** The demo bundle of the first case, as the fixture source reads it. */
export function serveBundle(): StubCall[] {
  return stubFetch(
    serve({
      "/demo/manifest.json": manifest,
      "/demo/catalog.json": catalog,
      [`/demo/${CASE.kinds.trend.file}`]: trendSignificant,
      [`/demo/${CASE.kinds.caseboard.file}`]: caseBoard,
    }),
  );
}

export function renderInApp(
  ui: ReactNode = <CaseBoard />,
  locale: "en" | "ko" = "en",
) {
  return render(
    <Providers>
      <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
        {ui}
      </NextIntlClientProvider>
    </Providers>,
  );
}

/** The arrow whose title starts with the variable name. */
export function findArrow(name: string): Promise<HTMLElement> {
  return screen.findByRole("listitem", { name: new RegExp(`^${name}`) });
}

/** The value of a field of an arrow, such as "Link test" or "Scale". */
export async function findField(arrowName: string, field: string): Promise<HTMLElement> {
  const arrow = await findArrow(arrowName);
  const term = within(arrow)
    .getAllByRole("term")
    .find((candidate) => candidate.textContent === field);
  const value = term?.nextElementSibling;
  if (!(value instanceof HTMLElement)) {
    throw new Error(`The ${arrowName} arrow has no ${field} field.`);
  }
  return value;
}

/** Waits until the link numbers show, which need the focus trend as well as the board. */
export async function findLoadedBoard(): Promise<void> {
  await screen.findByRole("button", { name: "Source of 0.52" });
}

/** Opens the inputs of an arrow with a click. */
export async function openArrow(name: string): Promise<HTMLElement> {
  const arrow = await findArrow(name);
  await userEvent.click(within(arrow).getByRole("button", { name: `Inputs of ${name}` }));
  return arrow;
}

/**
 * Lets the fetch layer spend every retry under fake timers, then gives the clock back.
 * The margin lets the last answer reach the view before the fake timers stop.
 */
export async function passAllRetries(): Promise<void> {
  await act(() => vi.advanceTimersByTimeAsync(ALL_RETRIES_MS + SETTLE_MS));
  vi.useRealTimers();
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
