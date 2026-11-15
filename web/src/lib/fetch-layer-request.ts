/**
 * The transport of the fetch layer: one request with its client timeout, the
 * retry rule and the typed errors. Import from "@/lib/fetch-layer", not from
 * this file.
 */
import { RETRY_DELAYS_MS } from "@/config/timeouts";
import type { Problem } from "@/contracts/types";

/** Each code is a key of the "errors" messages, so a view shows it as an empty state. */
export type FetchErrorCode =
  | "zoom_in_or_pin"
  | "not_in_offline_demo"
  | "timeout"
  | "network"
  | "unavailable"
  | "server";

export class FetchError extends Error {
  readonly code: FetchErrorCode;

  constructor(code: FetchErrorCode, detail: string = code) {
    super(detail);
    this.name = "FetchError";
    this.code = code;
  }
}

export interface Reply<T> {
  body: T;
  headers: Headers;
}

export interface RequestOptions {
  timeoutMs: number;
  init?: RequestInit;
  /** Lets the caller abort the request, as a newer parse does. */
  controller?: AbortController;
  /** False for a request that has its own fallback. */
  canRetry?: boolean;
}

const STATUS_UNAVAILABLE = 503;
const PROBLEM_AREA_TOO_LARGE = "area_too_large";

/**
 * Sends one request under the retry rule: only an HTTP 503 answer or a network
 * error is tried again, and RETRY_DELAYS_MS holds one wait for each retry
 * (TDD Flow B).
 */
export async function request<T>(
  url: string,
  options: RequestOptions,
): Promise<Reply<T>> {
  const retryLimit = options.canRetry === false ? 0 : RETRY_DELAYS_MS.length;
  for (let retry = 0; ; retry += 1) {
    try {
      return await attempt<T>(url, options);
    } catch (error) {
      if (retry === retryLimit || !isRetryable(error)) {
        throw error;
      }
      await wait(RETRY_DELAYS_MS[retry]);
    }
  }
}

/** One try. The timeout covers the answer and the read of its body. */
async function attempt<T>(
  url: string,
  { timeoutMs, init, controller = new AbortController() }: RequestOptions,
): Promise<Reply<T>> {
  let hasTimedOut = false;
  const timer = setTimeout(() => {
    hasTimedOut = true;
    controller.abort();
  }, timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (!response.ok) {
      throw await toHttpError(response);
    }
    return { body: await response.json(), headers: response.headers };
  } catch (error) {
    if (hasTimedOut) {
      throw new FetchError("timeout", `no answer in ${timeoutMs} ms`);
    }
    // An abort by the caller is no error of the app, so it keeps its own type.
    if (controller.signal.aborted || error instanceof FetchError) {
      throw error;
    }
    throw new FetchError("network", String(error));
  } finally {
    clearTimeout(timer);
  }
}

async function toHttpError(response: Response): Promise<FetchError> {
  const problemCode = await readProblemCode(response);
  const detail = `HTTP ${response.status} ${problemCode ?? ""}`.trimEnd();
  if (response.status === STATUS_UNAVAILABLE) {
    return new FetchError("unavailable", detail);
  }
  if (problemCode === PROBLEM_AREA_TOO_LARGE) {
    return new FetchError("zoom_in_or_pin", detail);
  }
  return new FetchError("server", detail);
}

async function readProblemCode(response: Response): Promise<string | null> {
  try {
    const problem: Partial<Problem> = await response.json();
    return problem.code ?? null;
  } catch {
    // An error answer of a proxy has no problem body. Its status names the error.
    return null;
  }
}

function isRetryable(error: unknown): boolean {
  return (
    error instanceof FetchError &&
    (error.code === "unavailable" || error.code === "network")
  );
}

function wait(delayMs: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, delayMs));
}
