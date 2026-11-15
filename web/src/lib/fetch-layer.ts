/**
 * The one module that sends every request (DES-003). It owns the client
 * timeouts, the retry rule and the typed errors that a view turns into an empty
 * state. fetch-layer-request.ts holds its transport.
 *
 * The source "live" asks the service. The source "fixture" answers only from
 * the bundled demo files under /demo/, and it rejects every request that the
 * demo manifest does not hold, so a demo never shows a result under another
 * request.
 */
import { API_BASE } from "@/config/flags";
import { TIMEOUT_MS } from "@/config/timeouts";
import {
  type CaseBoard,
  type Catalog,
  type DemoManifest,
  HEADER_BYTES_FETCHED,
  HEADER_CACHE,
  HEADER_CONTAINING_CELL,
  HEADER_REQUEST_ID,
  HEADER_RESULT_KEY,
  HEADER_SERVER_TIMING,
  type ParseProposal,
  type ParseRequest,
  type RequestMeta,
  type ResultKind,
  type ScanResult,
  type TrendResult,
} from "@/contracts/types";
import type { FetchSource } from "@/state/types";

import { FetchError, request } from "./fetch-layer-request";

export { FetchError, type FetchErrorCode } from "./fetch-layer-request";

export interface ResultByKind {
  trend: TrendResult;
  caseboard: CaseBoard;
  scan: ScanResult;
}

/** A result with the facts of the request that brought it. */
export interface Answer<T> {
  body: T;
  meta: RequestMeta;
}

const DEMO_BASE = "/demo/";
const MANIFEST_FILE = "manifest.json";

let manifestRequest: Promise<DemoManifest> | null = null;
let parseController: AbortController | null = null;
const analysesInFlight = new Map<string, Promise<Answer<unknown>>>();

export async function fetchCatalog(source: FetchSource): Promise<Catalog> {
  if (source === "fixture") {
    return fetchBundledCatalog();
  }
  try {
    const reply = await request<Catalog>(`${API_BASE}/meta/catalog.json`, {
      timeoutMs: TIMEOUT_MS.meta,
      canRetry: false,
    });
    return reply.body;
  } catch (liveError) {
    // With the service down, the app shell and both demos still load from the
    // bundle (TDD "Reliability and recovery"). The bundle is the retry.
    return fetchBundledCatalog().catch(() => {
      throw liveError;
    });
  }
}

/**
 * Sends a question to parse. A new call aborts the one before it, and the
 * aborted call rejects with an AbortError, not with a FetchError. The fixture
 * source needs the running demo case, because a parse request names no case.
 */
export async function fetchParse(
  source: FetchSource,
  parseRequest: ParseRequest,
  demoCaseId: string | null = null,
): Promise<ParseProposal> {
  parseController?.abort();
  parseController = new AbortController();
  if (source === "fixture") {
    const manifest = await fetchManifest();
    const demoCase = manifest.cases.find(
      (candidate) => candidate.case_id === demoCaseId,
    );
    if (demoCase === undefined) {
      throw new FetchError("not_in_offline_demo");
    }
    return fetchDemoFile(demoCase.parse[parseRequest.lang]);
  }
  const reply = await request<ParseProposal>(`${API_BASE}/api/v1/parse`, {
    timeoutMs: TIMEOUT_MS.parse,
    controller: parseController,
    init: {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parseRequest),
    },
  });
  return reply.body;
}

/**
 * Asks an analysis path with the encoded request spec. Only
 * state/run-analysis.ts calls this function (DES-002). Equal requests in flight
 * share one HTTP request.
 */
export function fetchAnalysis<K extends ResultKind>(
  source: FetchSource,
  kind: K,
  s: string,
): Promise<Answer<ResultByKind[K]>> {
  const id = `${source}:${kind}:${s}`;
  const inFlight = analysesInFlight.get(id);
  if (inFlight !== undefined) {
    // The ID names the kind, so the answer in flight has the result type of K.
    return inFlight as Promise<Answer<ResultByKind[K]>>;
  }
  const analysis: Promise<Answer<ResultByKind[K]>> = loadAnalysis(
    source,
    kind,
    s,
  ).finally(() => {
    // A newer request can hold the ID by now, after a reset in a test.
    if (analysesInFlight.get(id) === analysis) {
      analysesInFlight.delete(id);
    }
  });
  analysesInFlight.set(id, analysis);
  return analysis;
}

/** Reads a stored result by its key: GET /r/{kind}/{key}.json, or its bundled file. */
export async function fetchResult<K extends ResultKind>(
  source: FetchSource,
  kind: K,
  key: string,
): Promise<Answer<ResultByKind[K]>> {
  if (source === "fixture") {
    const file = findBundledResult(await fetchManifest(), kind, key);
    if (file === undefined) {
      throw new FetchError("not_in_offline_demo");
    }
    return fetchBundledResult(file, key);
  }
  const { body, headers } = await request<ResultByKind[K]>(
    `${API_BASE}/r/${kind}/${key}.json`,
    { timeoutMs: TIMEOUT_MS.stored },
  );
  return { body, meta: toMeta(kind, headers, key) };
}

/** The demo manifest. It loads one time, and a failed load is tried again. */
export function fetchManifest(): Promise<DemoManifest> {
  manifestRequest ??= fetchDemoFile<DemoManifest>(MANIFEST_FILE).catch(
    (error: unknown) => {
      manifestRequest = null;
      throw error;
    },
  );
  return manifestRequest;
}

/** Reads a bundled file by the path that the manifest gives for it. */
export async function fetchDemoFile<T>(file: string): Promise<T> {
  const reply = await request<T>(DEMO_BASE + file, {
    timeoutMs: TIMEOUT_MS.stored,
  });
  return reply.body;
}

/** For tests: forgets the manifest, the parse and the analyses in flight. */
export function resetFetchLayer(): void {
  manifestRequest = null;
  parseController = null;
  analysesInFlight.clear();
}

async function fetchBundledCatalog(): Promise<Catalog> {
  const manifest = await fetchManifest();
  return fetchDemoFile(manifest.catalog);
}

async function loadAnalysis<K extends ResultKind>(
  source: FetchSource,
  kind: K,
  s: string,
): Promise<Answer<ResultByKind[K]>> {
  if (source === "fixture") {
    const manifest = await fetchManifest();
    const entry = manifest.cases
      .map((demoCase) => demoCase.kinds[kind])
      .find((candidate) => candidate?.s === s);
    if (entry === undefined) {
      throw new FetchError("not_in_offline_demo");
    }
    return fetchBundledResult(entry.file, entry.key);
  }
  const { body, headers } = await request<ResultByKind[K]>(
    `${API_BASE}/api/v1/${kind}?s=${s}`,
    { timeoutMs: TIMEOUT_MS.analysis },
  );
  return { body, meta: toMeta(kind, headers, null) };
}

/** The file of a result key: an entry of kinds, or a file listed by key only. */
function findBundledResult(
  manifest: DemoManifest,
  kind: ResultKind,
  key: string,
): string | undefined {
  return manifest.cases
    .map((demoCase) =>
      demoCase.kinds[kind]?.key === key
        ? demoCase.kinds[kind].file
        : demoCase.referenced[kind]?.[key],
    )
    .find((file) => file !== undefined);
}

async function fetchBundledResult<T>(
  file: string,
  resultKey: string,
): Promise<Answer<T>> {
  const body = await fetchDemoFile<T>(file);
  const meta: RequestMeta = {
    resultKey,
    requestId: null,
    cache: null,
    bytesFetched: null,
    serverTiming: null,
    // ponytail: the manifest holds no containing-cell fact, so a bundled result
    // reads false. The map preview still shows the notice. Add the fact to
    // ManifestFile if the drawer of a demo must show it.
    usedContainingCell: false,
    sourceUrl: DEMO_BASE + file,
  };
  return { body, meta };
}

function toMeta(
  kind: ResultKind,
  headers: Headers,
  knownKey: string | null,
): RequestMeta {
  const resultKey = headers.get(HEADER_RESULT_KEY) ?? knownKey;
  if (resultKey === null) {
    throw new FetchError("server", `no ${HEADER_RESULT_KEY} header`);
  }
  const cache = headers.get(HEADER_CACHE);
  const bytesFetched = headers.get(HEADER_BYTES_FETCHED);
  return {
    resultKey,
    requestId: headers.get(HEADER_REQUEST_ID),
    cache: cache === "hit" || cache === "miss" ? cache : null,
    bytesFetched: bytesFetched === null ? null : Number(bytesFetched),
    serverTiming: headers.get(HEADER_SERVER_TIMING),
    usedContainingCell: headers.get(HEADER_CONTAINING_CELL) === "true",
    sourceUrl: `/r/${kind}/${resultKey}.json`,
  };
}
