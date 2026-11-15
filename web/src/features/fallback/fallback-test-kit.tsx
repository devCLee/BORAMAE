/**
 * The shared setup of the fallback tests: a fetch stub that serves the catalog, the
 * trend, the scan in turn and every stored hit trend, and the panel in a stand-in
 * for the case panel root.
 */
import { render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import { Providers } from "@/components/shell/Providers";
import {
  type DraftSpec,
  HEADER_RESULT_KEY,
  type ScanResult,
  type TrendResult,
} from "@/contracts/types";
import { messages } from "@/i18n/messages";
import {
  hang,
  inTurn,
  jsonResponse,
  problemResponse,
  type Respond,
  type StubCall,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { actions } from "@/state/store";
import { catalog, trendNoTrend, trendSignificant } from "@/test/fixtures";

import { FallbackPanel } from "./FallbackPanel";

export const FOCUS: DraftSpec = { var: "PRECTOTCORR", metric: { id: "rx1day" } };
export const SCAN_PATH = "/api/v1/scan?";
export const HITS = "Other variables here";
export const NEARBY = "The same variable nearby";
export const YEARS = "How long until this rate could be detected";
export const CHECKED = "What the scan checked";
export const FOUND_BY_SCAN = "Found by a scan";
export const CASE_ROOT = "case-root";

const SEOUL = { lat: 37.5665, lon: 126.978 };
const RESULT_KEY = "b5bae5463e95eff888bca78a896bf62a";
const CATALOG_PATH = "/meta/catalog.json";
const TREND_PATH = "/api/v1/trend?";
const STORED_TREND_PATH = "/r/trend/";

export function answer(body: TrendResult | ScanResult): Respond {
  return () => jsonResponse(body, { headers: { [HEADER_RESULT_KEY]: RESULT_KEY } });
}

export const failure: Respond = () => problemResponse(500, "internal");

/** With no scan turn, the scan never answers. */
export function serve(trend: Respond, ...scanTurns: Respond[]): StubCall[] {
  const scan = inTurn(...(scanTurns.length > 0 ? scanTurns : [hang]));
  return stubFetch((call) => {
    if (call.url.endsWith(CATALOG_PATH)) {
      return jsonResponse(catalog);
    }
    if (call.url.includes(TREND_PATH)) {
      return trend(call);
    }
    if (call.url.includes(SCAN_PATH)) {
      return scan(call);
    }
    if (call.url.includes(STORED_TREND_PATH)) {
      return jsonResponse(trendSignificant);
    }
    return problemResponse(404, "not_found");
  });
}

/** The state after Confirm with the trend panel open, as the case panel has it. */
export function openFocusTrend(): void {
  actions.editDraft(FOCUS, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
  actions.openPanel("trend");
}

/** The wrapper stands in for the case panel root, which takes the focus of a control that leaves. */
export function renderPanel(locale: "en" | "ko" = "en") {
  return render(
    <Providers>
      <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
        <div data-testid={CASE_ROOT} tabIndex={-1}>
          <FallbackPanel />
        </div>
      </NextIntlClientProvider>
    </Providers>,
  );
}

export async function showScan(
  scan: ScanResult,
  trend: TrendResult = trendNoTrend,
): Promise<void> {
  serve(answer(trend), answer(scan));
  openFocusTrend();
  renderPanel();
  // The hits heading shows only with a scan result.
  await screen.findByRole("heading", { name: HITS });
}

export function findList(name: string): Promise<HTMLElement> {
  return screen.findByRole("list", { name });
}

export async function nearbyItem(index: number): Promise<HTMLElement> {
  const items = within(await findList(NEARBY)).getAllByRole("listitem");
  return items[index];
}
