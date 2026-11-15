import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { LanguageGate } from "@/components/shell/LanguageGate";
import { messages } from "@/i18n/messages";
import { resetStore } from "@/state/store";
import { trendNotYet } from "@/test/fixtures";

import {
  shownWords,
  walkToBoard,
  walkToConfirm,
  walkToFallback,
  walkToVerdict,
} from "./app-test-kit";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));

// The gate on the root route uses the Next.js router (TESTING.md).
vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  useRouter: () => router,
}));
// The language switch and the demo player use the next-intl router of the locale routes.
vi.mock("@/i18n/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/i18n/navigation")>()),
  useRouter: () => router,
  usePathname: () => "/",
}));

const EN = messages.en;
const ENGLISH_VERDICT_WORDS = Object.values(EN.glossary.verdicts);
const KOREAN_VERDICT_WORDS = Object.values(messages.ko.glossary.verdicts);

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  router.push.mockClear();
  router.replace.mockClear();
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should show the verdict card of a significant trend", async () => {
  await walkToVerdict();

  expect(
    await screen.findByText(EN.verdict.sentences.significant_rise),
  ).toBeInTheDocument();
});

test("should show the chart of a significant trend", async () => {
  await walkToVerdict();

  expect(await screen.findByRole("figure")).toBeInTheDocument();
});

test("should show the case board of a significant trend", async () => {
  await walkToVerdict();

  expect(
    await screen.findByRole("list", { name: EN.board.groups.driver }),
  ).toBeInTheDocument();
});

test("should show the fallback of a trend that is not yet significant", async () => {
  await walkToVerdict({ trend: trendNotYet });

  expect(
    await screen.findByRole("heading", { name: EN.fallback.title }),
  ).toBeInTheDocument();
});

test("should show no case board for a trend that is not yet significant", async () => {
  await walkToFallback({ trend: trendNotYet });

  expect(screen.queryByTestId("slot-board")).not.toBeInTheDocument();
});

test("should render no English verdict word on the Korean walk", async () => {
  await walkToBoard({ locale: "ko" });

  expect(shownWords(ENGLISH_VERDICT_WORDS)).toEqual([]);
});

test("should render no Korean verdict word on the English walk", async () => {
  await walkToBoard({ locale: "en" });

  expect(shownWords(KOREAN_VERDICT_WORDS)).toEqual([]);
});

test("should open the chosen language again after a remount", async () => {
  await walkToConfirm({ locale: "ko" });
  cleanup();

  render(<LanguageGate />);

  expect(router.replace).toHaveBeenCalledWith("/ko/");
});
