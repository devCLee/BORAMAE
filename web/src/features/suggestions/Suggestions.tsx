"use client";

import { useTranslations } from "next-intl";
import { useId, useRef } from "react";

import { Button } from "@/components/ui/button";
import type { Outcome } from "@/features/verdict/outcome";
import { actions, useAppStore } from "@/state/store";
import type { Step } from "@/state/types";

type ActionId = "open_board" | "try_nearby" | "widen_window" | "pick_variable";

/**
 * The rule-based next actions of each outcome (TDD "rule-based suggestions"): a static
 * table that needs no model, so it also stands in for the guide when the chat is hidden.
 * ponytail: the rows and their order are working values (the TDD gives examples only).
 * "Nearby" and "another variable" go back to the rail steps and keep the mode, so in
 * Explore mode they change only the step; switch the door here if Explore needs more.
 */
const NEXT_ACTIONS: Record<Outcome, ActionId[]> = {
  significant_rise: ["open_board", "try_nearby", "pick_variable"],
  significant_fall: ["open_board", "try_nearby", "pick_variable"],
  not_yet: ["widen_window", "try_nearby", "pick_variable"],
  no_trend: ["try_nearby", "pick_variable", "widen_window"],
  record_too_short: ["widen_window", "pick_variable"],
  no_data: ["try_nearby", "pick_variable"],
};

// The rail steps of PRD "User flows": 2 picks the variables and 3 the place.
const VARIABLE_STEP: Step = 2;
const PLACE_STEP: Step = 3;

interface SuggestionsProps {
  outcome: Outcome;
  /** The first year of the record of the variable: the start of the widest window. */
  recordStartYear: number;
}

export function Suggestions({ outcome, recordStartYear }: SuggestionsProps) {
  const t = useTranslations("suggestions");
  const titleId = useId();
  const titleRef = useRef<HTMLHeadingElement>(null);
  const timeWindow = useAppStore((state) => state.window);
  const isFullRecord =
    timeWindow.start <= recordStartYear && timeWindow.end === "latest";
  const run: Record<ActionId, () => void> = {
    open_board: () => actions.openPanel("caseboard"),
    try_nearby: () => actions.goToStep(PLACE_STEP),
    pick_variable: () => actions.goToStep(VARIABLE_STEP),
    widen_window: () => {
      actions.setWindow({ start: recordStartYear, end: "latest" }, "user");
      // The button leaves with the narrow window, so the focus stays in the list.
      titleRef.current?.focus();
    },
  };
  const shown = NEXT_ACTIONS[outcome].filter(
    (id) => id !== "widen_window" || !isFullRecord,
  );

  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-2">
      <h3 id={titleId} ref={titleRef} tabIndex={-1} className="text-sm font-medium">
        {t("title")}
      </h3>
      <ul className="flex flex-wrap gap-2">
        {shown.map((id) => (
          <li key={id}>
            <Button variant="outline" className="min-h-11" onClick={run[id]}>
              {t(`actions.${id}`)}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
