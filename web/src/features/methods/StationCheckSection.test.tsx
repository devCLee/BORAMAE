import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { expect, test } from "vitest";

import stationCheck from "@content/evidence/station-phoenix-check.json";
import { messages } from "@/i18n/messages";

import { MethodsPage } from "./MethodsPage";
import { StationCheckSection } from "./StationCheckSection";

type Locale = keyof typeof messages;

const RATE = new Intl.NumberFormat("en", { maximumSignificantDigits: 2 });
const MEAN = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });
const R = new Intl.NumberFormat("en", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const ROWS = [
  { name: "Sky Harbor station (NOAA)", side: stationCheck.station },
  { name: "POWER grid cell (NASA)", side: stationCheck.grid_cell },
];

function renderSection(locale: Locale = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <StationCheckSection />
    </NextIntlClientProvider>,
  );
}

/** The table row of one series, found by its row header. */
function rowOf(name: string): HTMLElement {
  return screen.getByRole("rowheader", { name }).closest("tr") as HTMLElement;
}

test.each(ROWS)("should show the Sen rate of the $name row", ({ name, side }) => {
  renderSection();

  expect(rowOf(name)).toHaveTextContent(
    `${RATE.format(side.trend.sen_per_decade)} days per decade`,
  );
});

test.each(ROWS)(
  "should show the 95% interval of the $name row",
  ({ name, side }) => {
    renderSection();

    expect(rowOf(name)).toHaveTextContent(
      `${RATE.format(side.trend.sen_ci_low_per_decade)} to ${RATE.format(side.trend.sen_ci_high_per_decade)}`,
    );
  },
);

test.each(ROWS)("should show the mean count of the $name row", ({ name, side }) => {
  renderSection();

  expect(rowOf(name)).toHaveTextContent(MEAN.format(side.mean_days));
});

test("should show the correlation of the yearly counts", () => {
  renderSection();

  expect(
    screen.getByText(
      new RegExp(`correlate at r = ${R.format(stationCheck.agreement.pearson_r)}`),
    ),
  ).toBeInTheDocument();
});

test("should show the correlation with the trends taken out", () => {
  renderSection();

  expect(
    screen.getByText(
      new RegExp(`r is still ${R.format(stationCheck.agreement.link_test.r)}`),
    ),
  ).toBeInTheDocument();
});

test("should show how many fewer days the cell counts", () => {
  renderSection();

  expect(
    screen.getByText(
      new RegExp(
        `about ${MEAN.format(stationCheck.agreement.mean_gap_days)} fewer such days`,
      ),
    ),
  ).toBeInTheDocument();
});

test("should label the station data as non-NASA context", () => {
  renderSection();

  expect(
    screen.getByText(
      "NOAA station data, not NASA. Shown here as context only and never used in a verdict.",
    ),
  ).toBeInTheDocument();
});

test("should name the evidence file of the check", () => {
  renderSection();

  expect(
    screen.getByText(/content\/evidence\/station-phoenix-check\.json/),
  ).toBeInTheDocument();
});

test("should render the Korean heading", () => {
  renderSection("ko");

  expect(
    screen.getByRole("heading", { name: "관측소 점검: 피닉스의 더운 날" }),
  ).toBeInTheDocument();
});

test("should show the station check on the Methods page", () => {
  render(
    <NextIntlClientProvider locale="en" messages={messages.en} timeZone="UTC">
      <MethodsPage />
    </NextIntlClientProvider>,
  );

  expect(
    screen.getByRole("region", { name: "Station check: Phoenix hot days" }),
  ).toBeInTheDocument();
});
