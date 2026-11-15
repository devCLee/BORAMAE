import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, expect, test, vi } from "vitest";

import { AppShell } from "@/components/shell/AppShell";
import { LANGUAGE_STORAGE_KEY } from "@/components/shell/language-choice";
import { Providers } from "@/components/shell/Providers";
import { messages } from "@/i18n/messages";

const CURRENT_ROUTE = "/methods";

// The switch keeps the route, so the test needs a route that is not the home page.
vi.mock("@/i18n/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/i18n/navigation")>()),
  usePathname: () => CURRENT_ROUTE,
}));

const SLOT_IDS = [
  "slot-rail",
  "slot-map",
  "slot-places",
  "slot-case",
  "slot-window",
  "slot-guide",
  "slot-demo",
  "slot-provenance",
];

function renderShell(locale: "en" | "ko" = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <Providers>
        <AppShell />
      </Providers>
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

test.each(SLOT_IDS)("should mount the %s slot", (slotId) => {
  renderShell();

  expect(screen.getByTestId(slotId)).toBeInTheDocument();
});

test("should put the case panel in the result region", () => {
  renderShell();

  const region = screen.getByRole("region", { name: "Result" });

  expect(within(region).getByTestId("slot-case")).toBeInTheDocument();
});

test("should put the time slider in the time window region", () => {
  renderShell();

  const region = screen.getByRole("region", { name: "Time window" });

  expect(within(region).getByTestId("slot-window")).toBeInTheDocument();
});

test("should focus the skip link first", async () => {
  renderShell();

  await userEvent.tab();

  expect(
    screen.getByRole("link", { name: "Skip to main content" }),
  ).toHaveFocus();
});

test("should point the skip link at the main content", () => {
  renderShell();

  const target = screen
    .getByRole("link", { name: "Skip to main content" })
    .getAttribute("href");

  expect(document.querySelector(target ?? "")).toBe(screen.getByRole("main"));
});

test("should link to the Korean version of the same route", () => {
  renderShell();

  expect(screen.getByRole("link", { name: "한국어" })).toHaveAttribute(
    "href",
    `/ko${CURRENT_ROUTE}`,
  );
});

test("should offer English on a Korean page", () => {
  renderShell("ko");

  expect(screen.getByRole("link", { name: "English" })).toHaveAttribute(
    "href",
    `/en${CURRENT_ROUTE}`,
  );
});

test("should store the language chosen in the header", async () => {
  renderShell();
  // jsdom cannot load another document, so the click stays on this page.
  document.addEventListener("click", (event) => event.preventDefault(), {
    once: true,
  });

  await userEvent.click(screen.getByRole("link", { name: "한국어" }));

  expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("ko");
});

test("should open the result sheet by default", () => {
  renderShell();

  expect(screen.getByRole("button", { name: "Result" })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
});

test("should fold the result sheet on a click", async () => {
  renderShell();
  const toggle = screen.getByRole("button", { name: "Result" });

  await userEvent.click(toggle);

  expect(toggle).toHaveAttribute("aria-expanded", "false");
});

test("should fold the result sheet from the keyboard", async () => {
  renderShell();
  const toggle = screen.getByRole("button", { name: "Result" });
  toggle.focus();

  await userEvent.keyboard("{Enter}");

  expect(toggle).toHaveAttribute("aria-expanded", "false");
});

test("should keep focus on the sheet control after a fold", async () => {
  renderShell();
  const toggle = screen.getByRole("button", { name: "Result" });

  await userEvent.click(toggle);

  expect(toggle).toHaveFocus();
});

test("should keep the case panel mounted while the sheet is folded", async () => {
  renderShell();

  await userEvent.click(screen.getByRole("button", { name: "Result" }));

  expect(screen.getByTestId("slot-case")).toBeInTheDocument();
});
