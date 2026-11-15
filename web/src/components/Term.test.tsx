import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { expect, test } from "vitest";

import { Term } from "@/components/Term";
import { messages } from "@/i18n/messages";
import { catalog } from "@/test/fixtures";

const AIR_TEMPERATURE = catalog.variables[0];

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

test("should label the trigger with the glossary name", () => {
  renderIn(<Term id="p_value" />);

  expect(screen.getByRole("button", { name: "p-value" })).toBeInTheDocument();
});

test("should keep the text that the caller gives", () => {
  renderIn(<Term id="sen_slope">rate</Term>);

  expect(screen.getByRole("button", { name: "rate" })).toBeInTheDocument();
});

test("should open the glossary entry on a click", async () => {
  renderIn(<Term id="p_value" />);

  await userEvent.click(screen.getByRole("button", { name: "p-value" }));

  expect(screen.getByRole("dialog", { name: "p-value" })).toHaveTextContent(
    "not the chance that the trend is real",
  );
});

test("should show what the entry means", async () => {
  renderIn(<Term id="years_needed" />);

  await userEvent.click(screen.getByRole("button", { name: "Years needed" }));

  expect(screen.getByRole("dialog")).toHaveTextContent(
    "What this means: A detection estimate, not a forecast",
  );
});

test("should open the entry in the UI language", async () => {
  renderIn(<Term id="p_value" />, "ko");

  await userEvent.click(screen.getByRole("button", { name: "p값" }));

  expect(screen.getByRole("dialog")).toHaveTextContent(
    "추세가 진짜일 확률이 아니다",
  );
});

test("should open a variable with its catalog definition", async () => {
  renderIn(
    <Term id={AIR_TEMPERATURE.id} definition={AIR_TEMPERATURE.definition}>
      {AIR_TEMPERATURE.name.en}
    </Term>,
  );

  await userEvent.click(
    screen.getByRole("button", { name: AIR_TEMPERATURE.name.en }),
  );

  expect(screen.getByRole("dialog")).toHaveTextContent(
    AIR_TEMPERATURE.definition.en,
  );
});

test("should open a variable definition in the UI language", async () => {
  renderIn(
    <Term id={AIR_TEMPERATURE.id} definition={AIR_TEMPERATURE.definition}>
      {AIR_TEMPERATURE.name.ko}
    </Term>,
    "ko",
  );

  await userEvent.click(
    screen.getByRole("button", { name: AIR_TEMPERATURE.name.ko }),
  );

  expect(screen.getByRole("dialog")).toHaveTextContent(
    AIR_TEMPERATURE.definition.ko,
  );
});

test("should open from the keyboard", async () => {
  renderIn(<Term id="autocorrelation" />);
  screen.getByRole("button", { name: "Autocorrelation" }).focus();

  await userEvent.keyboard("{Enter}");

  expect(
    screen.getByRole("dialog", { name: "Autocorrelation" }),
  ).toBeInTheDocument();
});

test("should close on Escape", async () => {
  renderIn(<Term id="autocorrelation" />);
  await userEvent.click(screen.getByRole("button", { name: "Autocorrelation" }));

  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("should return focus to the trigger on Escape", async () => {
  renderIn(<Term id="autocorrelation" />);
  const trigger = screen.getByRole("button", { name: "Autocorrelation" });
  await userEvent.click(trigger);

  await userEvent.keyboard("{Escape}");

  expect(trigger).toHaveFocus();
});
