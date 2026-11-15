/**
 * The contract of the one client store (DES-001). Types only. Frozen from wave 2:
 * report a needed change.
 *
 * The store uses camelCase. The API records inside it (the proposal, the draft
 * spec, the window) keep their snake_case fields and are not mapped.
 */
import type {
  DraftSpec,
  Lang,
  ParseProposal,
  RequestMeta,
  RequestWindow,
  ResultKind,
  Units,
} from "@/contracts/types";

/** Who made a change. The confirm gate reads it (DES-002). */
export type Source = "user" | "guide" | "demo";
/** `fixture` answers only from the bundled demo files (DES-003). */
export type FetchSource = "live" | "fixture";
/** Null until the user picks a door on the first screen. */
export type Mode = null | "guided" | "explore" | "demo";
export type PanelKind = ResultKind;
export type Step = 1 | 2 | 3 | 4;
/** The verdict card stays hidden until the chart tap is answered or skipped (FR-10). */
export type VerdictGate = "pending" | "revealed";

export interface Point {
  lat: number;
  lon: number;
}

export interface MapView {
  center: Point;
  zoom: number;
  bounds: [west: number, south: number, east: number, north: number];
}

export interface MapTarget {
  center: Point;
  /** Null keeps the zoom that the map has. */
  zoom: number | null;
}

/** The cells that the map draws before a run. The result of the service is authoritative. */
export interface CellPreview {
  cells: [latIndex: number, lonIndex: number][];
  count: number;
  usedContainingCell: boolean;
}

export interface DemoState {
  caseId: string;
  stepIndex: number;
  isPaused: boolean;
}

export interface AppState {
  lang: Lang;
  units: Units;
  mode: Mode;
  step: Step;
  question: string;
  proposal: ParseProposal | null;
  draftSpec: DraftSpec | null;
  /** Null means not confirmed. No analysis request leaves without it (FR-03). */
  confirmedSpec: DraftSpec | null;
  /** With no pin, a request sends the bounds of the map view as its area (FR-09). */
  area: { pin: Point | null; radiusKm: number };
  window: RequestWindow;
  mapView: MapView | null;
  mapTarget: MapTarget | null;
  cellPreview: CellPreview | null;
  openPanels: PanelKind[];
  verdictGate: VerdictGate;
  /** Random for each tab. It names no person. */
  sessionId: string;
  fetchSource: FetchSource;
  demo: DemoState | null;
  meta: Record<PanelKind, RequestMeta | null>;
}

/**
 * Rules of the confirm gate (DES-002, TR-F-004, TR-F-016):
 * - editDraft, setPin and setRadius clear the confirmation for every source.
 * - setWindow keeps the confirmation for the source "user", and each open panel
 *   then asks for its result again. For "guide" and "demo" it clears it.
 * - runAtPoint sets the pin and confirms in one step. An Explore click and a
 *   click on a nearby pin count as confirmation (working value under Q-016).
 */
export interface Actions {
  chooseDoor(mode: Exclude<Mode, null>): void;
  goToStep(step: Step): void;
  back(): void;
  skipToExplore(): void;
  setQuestion(text: string): void;
  setProposal(proposal: ParseProposal | null): void;
  /** A member of the patch replaces the stored member whole. */
  editDraft(patch: Partial<DraftSpec>, source: Source): void;
  confirmSpec(): void;
  setPin(point: Point | null, source: Source): void;
  setRadius(km: number, source: Source): void;
  setWindow(window: RequestWindow, source: Source): void;
  runAtPoint(point: Point): void;
  setMapView(view: MapView | null): void;
  setMapTarget(target: MapTarget | null): void;
  setCellPreview(preview: CellPreview | null): void;
  openPanel(kind: PanelKind): void;
  closePanel(kind: PanelKind): void;
  revealVerdict(): void;
  setLang(lang: Lang): void;
  setUnits(units: Units): void;
  setFetchSource(source: FetchSource): void;
  startDemo(caseId: string): void;
  setDemoStep(index: number): void;
  pauseDemo(isPaused: boolean): void;
  endDemo(): void;
  setRequestMeta(kind: PanelKind, meta: RequestMeta | null): void;
}

/** The query hooks of web/src/hooks, by name. */
export type HookName =
  | "useCatalog"
  | "useParse"
  | "useTrend"
  | "useCaseBoard"
  | "useScan";

/** The four browser performance marks (TR-F-009, TR-Q-009). */
export type PerfMark =
  | "skip-activated"
  | "map-interactive"
  | "analysis-started"
  | "first-chart-rendered";
