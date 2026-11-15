import { afterEach, beforeEach, expect, test, vi } from "vitest";

// flags.ts reads process.env once at import, so each test imports a fresh copy.
beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

test("should turn the live board and the chat off when both variables are 'off'", async () => {
  vi.stubEnv("NEXT_PUBLIC_LIVE_BOARD", "off");
  vi.stubEnv("NEXT_PUBLIC_SHOW_CHAT", "off");

  const { IS_LIVE_BOARD_ON, IS_CHAT_SHOWN } = await import("@/config/flags");

  expect({ IS_LIVE_BOARD_ON, IS_CHAT_SHOWN }).toEqual({
    IS_LIVE_BOARD_ON: false,
    IS_CHAT_SHOWN: false,
  });
});

test("should hide the news panel when NEXT_PUBLIC_SHOW_NEWS is unset", async () => {
  vi.stubEnv("NEXT_PUBLIC_SHOW_NEWS", undefined);

  const { IS_NEWS_SHOWN } = await import("@/config/flags");

  expect(IS_NEWS_SHOWN).toBe(false);
});

test("should leave the live board and the chat on when both variables are unset", async () => {
  vi.stubEnv("NEXT_PUBLIC_LIVE_BOARD", undefined);
  vi.stubEnv("NEXT_PUBLIC_SHOW_CHAT", undefined);

  const { IS_LIVE_BOARD_ON, IS_CHAT_SHOWN } = await import("@/config/flags");

  expect({ IS_LIVE_BOARD_ON, IS_CHAT_SHOWN }).toEqual({
    IS_LIVE_BOARD_ON: true,
    IS_CHAT_SHOWN: true,
  });
});
