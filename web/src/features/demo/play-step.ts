import type {
  Circle,
  DemoScript,
  DemoStep,
  DraftSpec,
  ParseProposal,
  RequestWindow,
} from "@/contracts/types";
import { runAnalysis } from "@/state/run-analysis";
import { actions, getState } from "@/state/store";

// ponytail: about 3 s a step plays a script of ten steps in the 30 s of the PRD demo
// script; no document fixes a step length. Change it here if captions need longer.
export const STEP_MS = 3000;
// ponytail: zoom 8 shows a 25 km circle on a laptop screen; no document gives the
// zoom of a demo pin.
const PIN_ZOOM = 8;
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

type SubmitQuestion = (question: string) => void;
type StepAction = (args: DemoStep["args"], submitQuestion: SubmitQuestion) => void;

/** The language choice and the closing card act through what the player shows. */
const NO_STORE_ACTION: StepAction = () => {};

/**
 * What a user does at each step, as the same store actions (DES-020). The args
 * are the values of content/demo/cases.json, which lint:demo checks, so the
 * request equals the bundled one.
 */
const STEP_ACTIONS: Record<DemoStep["action"], StepAction> = {
  choose_language: NO_STORE_ACTION,
  type_question: ({ text }) => actions.setQuestion(String(text)),
  submit_question: (_args, submitQuestion) => submitQuestion(getState().question),
  confirm_variables: (args) => {
    actions.editDraft(args as unknown as DraftSpec, "demo");
    actions.goToStep(3);
  },
  set_pin: (args) => {
    const { lat, lon, radius_km } = args as unknown as Circle;
    actions.setPin({ lat, lon }, "demo");
    actions.setRadius(radius_km, "demo");
    actions.setMapTarget({ center: { lat, lon }, zoom: PIN_ZOOM });
  },
  set_window: (args) => {
    actions.goToStep(4);
    actions.setWindow(args as unknown as RequestWindow, "demo");
  },
  confirm_spec: () => {
    actions.confirmSpec();
    // runAnalysis never rejects; the case panel shows its outcome.
    void runAnalysis("trend");
  },
  show_verdict: () => actions.revealVerdict(),
  open_board: () => void runAnalysis("caseboard"),
  open_fallback: () => void runAnalysis("scan"),
  closing_card: NO_STORE_ACTION,
};

/**
 * The last step whose store actions ran. It lives at module level, as the store
 * does, so the remount of a locale route change runs no step twice.
 */
let applied: { caseId: string; index: number } | null = null;

/** Starts a case at its first step. With reduced motion it waits for Play or the step control (TR-Q-013). */
export function startCase(caseId: string): void {
  applied = { caseId, index: 0 };
  actions.startDemo(caseId);
  if (window.matchMedia(REDUCED_MOTION_QUERY).matches) {
    actions.pauseDemo(true);
  }
}

/**
 * Runs the store actions of each step after the last one that ran, up to the
 * target. A jump runs the steps that it passes, so the store holds the full spec.
 */
export function catchUp(
  script: DemoScript,
  target: number,
  submitQuestion: SubmitQuestion,
): void {
  if (applied?.caseId !== script.case_id || target <= applied.index) {
    return;
  }
  const pending = script.steps.slice(applied.index + 1, target + 1);
  applied = { caseId: script.case_id, index: target };
  pending.forEach((step) => STEP_ACTIONS[step.action](step.args, submitQuestion));
}

/** Shows the cards of the proposal. One that lands after the player moved on leaves the rail where it is. */
export function applyProposal(script: DemoScript, proposal: ParseProposal): void {
  actions.setProposal(proposal);
  const index = getState().demo?.stepIndex;
  if (index !== undefined && script.steps[index]?.action === "submit_question") {
    actions.goToStep(2);
  }
}
