"use client";

import { cn } from "cn";
import {
  CalendarX2Icon,
  HourglassIcon,
  MinusIcon,
  TrendingDownIcon,
  TrendingUpIcon,
  type LucideIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";

import type { NoVerdictReason, Verdict } from "@/contracts/types";

/** The four verdicts, and record too short, whose card withholds the verdict (FR-14). */
export type ChipVerdict = Verdict | Extract<NoVerdictReason, "record_too_short">;

// Color is never the only signal: each state also has its own icon and word.
// ponytail: the icons, the fall wording and every Korean word are working values that
// wait for the user's verdict wording review (FR-13). The words live in glossary.verdicts.
const CHIP_STYLES: Record<ChipVerdict, { icon: LucideIcon; role: string }> = {
  significant_rise: { icon: TrendingUpIcon, role: "text-trend-rise" },
  significant_fall: { icon: TrendingDownIcon, role: "text-trend-fall" },
  not_yet: { icon: HourglassIcon, role: "text-not-yet" },
  no_trend: { icon: MinusIcon, role: "text-no-trend" },
  record_too_short: { icon: CalendarX2Icon, role: "text-too-short" },
};

export function VerdictChip({ verdict }: { verdict: ChipVerdict }) {
  const t = useTranslations("glossary");
  const { icon: Icon, role } = CHIP_STYLES[verdict];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-current px-2.5 py-0.5 text-sm font-medium",
        role,
      )}
    >
      <Icon aria-hidden className="size-4" />
      {t(`verdicts.${verdict}`)}
    </span>
  );
}
