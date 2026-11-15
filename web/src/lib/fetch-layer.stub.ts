/**
 * A stand-in for fetch in tests. fetch is the network boundary of the app, and
 * no test mocks anything nearer than it. The stub records every request, and it
 * rejects an aborted request with the reason of the abort, as fetch does.
 */
import { vi } from "vitest";

import { resetFetchLayer } from "./fetch-layer";

export interface StubCall {
  url: string;
  method: string;
  /** The parsed JSON body of a POST. Undefined for a GET. */
  body: unknown;
  signal: AbortSignal | null;
}

export type Respond = (call: StubCall) => Response | Promise<Response>;

/**
 * Replaces fetch until vi.unstubAllGlobals() and returns the list of requests.
 * A new stub is a new network, so the fetch layer forgets what the old one said.
 */
export function stubFetch(respond: Respond): StubCall[] {
  resetFetchLayer();
  const calls: StubCall[] = [];
  vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
    const call: StubCall = {
      url: String(input),
      method: init?.method ?? "GET",
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      signal: init?.signal ?? null,
    };
    calls.push(call);
    return new Promise<Response>((resolve, reject) => {
      call.signal?.addEventListener("abort", () => reject(call.signal?.reason));
      Promise.resolve(call).then(respond).then(resolve, reject);
    });
  });
  return calls;
}

export function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), init);
}

/** An RFC 9457 error answer of the service. */
export function problemResponse(status: number, code: string): Response {
  return jsonResponse(
    { type: "about:blank", title: code, status, code },
    { status, headers: { "Content-Type": "application/problem+json" } },
  );
}

/** A request that never gets an answer. */
export function hang(): Promise<Response> {
  return new Promise(() => {});
}

/** Serves each URL of the table as JSON and answers 404 for every other URL. */
export function serve(files: Record<string, unknown>): Respond {
  return ({ url }) =>
    url in files ? jsonResponse(files[url]) : problemResponse(404, "not_found");
}

/** Answers the nth request with the nth responder. The last one answers every later request. */
export function inTurn(...responders: Respond[]): Respond {
  let turn = 0;
  return (call) => {
    const respond = responders[Math.min(turn, responders.length - 1)];
    turn += 1;
    return respond(call);
  };
}
