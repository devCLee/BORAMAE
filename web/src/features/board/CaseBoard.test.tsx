import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { CasePanel } from "@/features/case/CasePanel";
import { hang, inTurn } from "@/lib/fetch-layer.stub";
import { actions, resetStore } from "@/state/store";
import { caseBoard } from "@/test/fixtures";

import {
  answer,
  boardAnswer,
  confirmBundledSeoulSnow,
  confirmSeoulSnow,
  failure,
  findArrow,
  findLoadedBoard,
  openArrow,
  passAllRetries,
  reduceMotion,
  renderInApp,
  serveBundle,
  serveLive,
  unavailable,
} from "./board-test-kit";

// flags.ts reads the env at import, so the tests turn the live-board flag through this switch.
const flags = vi.hoisted(() => ({ isLiveBoardOn: true }));
vi.mock("@/config/flags", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/config/flags")>()),
  get IS_LIVE_BOARD_ON() {
    return flags.isLiveBoardOn;
  },
}));

const NO_BOARD = answer({ ...caseBoard, board_id: null, nodes: [] }, "0".repeat(32));
const RETRY = "Load the case board again";
const LIVE_OFF = "The live case board is off for now. The two demo cases still show their boards.";
const NO_BOARD_TEXT = "No case board exists for this variable yet.";

beforeEach(() => {
  flags.isLiveBoardOn = true;
  resetStore();
  confirmSeoulSnow();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test.each([
  { state: "loading", setup: () => serveLive(hang), ready: () => screen.findByRole("status") },
  { state: "loaded", setup: () => serveLive(), ready: () => screen.findByText("Consistent") },
  { state: "failed", setup: () => serveLive(failure), ready: () => screen.findByText(RETRY) },
  { state: "without a board", setup: () => serveLive(NO_BOARD), ready: () => screen.findByText(NO_BOARD_TEXT) },
])("should keep the slot test ID when the board is $state", async ({ setup, ready }) => {
  setup();
  renderInApp();
  await ready();

  expect(screen.getByTestId("slot-board")).toBeInTheDocument();
});

test("should show a skeleton while the board loads", async () => {
  serveLive(hang);
  renderInApp();

  expect(await screen.findByRole("status", { name: "Loading the case board" })).toBeInTheDocument();
});

test("should ask the live service for the board", async () => {
  const calls = serveLive();
  renderInApp();
  await findArrow("Air temperature");

  expect(calls.some((call) => call.url.includes("/api/v1/caseboard?s="))).toBe(true);
});

test("should show every arrow of the board, a contradiction too", async () => {
  serveLive();
  renderInApp();
  await findArrow("Water vapour");

  expect(screen.getAllByRole("listitem")).toHaveLength(caseBoard.nodes.length);
});

test("should list the drivers apart from the responses", async () => {
  serveLive();
  renderInApp();

  expect(within(await screen.findByRole("list", { name: "Drivers" })).getAllByRole("listitem")).toHaveLength(3);
});

test("should place the focus between the drivers and the responses", async () => {
  serveLive();
  renderInApp();
  const drivers = await screen.findByRole("list", { name: "Drivers" });
  const focus = screen.getByRole("group", { name: "Focus" });
  const responses = screen.getByRole("list", { name: "Responses" });

  expect([drivers.compareDocumentPosition(focus), focus.compareDocumentPosition(responses)]).toEqual([
    Node.DOCUMENT_POSITION_FOLLOWING,
    Node.DOCUMENT_POSITION_FOLLOWING,
  ]);
});

test("should say that a variable has no board", async () => {
  serveLive(NO_BOARD);
  renderInApp();

  expect(await screen.findByText(NO_BOARD_TEXT)).toBeInTheDocument();
});

test("should offer a retry after a 503 answer", async () => {
  vi.useFakeTimers();
  serveLive(unavailable);
  renderInApp();
  await passAllRetries();

  expect(await screen.findByRole("button", { name: RETRY })).toBeInTheDocument();
});

test("should keep the verdict card after a 503 answer of the board", async () => {
  vi.useFakeTimers();
  serveLive(unavailable);
  actions.revealVerdict();
  renderInApp(<CasePanel />);
  await passAllRetries();
  await screen.findByRole("button", { name: RETRY });

  expect(screen.getByRole("article")).toBeInTheDocument();
});

test("should ask for the board again on a retry", async () => {
  serveLive(inTurn(failure, boardAnswer));
  renderInApp();
  await userEvent.click(await screen.findByRole("button", { name: RETRY }));

  expect(await findArrow("Air temperature")).toBeInTheDocument();
});

test("should move the focus to the board when the retry button leaves", async () => {
  serveLive(inTurn(failure, hang));
  renderInApp();
  await userEvent.click(await screen.findByRole("button", { name: RETRY }));

  expect(screen.getByTestId("slot-board")).toHaveFocus();
});

test("should show the bundled board of a demo case with the live board off", async () => {
  flags.isLiveBoardOn = false;
  serveBundle();
  confirmBundledSeoulSnow();
  renderInApp();

  expect(await findArrow("Air temperature")).toBeInTheDocument();
});

test("should send no live request for a demo case with the live board off", async () => {
  flags.isLiveBoardOn = false;
  const calls = serveBundle();
  confirmBundledSeoulSnow();
  renderInApp();
  await findLoadedBoard();

  expect(calls.filter((call) => !call.url.startsWith("/demo/"))).toEqual([]);
});

test.each([
  { what: "the unavailable state", element: () => screen.getByText(LIVE_OFF) },
  { what: "the slot test ID", element: () => screen.getByTestId("slot-board") },
])("should show $what for a live case with the live board off", ({ element }) => {
  flags.isLiveBoardOn = false;
  serveLive();
  renderInApp();

  expect(element()).toBeInTheDocument();
});

test("should ask for no board for a live case with the live board off", () => {
  flags.isLiveBoardOn = false;
  const calls = serveLive();
  renderInApp();

  expect(calls.some((call) => call.url.includes("/caseboard"))).toBe(false);
});

test("should give every control of the board an accessible name", async () => {
  serveLive();
  renderInApp();
  await findLoadedBoard();
  await openArrow("Air temperature");

  expect([
    ...screen.queryAllByRole("button", { name: "" }),
    ...screen.queryAllByRole("link", { name: "" }),
  ]).toEqual([]);
});

test("should light the arrows up", async () => {
  serveLive();
  renderInApp();

  expect((await findArrow("Water vapour")).className).toContain("animate-in");
});

test("should not animate the arrows with reduced motion", async () => {
  reduceMotion();
  serveLive();
  renderInApp();

  expect((await findArrow("Water vapour")).className).not.toContain("animate-in");
});

test("should never say that a link was caused by the trend", async () => {
  serveLive();
  renderInApp();
  await openArrow("Air temperature");

  expect(screen.getByTestId("slot-board")).not.toHaveTextContent(/caused by/i);
});
