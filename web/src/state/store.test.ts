import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { DraftSpec, RequestMeta } from "@/contracts/types";

import { actions, getState, resetStore } from "./store";
import type { Source } from "./types";

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
const JEJU = { lat: 33.4996, lon: 126.5312 };
const LAST_30_YEARS = { start: 1991, end: 2020 };
const EVERY_SOURCE: Source[] = ["user", "guide", "demo"];
const META: RequestMeta = {
  resultKey: "b5bae5463e95eff888bca78a896bf62a",
  requestId: "req-7f3a9c",
  cache: "hit",
  bytesFetched: 0,
  serverTiming: "total;dur=52",
  usedContainingCell: false,
  sourceUrl: "/r/trend/b5bae5463e95eff888bca78a896bf62a.json",
};
/** The form of a session ID in docs/BUILD_CONTRACT.md. */
const SESSION_ID_FORM = /^[A-Za-z0-9_-]{8,64}$/;

function blockStorage(): void {
  const refuse = () => {
    throw new DOMException("The operation is insecure.", "SecurityError");
  };
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(refuse);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(refuse);
}

/** A confirmed spec with a result on screen: the state that an edit must clear. */
function showConfirmedResult(): void {
  actions.editDraft(SNOW, "user");
  actions.setPin(SEOUL, "user");
  actions.confirmSpec();
  actions.openPanel("trend");
  actions.setRequestMeta("trend", META);
  actions.revealVerdict();
}

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("should start with no confirmed spec", () => {
  expect(getState().confirmedSpec).toBeNull();
});

test("should confirm the draft spec", () => {
  actions.editDraft(SNOW, "user");

  actions.confirmSpec();

  expect(getState().confirmedSpec).toEqual(SNOW);
});

test("should confirm nothing while no draft exists", () => {
  actions.confirmSpec();

  expect(getState().confirmedSpec).toBeNull();
});

test("should replace a member of the draft whole", () => {
  actions.editDraft(SNOW, "user");

  actions.editDraft({ metric: { id: "annual_total" } }, "user");

  expect(getState().draftSpec).toEqual({
    var: "PRECSNO",
    metric: { id: "annual_total" },
  });
});

test.each(EVERY_SOURCE)(
  "should clear the confirmation when %s edits the draft",
  (source) => {
    showConfirmedResult();

    actions.editDraft({ var: "T2M" }, source);

    expect(getState().confirmedSpec).toBeNull();
  },
);

test.each(EVERY_SOURCE)(
  "should clear the confirmation when %s moves the pin",
  (source) => {
    showConfirmedResult();

    actions.setPin(JEJU, source);

    expect(getState().confirmedSpec).toBeNull();
  },
);

test.each(EVERY_SOURCE)(
  "should clear the confirmation when %s changes the radius",
  (source) => {
    showConfirmedResult();

    actions.setRadius(100, source);

    expect(getState().confirmedSpec).toBeNull();
  },
);

test("should keep the confirmation when the user changes the window", () => {
  showConfirmedResult();

  actions.setWindow(LAST_30_YEARS, "user");

  expect(getState().confirmedSpec).toEqual(SNOW);
});

test("should keep the panels open when the user changes the window", () => {
  showConfirmedResult();

  actions.setWindow(LAST_30_YEARS, "user");

  expect(getState().openPanels).toEqual(["trend"]);
});

test.each<Source>(["guide", "demo"])(
  "should clear the confirmation when %s changes the window",
  (source) => {
    showConfirmedResult();

    actions.setWindow(LAST_30_YEARS, source);

    expect(getState().confirmedSpec).toBeNull();
  },
);

test.each(EVERY_SOURCE)("should store the window that %s sets", (source) => {
  actions.setWindow(LAST_30_YEARS, source);

  expect(getState().window).toEqual(LAST_30_YEARS);
});

test("should close every panel when the confirmation is cleared", () => {
  showConfirmedResult();

  actions.setPin(JEJU, "user");

  expect(getState().openPanels).toEqual([]);
});

test("should drop the request facts when the confirmation is cleared", () => {
  showConfirmedResult();

  actions.setPin(JEJU, "user");

  expect(getState().meta.trend).toBeNull();
});

test("should hide the verdict again when the confirmation is cleared", () => {
  showConfirmedResult();

  actions.setPin(JEJU, "user");

  expect(getState().verdictGate).toBe("pending");
});

test("should set the pin at the point of a map click", () => {
  actions.runAtPoint(JEJU);

  expect(getState().area.pin).toEqual(JEJU);
});

test("should confirm the draft at the point of a map click", () => {
  actions.editDraft(SNOW, "user");

  actions.runAtPoint(JEJU);

  expect(getState().confirmedSpec).toEqual(SNOW);
});

test("should confirm T2M annual mean at a map click with no draft", () => {
  actions.runAtPoint(JEJU);

  expect(getState().confirmedSpec).toEqual({
    var: "T2M",
    metric: { id: "annual_mean" },
  });
});

test("should open only the trend panel at a map click", () => {
  showConfirmedResult();
  actions.openPanel("scan");

  actions.runAtPoint(JEJU);

  expect(getState().openPanels).toEqual(["trend"]);
});

test("should open a panel one time", () => {
  actions.openPanel("scan");

  actions.openPanel("scan");

  expect(getState().openPanels).toEqual(["scan"]);
});

test("should close a panel", () => {
  actions.openPanel("trend");
  actions.openPanel("caseboard");

  actions.closePanel("trend");

  expect(getState().openPanels).toEqual(["caseboard"]);
});

test("should drop the request facts of a closed panel", () => {
  showConfirmedResult();

  actions.closePanel("trend");

  expect(getState().meta.trend).toBeNull();
});

test("should reveal the verdict", () => {
  actions.revealVerdict();

  expect(getState().verdictGate).toBe("revealed");
});

test("should start in English when browser storage throws", () => {
  blockStorage();

  resetStore();

  expect(getState().lang).toBe("en");
});

test("should give a session ID when browser storage throws", () => {
  blockStorage();

  resetStore();

  expect(getState().sessionId).toMatch(SESSION_ID_FORM);
});

test("should keep the store working when browser storage throws", () => {
  blockStorage();
  resetStore();

  actions.setLang("ko");

  expect(getState().lang).toBe("ko");
});
