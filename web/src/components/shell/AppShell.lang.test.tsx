import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, expect, test, vi } from "vitest";

import { AppShell } from "@/components/shell/AppShell";
import { Providers } from "@/components/shell/Providers";
import { messages } from "@/i18n/messages";
import { getState, resetStore } from "@/state/store";

vi.mock("@/i18n/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/i18n/navigation")>()),
  usePathname: () => "/",
}));

beforeEach(() => {
  window.localStorage.clear();
  resetStore();
});

test("should hold the language of the route in the store", () => {
  render(
    <NextIntlClientProvider locale="ko" messages={messages.ko} timeZone="UTC">
      <Providers>
        <AppShell />
      </Providers>
    </NextIntlClientProvider>,
  );

  expect(getState().lang).toBe("ko");
});
