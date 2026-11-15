import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { messages } from "@/i18n/messages";
import { jsonResponse, problemResponse, stubFetch } from "@/lib/fetch-layer.stub";
import { resetStore } from "@/state/store";

import type { NewsResult } from "./news-params";
import { NewsPanel } from "./NewsPanel";

// flags.ts reads the env at import, so the tests turn the news flag on here.
vi.mock("@/config/flags", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/config/flags")>()),
  IS_NEWS_SHOWN: true,
}));

const EN = messages.en.case.news;
const ITEM = {
  title: "Seoul heat wave sets a record",
  source: "Example Daily",
  published: "2024-08-01T03:00:00Z",
  url: "https://news.example.com/heat",
  feed: "google_news_en",
} as const;

function renderNews() {
  return render(
    <Providers>
      <NextIntlClientProvider locale="en" messages={messages.en} timeZone="UTC">
        <NewsPanel variableName="Hot days" placeName="Seoul" window={[1981, "2024-12"]} />
      </NextIntlClientProvider>
    </Providers>,
  );
}

function serveNews(items: NewsResult["items"]) {
  stubFetch(() => jsonResponse({ items, feeds: [] }));
}

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should link each news title to its article", async () => {
  serveNews([ITEM]);
  renderNews();

  expect(await screen.findByRole("link", { name: new RegExp(ITEM.title) })).toHaveAttribute(
    "href",
    ITEM.url,
  );
});

test("should leave out an item whose URL is not http or https", async () => {
  serveNews([{ ...ITEM, url: "javascript:alert(1)" }]);
  renderNews();

  expect(await screen.findByText(EN.empty)).toBeInTheDocument();
});

test("should show the empty state when no item returns", async () => {
  serveNews([]);
  renderNews();

  expect(await screen.findByText(EN.empty)).toBeInTheDocument();
});

test("should show the error state when the request fails", async () => {
  stubFetch(() => problemResponse(500, "internal"));
  renderNews();

  expect(await screen.findByRole("alert")).toHaveTextContent(EN.error);
});
