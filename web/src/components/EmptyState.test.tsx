import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { expect, test } from "vitest";

import { EmptyState } from "@/components/EmptyState";
import { messages } from "@/i18n/messages";

function renderIn(ui: ReactNode, locale: "en" | "ko" = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      {ui}
    </NextIntlClientProvider>,
  );
}

test("should show the message of its key", () => {
  renderIn(<EmptyState messageKey="zoom_in_or_pin" />);

  expect(screen.getByRole("status")).toHaveTextContent(
    "This view covers too large an area.",
  );
});

test("should show the message in Korean", () => {
  renderIn(<EmptyState messageKey="not_in_offline_demo" />, "ko");

  expect(screen.getByRole("status")).toHaveTextContent(
    "오프라인 데모에는 데모에 쓰인 결과만 들어 있어요.",
  );
});

test("should offer no retry without a retry handler", () => {
  renderIn(<EmptyState messageKey="timeout" />);

  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("should retry on a click", async () => {
  let retries = 0;
  renderIn(<EmptyState messageKey="network" onRetry={() => (retries += 1)} />);

  await userEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(retries).toBe(1);
});

test("should retry from the keyboard", async () => {
  let retries = 0;
  renderIn(<EmptyState messageKey="network" onRetry={() => (retries += 1)} />);
  screen.getByRole("button", { name: "Try again" }).focus();

  await userEvent.keyboard("{Enter}");

  expect(retries).toBe(1);
});
