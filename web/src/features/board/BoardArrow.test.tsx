import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { resetStore } from "@/state/store";
import { catalog } from "@/test/fixtures";

import {
  confirmSeoulSnow,
  findArrow,
  findField,
  findLoadedBoard,
  NODE_TREND,
  openArrow,
  renderInApp,
  serveLive,
} from "./board-test-kit";

const NUM = /^Source of /;
const NODE_P_SHOWN = new Intl.NumberFormat("en", {
  maximumSignificantDigits: 2,
  roundingMode: "trunc",
}).format(NODE_TREND.stats.mk.p ?? Number.NaN);
const LABEL_WORDS = /Consistent|Weak|Contradicts|Not testable here/;
const LINK = "Link test";
const REGISTRY_REASON = "The registry marks this link as one that NASA POWER cannot test.";
const ARROW_NAMES = ["Air temperature", "Water vapour", "Skin temperature", "Snow depth", "Snow cover"];
const LABELS = [
  { name: "Air temperature", label: "Consistent" },
  { name: "Water vapour", label: "Contradicts" },
  { name: "Skin temperature", label: "Weak" },
  { name: "Snow cover", label: "Not testable here" },
];

beforeEach(() => {
  resetStore();
  confirmSeoulSnow();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test.each(LABELS)("should label the $name arrow $label", async ({ name, label }) => {
  serveLive();
  renderInApp();

  expect(within(await findField(name, LINK)).getByText(label)).toBeInTheDocument();
});

test.each(LABELS)("should pair the $label label with an icon", async ({ name, label }) => {
  serveLive();
  renderInApp();

  expect(within(await findField(name, LINK)).getByText(label).querySelector("svg")).not.toBeNull();
});

test.each([
  { name: "Air temperature", href: "https://doi.org/10.5555/boramae.sample.1" },
  { name: "Skin temperature", href: "https://example.org/boramae-sample-3" },
])("should link the $name arrow to its source", async ({ name, href }) => {
  serveLive();
  renderInApp();

  expect(within(await findArrow(name)).getByRole("link")).toHaveAttribute("href", href);
});

test.each([
  { name: "Air temperature", field: "Scale", text: "regional" },
  { name: "Water vapour", field: "Evidence", text: "Contested" },
])("should show the $field of an arrow", async ({ name, field, text }) => {
  serveLive();
  renderInApp();

  expect(await findField(name, field)).toHaveTextContent(text);
});

test.each([
  { label: "a labelled", name: "Air temperature", shown: "0.52" },
  { label: "an empty", name: "Snow depth", shown: "0.09" },
])("should show the link numbers of an arrow with $label label through Num", async ({ name, shown }) => {
  serveLive();
  renderInApp();
  const field = await findField(name, LINK);

  expect(await within(field).findByRole("button", { name: `Source of ${shown}` })).toBeInTheDocument();
});

test("should give a not-testable arrow its reason", async () => {
  serveLive();
  renderInApp();

  expect(within(await findArrow("Snow cover")).getByText(REGISTRY_REASON)).toBeInTheDocument();
});

test("should show no numbers in a not-testable arrow, also when it is open", async () => {
  serveLive();
  renderInApp();
  await findLoadedBoard();
  const arrow = await openArrow("Snow cover");

  expect(within(arrow).queryAllByRole("button", { name: NUM })).toEqual([]);
});

test("should show no label word for an empty label", async () => {
  serveLive();
  renderInApp();
  await findLoadedBoard();

  expect(await findField("Snow depth", LINK)).not.toHaveTextContent(LABEL_WORDS);
});

test.each([
  { what: "the rate of its node", num: /^Source of .+ per decade$/ },
  { what: "the p-value of its node", num: `Source of ${NODE_P_SHOWN}` },
  { what: "its effective sample size", num: "Source of 41" },
])("should open an arrow to $what", async ({ num }) => {
  serveLive();
  renderInApp();
  const arrow = await openArrow("Air temperature");

  expect(await within(arrow).findByRole("button", { name: num })).toBeInTheDocument();
});

test("should link a variable name to its catalog definition", async () => {
  serveLive();
  renderInApp();
  await userEvent.click(within(await findArrow("Air temperature")).getByRole("button", { name: "Air temperature" }));

  expect(await screen.findByText(catalog.variables[0].definition.en)).toBeInTheDocument();
});

test.each(ARROW_NAMES)("should open the %s arrow from the keyboard", async (name) => {
  serveLive();
  renderInApp();
  const toggle = within(await findArrow(name)).getByRole("button", { name: `Inputs of ${name}` });
  toggle.focus();
  await userEvent.keyboard("{Enter}");

  expect(toggle).toHaveAttribute("aria-expanded", "true");
});

test("should keep the focus on the toggle of an arrow", async () => {
  serveLive();
  renderInApp();
  const toggle = within(await findArrow("Snow cover")).getByRole("button", { name: "Inputs of Snow cover" });
  toggle.focus();
  await userEvent.keyboard("{Enter}");

  expect(toggle).toHaveFocus();
});

test("should show the labels in Korean", async () => {
  serveLive();
  renderInApp(undefined, "ko");

  expect(within(await findField("기온", "연결 검정")).getByText("일치")).toBeInTheDocument();
});
