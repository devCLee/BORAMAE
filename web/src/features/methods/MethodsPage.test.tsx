import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { expect, test } from "vitest";

import falseAlarm from "@content/evidence/false-alarm.json";
import licenses from "@content/licenses.json";
import { messages } from "@/i18n/messages";

import { MethodsPage } from "./MethodsPage";

type Locale = keyof typeof messages;

const [, GATE_FAILED] = falseAlarm.rates;
const PERCENT = new Intl.NumberFormat("en", {
  style: "percent",
  maximumFractionDigits: 1,
});
const SERIES_COUNT = new Intl.NumberFormat("en").format(falseAlarm.series_per_r1);
// D-09: the one protocol run passed at r1 = 0, failed at r1 = 0.2 and reports r1 = 0.4 alone.
const GATE_RESULTS = [
  { r1: 0, result: "Pass" },
  { r1: 0.2, result: "Fail" },
  { r1: 0.4, result: "Reported separately" },
];

function renderPage(locale: Locale = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={messages[locale]}
      timeZone="UTC"
    >
      <MethodsPage />
    </NextIntlClientProvider>,
  );
}

/** The table row of one r1 value, found by its row header. */
function rowOf(r1: number): HTMLElement {
  return screen
    .getByRole("rowheader", { name: String(r1) })
    .closest("tr") as HTMLElement;
}

test("should keep the slot test ID on the root", () => {
  renderPage();

  expect(screen.getByTestId("slot-methods")).toBeInTheDocument();
});

test.each(falseAlarm.rates)(
  "should show the measured rate at r1 = $r1",
  ({ r1, rate }) => {
    renderPage();

    expect(rowOf(r1)).toHaveTextContent(PERCENT.format(rate));
  },
);

test.each(falseAlarm.rates)(
  "should show the false-alarm count at r1 = $r1",
  ({ r1, false_alarms }) => {
    renderPage();

    expect(rowOf(r1)).toHaveTextContent(`${false_alarms} of ${SERIES_COUNT}`);
  },
);

test.each(falseAlarm.rates)(
  "should show the 95% interval at r1 = $r1",
  ({ r1, ci95: [low, high] }) => {
    renderPage();

    expect(rowOf(r1)).toHaveTextContent(
      `${PERCENT.format(low)} to ${PERCENT.format(high)}`,
    );
  },
);

test.each(GATE_RESULTS)(
  "should mark the result at r1 = $r1 as $result",
  ({ r1, result }) => {
    renderPage();

    expect(within(rowOf(r1)).getByText(result)).toBeInTheDocument();
  },
);

test("should keep the failed rate unrounded", () => {
  renderPage();

  expect(rowOf(GATE_FAILED.r1)).toHaveTextContent("7.3%");
});

test("should state the pass rule from the evidence file", () => {
  renderPage();

  expect(
    screen.getByText(
      "Pass rule: at most 7% false alarms for r₁ up to 0.2. Higher r₁ values are reported separately, with no pass rule.",
    ),
  ).toBeInTheDocument();
});

test("should describe the run with its series count, length and seed", () => {
  renderPage();

  expect(
    screen.getByText(
      new RegExp(
        `${SERIES_COUNT} series with no trend, each with ${falseAlarm.length} yearly values.*seed, ${falseAlarm.seed},`,
      ),
    ),
  ).toBeInTheDocument();
});

test("should name the evidence file of the table", () => {
  renderPage();

  expect(
    screen.getByText(/content\/evidence\/false-alarm\.json/),
  ).toBeInTheDocument();
});

test("should state that POWER is model data", () => {
  renderPage();

  expect(
    screen.getByText(/POWER is model data, not observation/),
  ).toBeInTheDocument();
});

test("should render one attribution per inventory entry", () => {
  renderPage();

  expect(
    within(
      screen.getByRole("region", { name: "Sources and licenses" }),
    ).getAllByRole("listitem"),
  ).toHaveLength(licenses.length);
});

test.each(licenses)("should link $name to its source", ({ name, url }) => {
  renderPage();

  expect(screen.getByRole("link", { name })).toHaveAttribute("href", url);
});

test("should show the license of an entry", () => {
  renderPage();

  expect(screen.getByText("License: OFL-1.1")).toBeInTheDocument();
});

test("should show the AI-use note", () => {
  renderPage();

  expect(
    within(screen.getByRole("region", { name: "How AI is used" })).getByText(
      /AI produces no number on this site/,
    ),
  ).toBeInTheDocument();
});

test("should link back to the app", () => {
  renderPage();

  expect(
    screen.getByRole("link", { name: "Back to the app" }),
  ).toHaveAttribute("href", "/en");
});

test("should reach the back link first with the Tab key", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.tab();

  expect(screen.getByRole("link", { name: "Back to the app" })).toHaveFocus();
});

test("should render the Korean page title", () => {
  renderPage("ko");

  expect(
    screen.getByRole("heading", { level: 1, name: "방법과 출처" }),
  ).toBeInTheDocument();
});

test("should mark the failed gate in Korean", () => {
  renderPage("ko");

  expect(within(rowOf(GATE_FAILED.r1)).getByText("실패")).toBeInTheDocument();
});
