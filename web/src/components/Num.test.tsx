import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { beforeEach, expect, expectTypeOf, test } from "vitest";

import { Num, type NumProps } from "@/components/Num";
import type { Provenance } from "@/contracts/types";
import { ProvenanceDrawer } from "@/features/provenance/ProvenanceDrawer";
import { closeProvenance } from "@/features/provenance/provenance-state";
import { messages } from "@/i18n/messages";
import { trendSignificant } from "@/test/fixtures";

const { provenance, footprint } = trendSignificant;

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

beforeEach(() => {
  closeProvenance();
});

test("should render the value in the number format of the UI language", () => {
  renderIn(<Num value={1234.5} provenance={provenance} />);

  expect(screen.getByText("1,234.5")).toBeInTheDocument();
});

test("should round the value by the options it gets", () => {
  renderIn(
    <Num
      value={3.288288}
      provenance={provenance}
      options={{ maximumFractionDigits: 1 }}
    />,
  );

  expect(screen.getByText("3.3")).toBeInTheDocument();
});

test("should render a share rate through formatRate", () => {
  renderIn(
    <Num
      value={0.012}
      provenance={provenance}
      rate={{ unit: "percent_points", shareScale: "fraction" }}
    />,
  );

  expect(screen.getByText("1.2 points per decade")).toBeInTheDocument();
});

test("should name the info button after the value", () => {
  renderIn(<Num value={1.5} provenance={provenance} />);

  expect(
    screen.getByRole("button", { name: "Source of 1.5" }),
  ).toBeInTheDocument();
});

test("should name the info button in Korean", () => {
  renderIn(<Num value={1.5} provenance={provenance} />, "ko");

  expect(screen.getByRole("button", { name: "1.5의 출처" })).toBeInTheDocument();
});

test("should open the drawer with its provenance from the info button", async () => {
  renderIn(
    <>
      <Num value={1.5} provenance={provenance} footprint={footprint} />
      <ProvenanceDrawer />
    </>,
  );

  await userEvent.click(screen.getByRole("button", { name: "Source of 1.5" }));

  expect(screen.getByRole("dialog")).toHaveTextContent(provenance.access_path);
});

test("should open the drawer from the keyboard", async () => {
  renderIn(
    <>
      <Num value={1.5} provenance={provenance} />
      <ProvenanceDrawer />
    </>,
  );
  screen.getByRole("button", { name: "Source of 1.5" }).focus();

  await userEvent.keyboard("{Enter}");

  expect(screen.getByRole("dialog")).toHaveTextContent(provenance.dataset_id);
});

// A type check: npm run typecheck fails when provenance becomes optional.
test("should require a provenance prop", () => {
  expectTypeOf<NumProps>()
    .toHaveProperty("provenance")
    .toEqualTypeOf<Provenance>();
});
