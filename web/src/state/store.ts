"use client";

/**
 * The one client store (DES-001), behind the frozen interface of ./types.
 * It lives at module level, so the demo state and the fetch source survive a
 * locale route change. It sends no request: state/run-analysis.ts and the query
 * hooks read it and send.
 */
import { useSyncExternalStore } from "react";

import { readStoredLanguage } from "@/components/shell/language-choice";
import type { DraftSpec, Lang } from "@/contracts/types";
import { routing } from "@/i18n/routing";
import { MARK_SKIP_ACTIVATED, markPerf } from "@/lib/perf";
import { readSessionId } from "@/lib/storage";

import type { Actions, AppState, Step } from "./types";

// PRD "User flows" (Defaults): the full record from 1981, and a radius of 25 km.
const RECORD_START_YEAR = 1981;
const DEFAULT_RADIUS_KM = 25;
const FIRST_STEP: Step = 1;
/** Back on the first step returns to the three doors. */
const STEP_BEFORE: Record<Step, Step | null> = { 1: null, 2: 1, 3: 2, 4: 3 };
// ponytail: a map click with no draft tests T2M annual mean. TRD Q-41 lists no
// Explore defaults, and this one is the working value of the build plan.
const EXPLORE_DRAFT: DraftSpec = { var: "T2M", metric: { id: "annual_mean" } };

/**
 * What a cleared confirmation takes with it (DES-002). No panel stays open on an
 * unconfirmed spec, so a panel of the old spec cannot ask for the next one.
 */
const UNCONFIRMED = {
  confirmedSpec: null,
  openPanels: [],
  verdictGate: "pending",
  meta: { trend: null, caseboard: null, scan: null },
} satisfies Partial<AppState>;

const NEW_INVESTIGATION = {
  ...UNCONFIRMED,
  step: FIRST_STEP,
  question: "",
  proposal: null,
  draftSpec: null,
  area: { pin: null, radiusKm: DEFAULT_RADIUS_KM },
  window: { start: RECORD_START_YEAR, end: "latest" },
} satisfies Partial<AppState>;

/** What the static build renders. It has no browser storage to read. */
const SERVER_STATE = createState(routing.defaultLocale, "");

let state = createBrowserState();
const listeners = new Set<() => void>();

export function getState(): AppState {
  return state;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Renders a component again when the selected member changes. Select one member
 * or a primitive. A selector that builds a new object or array on each call
 * renders forever.
 */
export function useAppStore<T>(selector: (state: AppState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(state),
    () => selector(SERVER_STATE),
  );
}

/** For tests: the state of a new page load in the same tab. */
export function resetStore(): void {
  set(createBrowserState());
}

export const actions: Actions = {
  chooseDoor: (mode) => set({ mode, step: FIRST_STEP }),
  goToStep: (step) => set({ step }),
  back: () => {
    const step = STEP_BEFORE[state.step];
    set(step === null ? { mode: null } : { step });
  },
  skipToExplore: () => {
    markPerf(MARK_SKIP_ACTIVATED);
    set({ mode: "explore" });
  },
  setQuestion: (question) => set({ question }),
  setProposal: (proposal) => set({ proposal }),
  editDraft: (patch) => {
    const { var: variable, metric } = { ...state.draftSpec, ...patch };
    const isWhole = variable !== undefined && metric !== undefined;
    set({
      ...UNCONFIRMED,
      draftSpec: isWhole ? { var: variable, metric } : null,
    });
  },
  confirmSpec: () => set({ confirmedSpec: state.draftSpec }),
  setPin: (pin) => set({ ...UNCONFIRMED, area: { ...state.area, pin } }),
  setRadius: (radiusKm) =>
    set({ ...UNCONFIRMED, area: { ...state.area, radiusKm } }),
  setWindow: (window, source) =>
    set(source === "user" ? { window } : { ...UNCONFIRMED, window }),
  runAtPoint: (pin) => {
    const draftSpec = state.draftSpec ?? EXPLORE_DRAFT;
    set({
      ...UNCONFIRMED,
      area: { ...state.area, pin },
      draftSpec,
      confirmedSpec: draftSpec,
      openPanels: ["trend"],
    });
  },
  setMapView: (mapView) => set({ mapView }),
  setMapTarget: (mapTarget) => set({ mapTarget }),
  setCellPreview: (cellPreview) => set({ cellPreview }),
  openPanel: (kind) => {
    if (!state.openPanels.includes(kind)) {
      set({ openPanels: [...state.openPanels, kind] });
    }
  },
  closePanel: (kind) =>
    set({
      openPanels: state.openPanels.filter((open) => open !== kind),
      meta: { ...state.meta, [kind]: null },
    }),
  revealVerdict: () => set({ verdictGate: "revealed" }),
  setLang: (lang) => set({ lang }),
  setUnits: (units) => set({ units }),
  setFetchSource: (fetchSource) => {
    // A spec that one source confirmed must not send a request to the other one.
    if (fetchSource !== state.fetchSource) {
      set({ ...UNCONFIRMED, fetchSource });
    }
  },
  startDemo: (caseId) =>
    set({
      ...NEW_INVESTIGATION,
      mode: "demo",
      fetchSource: "fixture",
      demo: { caseId, stepIndex: 0, isPaused: false },
    }),
  setDemoStep: (stepIndex) => {
    if (state.demo !== null) {
      set({ demo: { ...state.demo, stepIndex } });
    }
  },
  pauseDemo: (isPaused) => {
    if (state.demo !== null) {
      set({ demo: { ...state.demo, isPaused } });
    }
  },
  endDemo: () => set({ ...NEW_INVESTIGATION, fetchSource: "live", demo: null }),
  setRequestMeta: (kind, meta) => {
    // The hooks of one panel all report the same facts. Only a change is news.
    if (state.meta[kind] !== meta) {
      set({ meta: { ...state.meta, [kind]: meta } });
    }
  },
};

function createState(lang: Lang, sessionId: string): AppState {
  return {
    ...NEW_INVESTIGATION,
    lang,
    units: "metric",
    mode: null,
    mapView: null,
    mapTarget: null,
    cellPreview: null,
    sessionId,
    fetchSource: "live",
    demo: null,
  };
}

function createBrowserState(): AppState {
  return createState(
    readStoredLanguage() ?? routing.defaultLocale,
    readSessionId(),
  );
}

function set(patch: Partial<AppState>): void {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}
