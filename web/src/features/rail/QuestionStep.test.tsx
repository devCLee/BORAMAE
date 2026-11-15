import { act, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { actions, resetStore } from "@/state/store";

import { QUESTION_EN, renderRail, serveApi } from "./rail-test-utils";

beforeEach(() => {
  resetStore();
  serveApi();
  actions.chooseDoor("guided");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should show a question that the store receives after the field mounted", () => {
  renderRail();

  act(() => actions.setQuestion(QUESTION_EN));

  expect(
    screen.getByRole("textbox", { name: "What do you want to investigate?" }),
  ).toHaveValue(QUESTION_EN);
});
