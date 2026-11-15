import { act, renderHook } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";

import { LANGUAGE_STORAGE_KEY } from "@/components/shell/language-choice";
import type { DraftSpec } from "@/contracts/types";
import { MARK_SKIP_ACTIVATED } from "@/lib/perf";

import { actions, getState, resetStore, subscribe, useAppStore } from "./store";

const SNOW: DraftSpec = {
  var: "PRECSNO",
  metric: {
    id: "first_date",
    op: ">=",
    season_start: "08-01",
    threshold: "0.1",
  },
};
const SEOUL = { lat: 37.5665, lon: 126.978 };
/** The form of a session ID in docs/BUILD_CONTRACT.md. */
const SESSION_ID_FORM = /^[A-Za-z0-9_-]{8,64}$/;

function confirmSnow(): void {
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  performance.clearMarks();
  resetStore();
});

test("should start a door at the first step", () => {
  actions.goToStep(3);

  actions.chooseDoor("guided");

  expect(getState()).toMatchObject({ mode: "guided", step: 1 });
});

test("should go back to the step before", () => {
  actions.chooseDoor("guided");
  actions.goToStep(3);

  actions.back();

  expect(getState().step).toBe(2);
});

test("should go back from the first step to the doors", () => {
  actions.chooseDoor("guided");

  actions.back();

  expect(getState().mode).toBeNull();
});

test("should open Explore mode on Skip", () => {
  actions.chooseDoor("guided");

  actions.skipToExplore();

  expect(getState().mode).toBe("explore");
});

test("should set the mark skip-activated on Skip", () => {
  actions.skipToExplore();

  expect(performance.getEntriesByName(MARK_SKIP_ACTIVATED)).toHaveLength(1);
});

test("should clear the confirmation when the fetch source changes", () => {
  confirmSnow();

  actions.setFetchSource("fixture");

  expect(getState()).toMatchObject({
    fetchSource: "fixture",
    confirmedSpec: null,
  });
});

test("should start a demo case on the fixture source", () => {
  actions.startDemo("first-snow-seoul");

  expect(getState()).toMatchObject({
    mode: "demo",
    fetchSource: "fixture",
    demo: { caseId: "first-snow-seoul", stepIndex: 0, isPaused: false },
  });
});

test("should start a demo case from a new investigation", () => {
  confirmSnow();
  actions.openPanel("trend");

  actions.startDemo("first-snow-seoul");

  expect(getState()).toMatchObject({
    draftSpec: null,
    confirmedSpec: null,
    area: { pin: null, radiusKm: 25 },
    window: { start: 1981, end: "latest" },
    openPanels: [],
  });
});

test("should move a demo to a step", () => {
  actions.startDemo("first-snow-seoul");

  actions.setDemoStep(4);

  expect(getState().demo?.stepIndex).toBe(4);
});

test("should pause a demo", () => {
  actions.startDemo("first-snow-seoul");

  actions.pauseDemo(true);

  expect(getState().demo?.isPaused).toBe(true);
});

test("should end a demo on the live source with no confirmed spec", () => {
  actions.startDemo("first-snow-seoul");
  actions.editDraft(SNOW, "demo");
  actions.confirmSpec();

  actions.endDemo();

  expect(getState()).toMatchObject({
    fetchSource: "live",
    demo: null,
    confirmedSpec: null,
  });
});

test("should give the tab a session ID in the contract form", () => {
  expect(getState().sessionId).toMatch(SESSION_ID_FORM);
});

test("should keep the session ID of the tab across a page load", () => {
  const before = getState().sessionId;

  resetStore();

  expect(getState().sessionId).toBe(before);
});

test("should start in the stored language", () => {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "ko");

  resetStore();

  expect(getState().lang).toBe("ko");
});

test("should tell a subscriber about a change", () => {
  let changes = 0;
  subscribe(() => (changes += 1));

  actions.setUnits("imperial");

  expect(changes).toBe(1);
});

test("should stop telling a subscriber that left", () => {
  let changes = 0;
  const unsubscribe = subscribe(() => (changes += 1));

  unsubscribe();
  actions.setUnits("imperial");

  expect(changes).toBe(0);
});

test("should render a component again with the selected member", () => {
  const { result } = renderHook(() => useAppStore((state) => state.units));

  act(() => actions.setUnits("imperial"));

  expect(result.current).toBe("imperial");
});
