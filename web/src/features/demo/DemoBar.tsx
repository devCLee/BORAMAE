"use client";

import { useLocale } from "next-intl";
import { useEffect } from "react";

import type { Lang } from "@/contracts/types";
import { actions, getState, useAppStore } from "@/state/store";

import { CaseList } from "./CaseList";
import { findScript, verdictIndexOf } from "./demo-content";
import { DemoPlayer } from "./DemoPlayer";
import { startCase } from "./play-step";

// ponytail: the judge link is /{locale}/?demo=<case_id>&at=result, a product choice
// under TDD Q-012 that the owner has not confirmed.
const CASE_PARAM = "demo";
const AT_PARAM = "at";
const AT_RESULT = "result";

/**
 * The demo slot (DES-020, FR-06): the case list behind the demo door, the player
 * while a case runs, and the judge link that opens a case at its verdict step.
 */
export function DemoBar() {
  const locale = useLocale() as Lang;
  const mode = useAppStore((state) => state.mode);
  const caseId = useAppStore((state) => state.demo?.caseId ?? null);
  const script = caseId === null ? undefined : findScript(caseId);

  useEffect(() => {
    // Read from window.location: useSearchParams needs a Suspense boundary in a static export.
    const query = new URLSearchParams(window.location.search);
    const linked = findScript(query.get(CASE_PARAM) ?? "");
    if (linked === undefined || query.get(AT_PARAM) !== AT_RESULT || getState().demo !== null) {
      return;
    }
    startCase(linked.case_id);
    // The path already holds the language (FR-01), so the link keeps it and skips the choice.
    actions.setLang(locale);
    actions.setDemoStep(verdictIndexOf(linked));
  }, [locale]);

  return (
    <div data-testid="slot-demo">
      {script !== undefined ? (
        <DemoPlayer key={script.case_id} script={script} />
      ) : (
        mode === "demo" && <CaseList />
      )}
    </div>
  );
}
