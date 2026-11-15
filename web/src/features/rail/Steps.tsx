"use client";

import { cn } from "cn";
import { useTranslations } from "next-intl";
import { type ComponentType, useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { actions, useAppStore } from "@/state/store";
import type { Step } from "@/state/types";

import { PlaceStep } from "./PlaceStep";
import { QuestionStep } from "./QuestionStep";
import { ReadBack } from "./ReadBack";
import { VariableStep } from "./VariableStep";
import { WindowStep } from "./WindowStep";

const STEPS: Step[] = [1, 2, 3, 4];
const STEP_BODIES: Record<Step, ComponentType> = {
  1: QuestionStep,
  2: VariableStep,
  3: PlaceStep,
  4: WindowStep,
};

/**
 * The four guided steps in order (FR-02) with Back and Skip on each, and the
 * read-back of the draft spec under them whenever it waits for Confirm.
 */
export function Steps() {
  const t = useTranslations("rail");
  const step = useAppStore((state) => state.step);
  const isGuided = useAppStore((state) => state.mode === "guided");
  const draft = useAppStore((state) => state.draftSpec);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const Body = STEP_BODIES[step];

  useEffect(() => {
    // The control that moved the step is gone, so focus lands on the new step.
    // A demo drives the steps itself and keeps the focus on its own controls.
    if (isGuided) {
      headingRef.current?.focus();
    }
  }, [step, isGuided]);

  return (
    <div className="flex flex-col gap-4">
      <ol aria-label={t("steps.label")} className="flex gap-1">
        {STEPS.map((n) => (
          <li
            key={n}
            aria-current={n === step ? "step" : undefined}
            className={cn(
              "flex-1 border-t-4 pt-1 text-xs",
              n === step ? "border-primary font-medium" : "border-muted text-muted-foreground",
            )}
          >
            {n}. {t(`steps.names.${n}`)}
          </li>
        ))}
      </ol>
      <h2 ref={headingRef} tabIndex={-1} className="text-base font-semibold">
        {t(`steps.names.${step}`)}
      </h2>
      <Body />
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" className="min-h-11" onClick={actions.back}>
          {t("back")}
        </Button>
        {step === 3 && (
          <Button className="min-h-11" onClick={() => actions.goToStep(4)}>
            {t("next")}
          </Button>
        )}
        <Button variant="ghost" className="min-h-11" onClick={actions.skipToExplore}>
          {t("skip")}
        </Button>
      </div>
      {/* ponytail: the read-back shows on every step while a draft waits for Confirm, so a
          chip or a pin change on any step reaches it; the plan places it on no one step. */}
      {draft !== null && <ReadBack draft={draft} />}
    </div>
  );
}
