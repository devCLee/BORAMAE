/**
 * The offline trace of both demos (FR-06, TR-D-011, TDD Flow E). The app starts at
 * the language gate with the live source, and each script plays from its first step
 * on the files that export-demo wrote. The fetch stub serves web/public/demo and
 * web/public/basemap from disk and refuses every other path with a 404, as the
 * static file server of the demo laptop does with no service behind it.
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { AppShell } from "@/components/shell/AppShell";
import { LANGUAGE_NAMES } from "@/components/shell/language-choice";
import { LanguageGate } from "@/components/shell/LanguageGate";
import { Providers } from "@/components/shell/Providers";
import type {
  CaseBoard,
  Catalog,
  DemoCase,
  DemoManifest,
  DemoScript,
  DemoStep,
  Lang,
  ManifestCase,
  ScanResult,
  TrendResult,
} from "@/contracts/types";
import { DEMO_CASES, findScript, verdictIndexOf } from "@/features/demo/demo-content";
import { outcomeOf } from "@/features/verdict/outcome";
import { messages } from "@/i18n/messages";
import { problemResponse, type StubCall, stubFetch } from "@/lib/fetch-layer.stub";
import { resetStore } from "@/state/store";

const PUBLIC_DIR = path.join(import.meta.dirname, "../../../public");
const ORIGIN = "http://localhost";
const BUNDLE_PREFIXES = ["/demo/", "/basemap/"];
/** The shell reads the live catalog once before the demo door; W5-E2E-WEB owns that check. */
const LIVE_CATALOG_READ = "GET /meta/catalog.json";
const JUDGE_LANG: Lang = "ko";
// ponytail: a short real wait lets the bundled answers of a step land before the next
// step, as the 3 s of a played step do. Every check still waits with findBy or waitFor.
const SETTLE_MS = 25;

const gateRouter = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const localeRouter = vi.hoisted(() => ({ replace: vi.fn() }));
const openSocket = vi.fn();

// The player navigates with the next-intl router, which needs the app router of Next.js.
vi.mock("@/i18n/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/i18n/navigation")>()),
  useRouter: () => localeRouter,
  usePathname: () => "/",
}));
// The language gate of the root route calls useRouter of next/navigation (TESTING.md).
vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  useRouter: () => gateRouter,
}));

interface TracedCase {
  id: string;
  demoCase: DemoCase;
  verdictIndex: number;
  lastIndex: number;
  /** The verdict sentence of the exported trend file in each language. */
  verdict: Record<Lang, string>;
  /** What the board or the fallback of the exported file shows in the script's language. */
  lastContent: string[];
}

const MANIFEST = readBundled<DemoManifest>("manifest.json");
const CATALOG = readBundled<Catalog>(MANIFEST.catalog);
const TRACED = DEMO_CASES.map(toTracedCase);

function readBundled<T>(file: string): T {
  return JSON.parse(readFileSync(path.join(PUBLIC_DIR, "demo", file), "utf8")) as T;
}

function toTracedCase(demoCase: DemoCase): TracedCase {
  const script = findScript(demoCase.id) as DemoScript;
  const entry = MANIFEST.cases.find(({ case_id }) => case_id === demoCase.id) as ManifestCase;
  const trend = readBundled<TrendResult>(entry.kinds.trend.file);
  const lastIndex = script.steps.length - 1;
  return {
    id: demoCase.id,
    demoCase,
    verdictIndex: verdictIndexOf(script),
    lastIndex,
    verdict: { en: sentenceOf(trend, "en"), ko: sentenceOf(trend, "ko") },
    lastContent: lastContentOf(script.steps[lastIndex - 1].action, entry, demoCase.lang),
  };
}

function sentenceOf(trend: TrendResult, lang: Lang): string {
  const sentences: Record<string, string> = messages[lang].verdict.sentences;
  return sentences[outcomeOf(trend)];
}

/** The board shows the mechanism of each node, and the fallback a test button for each hit. */
function lastContentOf(action: DemoStep["action"], entry: ManifestCase, lang: Lang): string[] {
  if (action === "open_board") {
    const { nodes } = readBundled<CaseBoard>(entry.kinds.caseboard.file);
    return nodes.map(({ row }) => row.mechanism[lang]);
  }
  if (action === "open_fallback") {
    const { hits } = readBundled<ScanResult>(entry.kinds.scan.file);
    return hits.map((hit) => chooseLabel(hit.var, lang));
  }
  throw new Error(`${entry.case_id}: the step before the closing card is ${action}`);
}

function chooseLabel(variableId: string, lang: Lang): string {
  const variable = CATALOG.variables.find(({ id }) => id === variableId);
  return messages[lang].fallback.hits.choose.replace("{variable}", variable?.name[lang] ?? variableId);
}

function respondFromDisk(call: StubCall): Response {
  const pathname = pathOf(call);
  const file = path.join(PUBLIC_DIR, pathname);
  return isBundlePath(pathname) && existsSync(file)
    ? new Response(readFileSync(file, "utf8"))
    : problemResponse(404, "not_found");
}

function pathOf({ url }: StubCall): string {
  return new URL(url, ORIGIN).pathname;
}

function isBundlePath(pathname: string): boolean {
  return BUNDLE_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

/** Each request outside the bundle, without one live catalog read. */
function requestsOutsideBundle(calls: StubCall[]): string[] {
  const outside = calls
    .filter((call) => !isBundlePath(pathOf(call)))
    .map((call) => `${call.method} ${pathOf(call)}`);
  const catalogRead = outside.indexOf(LIVE_CATALOG_READ);
  return outside.filter((_request, index) => index !== catalogRead);
}

/** Each bundle path that the trace asked for and that the export did not write. */
function bundlePathsNotOnDisk(calls: StubCall[]): string[] {
  return calls
    .map(pathOf)
    .filter((pathname) => isBundlePath(pathname) && !existsSync(path.join(PUBLIC_DIR, pathname)));
}

function textsNotShown(texts: string[]): string[] {
  return texts.filter((text) => screen.queryAllByText(text).length === 0);
}

/** A locale route of the static export: [locale]/layout.tsx around [locale]/page.tsx. */
function LocalePage({ locale }: { locale: Lang }) {
  return (
    <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
      <Providers>
        <AppShell />
      </Providers>
    </NextIntlClientProvider>
  );
}

/** The root route: the gate pushes the route of the language, and the host serves its page. */
function openAppIn(lang: Lang): void {
  const gate = render(<LanguageGate />);
  fireEvent.click(screen.getByRole("button", { name: LANGUAGE_NAMES[lang] }));
  const route = String(gateRouter.push.mock.lastCall?.[0]);
  gate.unmount();
  window.history.replaceState(null, "", route);
  render(<LocalePage locale={route.split("/")[1] as Lang} />);
}

/** Plays the script of the case from its first step, the language choice, to the step at index. */
async function playTo({ demoCase }: TracedCase, index: number): Promise<StubCall[]> {
  const { lang } = demoCase;
  const { demo, landing } = messages[lang];
  const calls = stubFetch(respondFromDisk);
  openAppIn(lang);
  fireEvent.click(screen.getByRole("button", { name: landing.doors.demo.label }));
  const list = await screen.findByRole("region", { name: demo.cases.heading });
  fireEvent.click(
    await within(list).findByRole("button", {
      name: (name) => name.startsWith(demoCase.question[lang]),
    }),
  );
  const controls = screen.getByRole("group", { name: demo.controls.label });
  // Paused, the player moves only with the step control, one step at a time.
  fireEvent.click(within(controls).getByRole("button", { name: demo.controls.pause }));
  const overlay = screen.getByRole("dialog", { name: demo.overlay.language });
  fireEvent.click(within(overlay).getByRole("button", { name: LANGUAGE_NAMES[lang] }));
  for (let step = 2; step <= index; step += 1) {
    await settle();
    fireEvent.click(within(controls).getByRole("button", { name: demo.controls.next }));
  }
  await settle();
  return calls;
}

async function settle(): Promise<void> {
  await act(() => new Promise<void>((resolve) => setTimeout(resolve, SETTLE_MS)));
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  gateRouter.push.mockClear();
  openSocket.mockClear();
  vi.stubGlobal("WebSocket", openSocket);
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test.each(TRACED)(
  "should request nothing outside /demo/ and /basemap/ but one live catalog read in $id",
  async (traced) => {
    const calls = await playTo(traced, traced.lastIndex);

    expect(requestsOutsideBundle(calls)).toEqual([]);
  },
);

test.each(TRACED)("should find each requested bundle file on disk in $id", async (traced) => {
  const calls = await playTo(traced, traced.lastIndex);

  expect(bundlePathsNotOnDisk(calls)).toEqual([]);
});

test.each(TRACED)("should open no WebSocket in $id", async (traced) => {
  await playTo(traced, traced.lastIndex);

  expect(openSocket).not.toHaveBeenCalled();
});

test.each(TRACED)(
  "should show the verdict of the exported trend file at the verdict step of $id",
  async (traced) => {
    await playTo(traced, traced.verdictIndex);

    expect(await screen.findByText(traced.verdict[traced.demoCase.lang])).toBeInTheDocument();
  },
);

test.each(TRACED)(
  "should show the board or the fallback of the exported file at the last content step of $id",
  async (traced) => {
    await playTo(traced, traced.lastIndex - 1);

    await waitFor(() => expect(textsNotShown(traced.lastContent)).toEqual([]));
  },
);

test.each(TRACED)("should render the same verdict at the judge link of $id", async (traced) => {
  stubFetch(respondFromDisk);
  window.history.replaceState(null, "", `/${JUDGE_LANG}/?demo=${traced.id}&at=result`);

  render(<LocalePage locale={JUDGE_LANG} />);

  expect(await screen.findByText(traced.verdict[JUDGE_LANG])).toBeInTheDocument();
});

test("should move the focus to the board with its suggestion at the judge link of hot-days-phoenix", async () => {
  stubFetch(respondFromDisk);
  window.history.replaceState(null, "", "/en/?demo=hot-days-phoenix&at=result");
  render(<LocalePage locale="en" />);
  const board = await screen.findByRole("region", { name: messages.en.board.title });

  fireEvent.click(screen.getByRole("button", { name: messages.en.suggestions.actions.open_board }));

  expect(board).toHaveFocus();
});
