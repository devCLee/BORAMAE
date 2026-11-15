import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Providers } from "@/components/shell/Providers";
import { API_BASE } from "@/config/flags";
import {
  hang,
  inTurn,
  jsonResponse,
  problemResponse,
  serve,
  stubFetch,
} from "@/lib/fetch-layer.stub";
import { actions, getState, resetStore } from "@/state/store";
import { manifest, parseInput1En, parseInput1Ko } from "@/test/fixtures";

import { useParse } from "./queries";

const QUESTION = "서울 첫눈이 늦어지고 있나요?";
const CASE = manifest.cases[0];

function renderParse() {
  return renderHook(() => useParse(), { wrapper: Providers });
}

beforeEach(() => {
  resetStore();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("should send the question with the language and the session ID of the store", async () => {
  const calls = stubFetch(() => jsonResponse(parseInput1Ko));
  actions.setLang("ko");
  const { result } = renderParse();

  act(() => result.current.mutate(QUESTION));

  await waitFor(() =>
    expect(calls).toMatchObject([
      {
        url: `${API_BASE}/api/v1/parse`,
        body: {
          text: QUESTION,
          lang: "ko",
          session_id: getState().sessionId,
        },
      },
    ]),
  );
});

test("should give the proposal of the answer", async () => {
  stubFetch(() => jsonResponse(parseInput1Ko));
  const { result } = renderParse();

  act(() => result.current.mutate(QUESTION));

  await waitFor(() => expect(result.current.data).toEqual(parseInput1Ko));
});

test("should give the proposal of the later question when a second one follows", async () => {
  stubFetch(inTurn(hang, () => jsonResponse(parseInput1En)));
  const { result } = renderParse();

  act(() => result.current.mutate(QUESTION));
  act(() => result.current.mutate("Is the first snow in Seoul coming later?"));

  await waitFor(() => expect(result.current.data).toEqual(parseInput1En));
});

test("should give the typed error of a failed parse", async () => {
  stubFetch(() => problemResponse(400, "text_too_long"));
  const { result } = renderParse();

  act(() => result.current.mutate(QUESTION));

  await waitFor(() => expect(result.current.error?.code).toBe("server"));
});

test("should answer from the parse file of the running demo case", async () => {
  stubFetch(
    serve({
      "/demo/manifest.json": manifest,
      [`/demo/${CASE.parse.ko}`]: parseInput1Ko,
    }),
  );
  actions.startDemo(CASE.case_id);
  actions.setLang("ko");
  const { result } = renderParse();

  act(() => result.current.mutate(QUESTION));

  await waitFor(() => expect(result.current.data).toEqual(parseInput1Ko));
});
