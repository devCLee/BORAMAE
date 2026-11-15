/**
 * The shared setup of the AiText tests: a fetch stub that serves the catalog and the
 * stored results of a table, and AiText next to the provenance drawer.
 */
import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import { Providers } from "@/components/shell/Providers";
import { API_BASE } from "@/config/flags";
import { ProvenanceDrawer } from "@/features/provenance/ProvenanceDrawer";
import { messages } from "@/i18n/messages";
import { serve, type StubCall, stubFetch } from "@/lib/fetch-layer.stub";
import { catalog, trendSignificant } from "@/test/fixtures";

import { AiText, type AiTextProps } from "./AiText";

export const TREND_KEY = "b5bae5463e95eff888bca78a896bf62a";
export const TREND_URL = `${API_BASE}/r/trend/${TREND_KEY}.json`;
export const CATALOG_URL = `${API_BASE}/meta/catalog.json`;
export const CHECKING = "Checking the numbers in this answer…";
export const WITHHELD =
  "This answer was withheld because its numbers do not match the computed results. The results on screen stay as they are.";
export const KO_WITHHELD =
  "답변의 숫자가 계산 결과와 맞지 않아 이 답변을 보여 드리지 않아요. 화면의 결과는 그대로예요.";
export const BADGE = "Written by AI:";
export const RATE = "Seoul's first snow comes 3.3 days later per decade.";
export const INTERVAL = "The 95% interval runs from 2 to 5 days.";
export const INVENTED = "By 2031 it will come 9.99 days later.";
export const ANSWER = `${RATE} ${INTERVAL} ${INVENTED}`;

/** Serves the catalog and each file of the table; every other URL answers 404. */
export function serveFiles(
  files: Record<string, unknown> = { [TREND_URL]: trendSignificant },
): StubCall[] {
  return stubFetch(serve({ [CATALOG_URL]: catalog, ...files }));
}

export function renderAiText(
  props: Partial<AiTextProps> = {},
  locale: "en" | "ko" = "en",
) {
  return render(
    <Providers>
      <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
        <AiText text={ANSWER} resultKeys={[TREND_KEY]} citations={[]} {...props} />
        <ProvenanceDrawer />
      </NextIntlClientProvider>
    </Providers>,
  );
}
