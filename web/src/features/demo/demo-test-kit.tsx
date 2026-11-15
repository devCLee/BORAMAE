/**
 * Helpers of the demo player tests: the screen with the real case panel, the
 * bundle of sample files that the fetch stub serves, and the steps of the
 * first-snow script.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import { Providers } from "@/components/shell/Providers";
import type { DemoManifest, DemoScript, DemoStep, Lang } from "@/contracts/types";
import { CasePanel } from "@/features/case/CasePanel";
import { messages } from "@/i18n/messages";
import { serve, stubFetch } from "@/lib/fetch-layer.stub";
import { actions } from "@/state/store";
import {
  catalog,
  manifest,
  parseInput1En,
  parseInput1Ko,
  trendNoTrend,
} from "@/test/fixtures";

import { DemoBar } from "./DemoBar";
import { DEMO_CASES, findScript } from "./demo-content";

export const SNOW = DEMO_CASES[0];
export const SNOW_SCRIPT = findScript(SNOW.id) as DemoScript;
/** The sample manifest names the first-snow case first. */
const SNOW_ENTRY = manifest.cases[0];
/** The sample manifest with its second case renamed to the second demo case. */
export const BOTH_CASES: DemoManifest = {
  ...manifest,
  cases: [SNOW_ENTRY, { ...manifest.cases[1], case_id: DEMO_CASES[1].id }],
};

export function Screen({ locale }: { locale: Lang }) {
  return (
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <Providers>
        <DemoBar />
        <CasePanel />
      </Providers>
    </NextIntlClientProvider>
  );
}

/** The bundled files under /demo/, as a static file server answers them. */
export function bundle(demoManifest: DemoManifest = BOTH_CASES) {
  return {
    "/demo/manifest.json": demoManifest,
    "/demo/catalog.json": catalog,
    [`/demo/${SNOW_ENTRY.kinds.trend.file}`]: trendNoTrend,
    [`/demo/${SNOW_ENTRY.parse.ko}`]: parseInput1Ko,
    [`/demo/${SNOW_ENTRY.parse.en}`]: parseInput1En,
  };
}

/** The sample manifest whose first-snow trend entry holds another request. */
export function manifestWithTrendS(s: string): DemoManifest {
  const trend = { ...SNOW_ENTRY.kinds.trend, s };
  return {
    ...manifest,
    cases: [{ ...SNOW_ENTRY, kinds: { ...SNOW_ENTRY.kinds, trend } }],
  };
}

/** Opens the demo door and starts the first-snow case from the list. */
export async function startSnowDemo(
  locale: Lang = "en",
  demoManifest?: DemoManifest,
) {
  const calls = stubFetch(serve(bundle(demoManifest)));
  actions.chooseDoor("demo");
  const view = render(<Screen locale={locale} />);
  const start = await screen.findByRole("button", {
    name: (name) => name.startsWith(SNOW.question[locale]),
  });
  fireEvent.click(start);
  return { calls, view };
}

export function pressNext(times: number): void {
  Array.from({ length: times }).forEach(() =>
    fireEvent.click(screen.getByRole("button", { name: "Next step" })),
  );
}

export function indexOfAction(action: DemoStep["action"]): number {
  return SNOW_SCRIPT.steps.findIndex((step) => step.action === action);
}
