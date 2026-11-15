import { screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { messages } from "@/i18n/messages";
import { resetStore } from "@/state/store";
import { trendSignificant } from "@/test/fixtures";

import { openJudgeLink, walkToVerdict } from "./app-test-kit";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
// flags.ts reads the env at import, so the tests turn the live-board flag through this switch.
const flags = vi.hoisted(() => ({ isLiveBoardOn: false }));

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
vi.mock("@/config/flags", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/config/flags")>()),
  get IS_LIVE_BOARD_ON() {
    return flags.isLiveBoardOn;
  },
}));

const EN = messages.en;

beforeEach(() => {
  flags.isLiveBoardOn = false;
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should show the bundled board of a demo case with the live board off", async () => {
  await openJudgeLink("hot-days-phoenix", "en", trendSignificant);

  expect(
    await screen.findByRole("list", { name: EN.board.groups.driver }),
  ).toBeInTheDocument();
});

test("should show the unavailable state for a live case with the live board off", async () => {
  await walkToVerdict();

  expect(await screen.findByText(EN.board.live_off)).toBeInTheDocument();
});
