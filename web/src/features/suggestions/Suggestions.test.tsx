import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, expect, test } from "vitest";

import type { Outcome } from "@/features/verdict/outcome";
import { messages } from "@/i18n/messages";
import { actions, getState, resetStore } from "@/state/store";

import { Suggestions } from "./Suggestions";

const RECORD_START_YEAR = 1981;
const NARROW_WINDOW = { start: 2001, end: "latest" } as const;
const OPEN_BOARD = "Open the case board";
const TRY_NEARBY = "Try a nearby area";
const WIDEN = "Widen the time window to the full record";
const PICK_VARIABLE = "Pick another variable";

const ACTIONS: {
  name: string;
  outcome: Outcome;
  read: () => unknown;
  expected: unknown;
}[] = [
  {
    name: OPEN_BOARD,
    outcome: "significant_rise",
    read: () => getState().openPanels,
    expected: ["caseboard"],
  },
  { name: TRY_NEARBY, outcome: "not_yet", read: () => getState().step, expected: 3 },
  { name: PICK_VARIABLE, outcome: "not_yet", read: () => getState().step, expected: 2 },
  {
    name: WIDEN,
    outcome: "not_yet",
    read: () => getState().window,
    expected: { start: RECORD_START_YEAR, end: "latest" },
  },
];

function renderSuggestions(outcome: Outcome, locale: "en" | "ko" = "en") {
  return render(
    <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
      <Suggestions outcome={outcome} recordStartYear={RECORD_START_YEAR} />
    </NextIntlClientProvider>,
  );
}

function buttonNames(): string[] {
  return screen.getAllByRole("button").map((button) => button.textContent ?? "");
}

beforeEach(() => {
  resetStore();
  actions.setWindow(NARROW_WINDOW, "user");
});

test.each<{ outcome: Outcome; names: string[] }>([
  { outcome: "significant_rise", names: [OPEN_BOARD, TRY_NEARBY, PICK_VARIABLE] },
  { outcome: "significant_fall", names: [OPEN_BOARD, TRY_NEARBY, PICK_VARIABLE] },
  { outcome: "not_yet", names: [WIDEN, TRY_NEARBY, PICK_VARIABLE] },
  { outcome: "no_trend", names: [TRY_NEARBY, PICK_VARIABLE, WIDEN] },
  { outcome: "record_too_short", names: [WIDEN, PICK_VARIABLE] },
  { outcome: "no_data", names: [TRY_NEARBY, PICK_VARIABLE] },
])("should offer the next actions of $outcome", ({ outcome, names }) => {
  renderSuggestions(outcome);

  expect(buttonNames()).toEqual(names);
});

test("should leave out widening when the window is the full record", () => {
  resetStore();
  renderSuggestions("not_yet");

  expect(screen.queryByRole("button", { name: WIDEN })).toBeNull();
});

test("should name the actions in Korean", () => {
  renderSuggestions("significant_rise", "ko");

  expect(buttonNames()).toEqual(["사례 보드 열기", "가까운 지역 살펴보기", "다른 변수 고르기"]);
});

test("should label the list of next steps", () => {
  renderSuggestions("not_yet");

  expect(screen.getByRole("region", { name: "Next steps" })).toBeInTheDocument();
});

test.each(ACTIONS)("should run $name on a click", async ({ name, outcome, read, expected }) => {
  renderSuggestions(outcome);

  await userEvent.click(screen.getByRole("button", { name }));

  expect(read()).toEqual(expected);
});

test.each(ACTIONS)("should run $name from the keyboard", async ({ name, outcome, read, expected }) => {
  renderSuggestions(outcome);
  screen.getByRole("button", { name }).focus();

  await userEvent.keyboard("{Enter}");

  expect(read()).toEqual(expected);
});

test("should keep the focus on an action that stays", async () => {
  renderSuggestions("significant_rise");
  const button = screen.getByRole("button", { name: OPEN_BOARD });

  await userEvent.click(button);

  expect(button).toHaveFocus();
});

test("should move the focus to the list title when widening removes its button", async () => {
  renderSuggestions("not_yet");

  await userEvent.click(screen.getByRole("button", { name: WIDEN }));

  expect(screen.getByRole("heading", { name: "Next steps" })).toHaveFocus();
});
