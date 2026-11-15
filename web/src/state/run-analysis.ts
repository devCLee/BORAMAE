/**
 * The confirm gate (DES-002, FR-03). This is the only module that calls the
 * analysis paths, and no request leaves it for a spec that the user did not
 * confirm (TR-F-004).
 */
import type { Area, RequestMeta, RequestSpec } from "@/contracts/types";
import {
  type Answer,
  fetchAnalysis,
  FetchError,
  type ResultByKind,
} from "@/lib/fetch-layer";
import { MARK_ANALYSIS_STARTED, markPerf } from "@/lib/perf";
import { encodeSpec } from "@/lib/spec-codec";

import { actions, getState } from "./store";
import type { AppState, PanelKind } from "./types";

export type AnalysisOutcome<K extends PanelKind> =
  | { status: "done"; body: ResultByKind[K]; meta: RequestMeta }
  | { status: "failed"; error: FetchError }
  /** Nothing was sent: no spec is confirmed, or no area exists yet. */
  | { status: "refused" };

/**
 * Opens the panel of the kind and asks for its result. Feature code calls this
 * function and nothing below it. It never rejects, so a caller that only starts
 * the analysis needs no catch. A panel reads the result through its query hook.
 */
export async function runAnalysis<K extends PanelKind>(
  kind: K,
): Promise<AnalysisOutcome<K>> {
  const s = encodeRequest(getState(), kind);
  if (s === null) {
    return { status: "refused" };
  }
  actions.openPanel(kind);
  try {
    return { status: "done", ...(await sendAnalysis(kind, s)) };
  } catch (error) {
    return { status: "failed", error: toFetchError(error) };
  }
}

/**
 * The gate: the request of a panel in its encoded form, or null while the app
 * must not send it. The area is the pinned circle, or the map view when no place
 * is pinned (FR-09).
 */
export function encodeRequest(state: AppState, kind: PanelKind): string | null {
  const { confirmedSpec, window } = state;
  const area = toArea(state);
  if (confirmedSpec === null || area === null) {
    return null;
  }
  const spec: RequestSpec = {
    v: 1,
    kind,
    var: confirmedSpec.var,
    metric: confirmedSpec.metric,
    area,
    window,
  };
  return encodeSpec(spec);
}

/**
 * For the query hooks of web/src/hooks only: sends the request s of a panel and
 * rejects with a FetchError. It sends s only while s is the confirmed request,
 * so a query cannot store the answer of one request under the key of another.
 */
export async function sendAnalysis<K extends PanelKind>(
  kind: K,
  s: string,
): Promise<Answer<ResultByKind[K]>> {
  const state = getState();
  if (s !== encodeRequest(state, kind)) {
    throw new FetchError("server", "not the confirmed request");
  }
  markPerf(MARK_ANALYSIS_STARTED);
  return fetchAnalysis(state.fetchSource, kind, s);
}

function toArea({ area, mapView }: AppState): Area | null {
  if (area.pin !== null) {
    return { lat: area.pin.lat, lon: area.pin.lon, radius_km: area.radiusKm };
  }
  if (mapView === null) {
    return null;
  }
  const [west, south, east, north] = mapView.bounds;
  return { west, south, east, north };
}

function toFetchError(error: unknown): FetchError {
  return error instanceof FetchError
    ? error
    : new FetchError("server", String(error));
}
