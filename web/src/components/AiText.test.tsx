import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { closeProvenance } from "@/features/provenance/provenance-state";
import { hang, problemResponse, stubFetch } from "@/lib/fetch-layer.stub";
import { resetStore } from "@/state/store";
import { trendSignificant } from "@/test/fixtures";

import {
  BADGE,
  CHECKING,
  INTERVAL,
  INVENTED,
  KO_WITHHELD,
  RATE,
  renderAiText,
  serveFiles,
  TREND_URL,
  WITHHELD,
} from "./AiText.test-kit";

const RATE_BUTTON = "Source of 3.3";
const NO_NUMBER = "Snow cover comes from a model, not from stations.";

beforeEach(() => {
  resetStore();
  closeProvenance();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should show a kept sentence after the check", async () => {
  serveFiles();
  const { container } = renderAiText();
  await screen.findAllByText(BADGE);

  expect(container).toHaveTextContent(RATE);
});

test("should not show the sentence with an unmatched number", async () => {
  serveFiles();
  const { container } = renderAiText();
  await screen.findAllByText(BADGE);

  expect(container).not.toHaveTextContent(INVENTED);
});

test("should badge each kept sentence", async () => {
  serveFiles();
  renderAiText();

  expect(await screen.findAllByText(BADGE)).toHaveLength(2);
});

test("should say that it checks the numbers while a result loads", async () => {
  stubFetch(({ url }) => (url === TREND_URL ? hang() : problemResponse(404, "not_found")));
  renderAiText();

  expect(await screen.findByRole("status")).toHaveTextContent(CHECKING);
});

test("should show no sentence before the check is done", async () => {
  const calls = stubFetch(({ url }) =>
    url === TREND_URL ? hang() : problemResponse(404, "not_found"),
  );
  const { container } = renderAiText();
  await waitFor(() => expect(calls.map(({ url }) => url)).toContain(TREND_URL));

  expect(container).not.toHaveTextContent(INTERVAL);
});

test("should load a result by its key when no open panel holds it", async () => {
  const calls = serveFiles();
  renderAiText();
  await screen.findAllByText(BADGE);

  expect(calls.map(({ url }) => url)).toContain(TREND_URL);
});

test("should withhold the numbers of a result that does not load", async () => {
  serveFiles({});
  renderAiText({ text: RATE });

  expect(await screen.findByText(WITHHELD)).toBeInTheDocument();
});

test("should show the withheld notice when no sentence is kept", async () => {
  serveFiles();
  renderAiText({ text: INVENTED });

  expect(await screen.findByText(WITHHELD)).toBeInTheDocument();
});

test("should show the withheld notice in Korean", async () => {
  serveFiles();
  renderAiText({ text: INVENTED }, "ko");

  expect(await screen.findByText(KO_WITHHELD)).toBeInTheDocument();
});

test("should render nothing for an empty text", async () => {
  serveFiles();
  const { container } = renderAiText({ text: "" });
  await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());

  expect(container).toHaveTextContent(/^$/);
});

test("should keep a sentence with no number", async () => {
  serveFiles({});
  const { container } = renderAiText({ text: NO_NUMBER, resultKeys: [] });
  await screen.findAllByText(BADGE);

  expect(container).toHaveTextContent(NO_NUMBER);
});

test("should name the info button of a matched number after the number", async () => {
  serveFiles();
  renderAiText();

  expect(await screen.findByRole("button", { name: RATE_BUTTON })).toBeInTheDocument();
});

test("should open the provenance of a matched number", async () => {
  serveFiles();
  renderAiText();

  await userEvent.click(await screen.findByRole("button", { name: RATE_BUTTON }));

  expect(screen.getByRole("dialog")).toHaveTextContent(trendSignificant.provenance.access_path);
});

test("should open the provenance of a matched number from the keyboard", async () => {
  serveFiles();
  renderAiText();
  (await screen.findByRole("button", { name: RATE_BUTTON })).focus();

  await userEvent.keyboard("{Enter}");

  expect(screen.getByRole("dialog")).toHaveTextContent(trendSignificant.provenance.dataset_id);
});

test("should return focus to the info button when the drawer closes", async () => {
  serveFiles();
  renderAiText();
  const infoButton = await screen.findByRole("button", { name: RATE_BUTTON });
  await userEvent.click(infoButton);

  await userEvent.click(screen.getByRole("button", { name: "Close" }));

  await waitFor(() => expect(infoButton).toHaveFocus());
});
