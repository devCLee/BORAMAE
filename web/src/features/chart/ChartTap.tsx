"use client";

import { useTranslations } from "next-intl";
import { useId } from "react";

import { Button } from "@/components/ui/button";

const ANSWERS = ["yes", "no", "skip"] as const;

interface ChartTapProps {
  /** Every answer, skip included, opens the verdict gate. */
  onAnswer: () => void;
}

/**
 * The optional tap before the verdict (FR-10). The answer is not kept and not sent:
 * the app sends and stores nothing (TDD "Chart", Q-022).
 */
export function ChartTap({ onAnswer }: ChartTapProps) {
  const t = useTranslations("chart");
  const questionId = useId();

  return (
    <div
      role="group"
      aria-labelledby={questionId}
      className="flex flex-wrap items-center gap-2"
    >
      <p id={questionId} className="text-sm font-medium">
        {t("tap.question")}
      </p>
      {ANSWERS.map((answer) => (
        <Button
          key={answer}
          variant={answer === "skip" ? "ghost" : "outline"}
          className="min-h-11"
          onClick={onAnswer}
        >
          {t(`tap.${answer}`)}
        </Button>
      ))}
    </div>
  );
}
