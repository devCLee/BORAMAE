/**
 * The walks of the end-to-end tests: the whole AppShell with the real store, the
 * real fetch layer and the real components. Only fetch is stubbed (fixture-network.ts),
 * and maplibre-gl is the Vitest mock. These checks run at the fetch layer, which is
 * narrower than the automated browser test that the TRD names (DEC-010);
 * W7-BROWSER-QA adds the real-browser walk.
 *
 * A test file that uses the kit mocks next/navigation and @/i18n/navigation, because
 * the gate and the locale routes need the router of Next.js (TESTING.md).
 */
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";

import { AppShell } from "@/components/shell/AppShell";
import { LANGUAGE_NAMES } from "@/components/shell/language-choice";
import { LanguageGate } from "@/components/shell/LanguageGate";
import { Providers } from "@/components/shell/Providers";
import type {
  CatalogInputs,
  Lang,
  ParseProposal,
  RequestSpec,
  ScanResult,
  TrendResult,
} from "@/contracts/types";
import { decodeRequest } from "@/features/rail/rail-test-utils";
import { outcomeOf } from "@/features/verdict/outcome";
import { messages } from "@/i18n/messages";
import type { StubCall } from "@/lib/fetch-layer.stub";
import type { PanelKind, Point } from "@/state/types";
import {
  catalog,
  parseInput1En,
  parseInput1Ko,
  scanNote,
  trendSignificant,
} from "@/test/fixtures";
import { Map as MockMap } from "@/test/mocks/maplibre-gl";
import catalogInputsJson from "@content/catalog-inputs.json";

import { serveBundle, serveService } from "./fixture-network";

export interface Walk {
  locale?: Lang;
  proposal?: ParseProposal;
  trend?: TrendResult;
  scan?: ScanResult;
  /** False leaves the place unpinned, so a request sends the map view (FR-09). */
  isPinned?: boolean;
}

/** The view of golden request vector 6 (content/golden/request-spec.json): South Korea. */
export const MAP_VIEW_AREA = { west: 124.5, south: 33, east: 131.875, north: 38.75 };
const MAP_VIEW_CENTER = { lng: 128.1875, lat: 35.875 };
const MAP_VIEW_ZOOM = 6;

const DEFAULT_LOCALE: Lang = "en";
/** The actions after a walk run in English, the language of the trace tests. */
const EN = messages.en;
const PARSE_ANSWERS: Record<Lang, ParseProposal> = {
  en: parseInput1En,
  ko: parseInput1Ko,
};
const ANALYSIS_PATH = /\/api\/v1\/(trend|caseboard|scan)\?/;
const INPUT_1 = findInput1();

/** The guided walk through the four steps, up to the read-back with Confirm not pressed. */
export async function walkToConfirm({
  locale = DEFAULT_LOCALE,
  proposal = PARSE_ANSWERS[locale],
  trend = trendSignificant,
  scan = scanNote,
  isPinned = true,
}: Walk = {}): Promise<StubCall[]> {
  const text = messages[locale];
  const calls = serveService(proposal, trend, scan);
  await openApp(locale);
  await userEvent.click(
    screen.getByRole("button", { name: text.landing.doors.guided.label }),
  );
  await userEvent.type(
    screen.getByRole("textbox", { name: text.rail.question.label }),
    `${INPUT_1.question[locale]}{Enter}`,
  );
  await userEvent.click(
    await screen.findByRole("button", { name: confirmNameOf(proposal, locale) }),
  );
  if (isPinned) {
    await userEvent.type(
      screen.getByRole("combobox", { name: text.places.search.label }),
      `${INPUT_1.place[locale]}{Enter}`,
    );
  }
  await userEvent.click(screen.getByRole("button", { name: text.rail.next }));
  return calls;
}

/** The walk on through Confirm and the chart tap, which it answers with Skip (FR-10). */
export async function walkToVerdict(walk: Walk = {}): Promise<StubCall[]> {
  const calls = await walkToConfirm(walk);
  const text = messages[walk.locale ?? DEFAULT_LOCALE];
  await userEvent.click(
    screen.getByRole("button", { name: text.rail.read_back.confirm }),
  );
  await userEvent.click(
    await screen.findByRole("button", { name: text.chart.tap.skip }),
  );
  return calls;
}

/** The walk until the case board of a significant trend has loaded. */
export async function walkToBoard(walk: Walk = {}): Promise<StubCall[]> {
  const calls = await walkToVerdict(walk);
  const text = messages[walk.locale ?? DEFAULT_LOCALE];
  await screen.findByRole("list", { name: text.board.groups.driver });
  return calls;
}

/** The walk until the fallback of a tested verdict that is not significant shows. */
export async function walkToFallback(walk: Walk = {}): Promise<StubCall[]> {
  const calls = await walkToVerdict(walk);
  const text = messages[walk.locale ?? DEFAULT_LOCALE];
  await screen.findByRole("heading", { name: text.fallback.title });
  return calls;
}

/**
 * Opens the judge link of a demo case with the bundle as the only network, and
 * waits for the verdict of the bundled trend.
 */
export async function openJudgeLink(
  caseId: string,
  locale: Lang,
  trend: TrendResult,
): Promise<StubCall[]> {
  window.history.replaceState(null, "", `/${locale}/?demo=${caseId}&at=result`);
  const calls = serveBundle(trend);
  renderApp(locale);
  await screen.findByText(messages[locale].verdict.sentences[outcomeOf(trend)]);
  return calls;
}

/** Clicks the map at the point, which moves the pin in the guided steps. Returns the requests after it. */
export function clickMap(calls: StubCall[], point: Point): Promise<StubCall[]> {
  return sentAfter(calls, async () => {
    const [map] = MockMap.instances;
    act(() => {
      map.fire("click", { lngLat: { lat: point.lat, lng: point.lon } });
    });
    await screen.findByRole("button", { name: EN.rail.read_back.confirm });
  });
}

/** Moves the radius one step up with the keyboard. Returns the requests after it. */
export function widenRadius(calls: StubCall[]): Promise<StubCall[]> {
  return sentAfter(calls, async () => {
    await pressKey(
      screen.getByRole("slider", { name: EN.places.radius.label }),
      "{ArrowRight}",
    );
    await screen.findByRole("button", { name: EN.rail.read_back.confirm });
  });
}

/** Moves the start of the time window one year later with the keyboard. */
export function moveWindowStart(): Promise<void> {
  return pressKey(
    screen.getByRole("slider", { name: EN.window.start_thumb }),
    "{ArrowRight}",
  );
}

/** Presses Confirm on the read-back. Returns the requests after it. */
export function confirmAgain(calls: StubCall[]): Promise<StubCall[]> {
  return sentAfter(calls, () =>
    userEvent.click(screen.getByRole("button", { name: EN.rail.read_back.confirm })),
  );
}

/** The kind of each analysis request, in the order the requests left. */
export function analysisKinds(calls: StubCall[]): string[] {
  return calls.flatMap(({ url }) => url.match(ANALYSIS_PATH)?.[1] ?? []);
}

/** The areas of the analysis requests of one kind. */
export function areasOf(calls: StubCall[], kind: PanelKind): RequestSpec["area"][] {
  return requestsOf(calls, kind).map(({ area }) => area);
}

/** The time windows of the analysis requests of one kind. */
export function windowsOf(calls: StubCall[], kind: PanelKind): RequestSpec["window"][] {
  return requestsOf(calls, kind).map(({ window }) => window);
}

export function urlsOf(calls: StubCall[]): string[] {
  return calls.map(({ url }) => url);
}

/** The request URLs that hold the text. */
export function urlsWith(calls: StubCall[], text: string): string[] {
  return urlsOf(calls).filter((url) => url.includes(text));
}

/** The words that the page shows, in its text or in an accessible name. */
export function shownWords(words: string[]): string[] {
  const labels = [...document.querySelectorAll("[aria-label]")].map((element) =>
    element.getAttribute("aria-label"),
  );
  const shown = [document.body.textContent, ...labels].join("\n");
  return words.filter((word) => shown.includes(word));
}

/** Mounts the locale route of the app. The mock map loads facing South Korea. */
function renderApp(locale: Lang): void {
  render(
    <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
      <Providers>
        <AppShell />
      </Providers>
    </NextIntlClientProvider>,
  );
  const [map] = MockMap.instances;
  map.getBounds.mockReturnValue({
    getWest: () => MAP_VIEW_AREA.west,
    getSouth: () => MAP_VIEW_AREA.south,
    getEast: () => MAP_VIEW_AREA.east,
    getNorth: () => MAP_VIEW_AREA.north,
  });
  map.getCenter.mockReturnValue(MAP_VIEW_CENTER);
  map.getZoom.mockReturnValue(MAP_VIEW_ZOOM);
  act(() => {
    map.fire("load");
  });
}

/** Chooses the language on the gate of the root route, then mounts the route of that language. */
async function openApp(locale: Lang): Promise<void> {
  render(<LanguageGate />);
  await userEvent.click(screen.getByRole("button", { name: LANGUAGE_NAMES[locale] }));
  // jsdom loads no other document, so the walk mounts the route that the gate opens.
  cleanup();
  renderApp(locale);
}

function requestsOf(calls: StubCall[], kind: PanelKind): RequestSpec[] {
  return calls
    .filter(({ url }) => url.includes(`/api/v1/${kind}?`))
    .map(({ url }) => decodeRequest(url));
}

/** The name of the Confirm control on the card of the first proposed variable. */
function confirmNameOf(proposal: ParseProposal, locale: Lang): string {
  const [first] = proposal.variables;
  const variable = catalog.variables.find(({ id }) => id === first.var);
  return messages[locale].rail.variables.confirm_name.replace(
    "{name}",
    variable?.name[locale] ?? first.var,
  );
}

/** Focuses the element, as a keyboard user does, then presses the key. */
async function pressKey(element: HTMLElement, key: string): Promise<void> {
  act(() => element.focus());
  await userEvent.keyboard(key);
}

async function sentAfter(
  calls: StubCall[],
  action: () => Promise<unknown>,
): Promise<StubCall[]> {
  const before = calls.length;
  await action();
  return calls.slice(before);
}

/** Catalog input 1 (content/catalog-inputs.json): the first-snow question about Seoul. */
function findInput1() {
  const input = (catalogInputsJson as unknown as CatalogInputs).inputs.find(
    ({ id }) => id === 1,
  );
  if (input?.place == null) {
    throw new Error("content/catalog-inputs.json holds no input 1 with a place.");
  }
  return { question: input.text, place: input.place.name };
}
