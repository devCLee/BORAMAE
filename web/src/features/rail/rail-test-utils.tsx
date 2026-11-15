/**
 * Helpers of the rail tests: the real store, the real query hooks and a fetch
 * stub that serves the sample fixtures.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";

import { Providers } from "@/components/shell/Providers";
import { API_BASE } from "@/config/flags";
import type { Lang, ParseProposal, RequestSpec } from "@/contracts/types";
import { messages } from "@/i18n/messages";
import { serve, stubFetch } from "@/lib/fetch-layer.stub";
import { actions } from "@/state/store";
import { catalog, parseInput1En } from "@/test/fixtures";

import { Rail } from "./Rail";

export const CATALOG_URL = `${API_BASE}/meta/catalog.json`;
export const PARSE_URL = `${API_BASE}/api/v1/parse`;
export const TREND_PATH = "/api/v1/trend?s=";
export const SEOUL = { lat: 37.5665, lon: 126.978 };
export const QUESTION_EN = "Is Seoul's first snow coming later?";

/** Renders the rail in the locale, with the store in the same language. */
export function renderRail(locale: Lang = "en") {
  actions.setLang(locale);
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <Providers>
        <Rail />
      </Providers>
    </NextIntlClientProvider>,
  );
}

/** Serves the sample catalog and answers every parse with the proposal. */
export function serveApi(proposal: ParseProposal = parseInput1En) {
  return stubFetch(serve({ [CATALOG_URL]: catalog, [PARSE_URL]: proposal }));
}

export async function ask(question = QUESTION_EN, locale: Lang = "en") {
  const field = screen.getByRole("textbox", {
    name: messages[locale].rail.question.label,
  });
  await userEvent.clear(field);
  await userEvent.type(field, `${question}{Enter}`);
}

/** Guided mode on step 2, with the cards of the proposal on screen. */
export async function openVariables(
  proposal: ParseProposal = parseInput1En,
  locale: Lang = "en",
) {
  const calls = serveApi(proposal);
  actions.chooseDoor("guided");
  renderRail(locale);
  await ask(QUESTION_EN, locale);
  await screen.findByRole("heading", {
    name: messages[locale].rail.steps.names["2"],
  });
  return calls;
}

/** The request spec of an analysis URL: the base64url JSON of its s parameter. */
export function decodeRequest(url: string): RequestSpec {
  const s = new URL(url, "http://localhost").searchParams.get("s") ?? "";
  return JSON.parse(atob(s.replaceAll("-", "+").replaceAll("_", "/")));
}
