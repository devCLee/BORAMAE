"use client";

import { useLocale, useTranslations } from "next-intl";

import type { Catalog } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";
import { formatMonth } from "@/lib/format";
import { actions, useAppStore } from "@/state/store";

import { LabeledSlider, useDragValues } from "./LabeledSlider";

// PRD "User flows" (Defaults): the full record from 1981. FR-14: a minimum record
// of 20 years when no variable is in focus.
const RECORD_START_YEAR = 1981;
const DEFAULT_MIN_RECORD_YEARS = 20;
const YEAR_DIGITS = 4;

/**
 * The one time window of every panel (FR-09, TR-F-016). The track runs from 1981
 * to the pinned month of the catalog, and the thumbs stay inside the record of
 * the variable in focus. A release sends the window; the right end sends "latest".
 */
export function TimeSlider() {
  const catalog = useCatalog().data;

  return (
    <div data-testid="slot-window">
      {catalog !== undefined && <WindowControl catalog={catalog} />}
    </div>
  );
}

function WindowControl({ catalog }: { catalog: Catalog }) {
  const t = useTranslations("window");
  const locale = useLocale();
  const stored = useAppStore((state) => state.window);
  const focusId = useAppStore((state) => state.draftSpec?.var ?? null);
  const focus = catalog.variables.find((variable) => variable.id === focusId);

  const trackEndMonth = pinnedMonth(catalog);
  const endMonth = focus?.record_end ?? trackEndMonth;
  const first = focus === undefined ? RECORD_START_YEAR : yearOf(focus.record_start);
  const last = yearOf(endMonth);
  const clamp = (year: number) => Math.min(Math.max(year, first), last);
  const { shown, dragProps } = useDragValues([
    clamp(stored.start),
    clamp(stored.end === "latest" ? last : stored.end),
  ]);
  const [start, end] = shown;
  const years = end - start + 1;
  const minYears = focus?.min_record_years ?? DEFAULT_MIN_RECORD_YEARS;
  const gapStart = first - RECORD_START_YEAR;
  const gapEnd = yearOf(trackEndMonth) - last;

  function handleCommit([nextStart, nextEnd]: number[]) {
    actions.setWindow(
      { start: nextStart, end: nextEnd === last ? "latest" : nextEnd },
      "user",
    );
  }

  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="flex justify-between tabular-nums">
        <span>{start}</span>
        <span>
          {end === last
            ? t("latest", { month: formatMonth(endMonth, locale) })
            : end}
        </span>
      </p>
      <div className="flex items-center">
        {gapStart > 0 && (
          <span
            data-testid="coverage-gap-start"
            aria-hidden
            className="h-1 rounded-full bg-coverage-muted"
            style={{ flex: `${gapStart} 1 0` }}
          />
        )}
        <LabeledSlider
          data-testid="window-slider"
          thumbLabels={[t("start_thumb"), t("end_thumb")]}
          min={first}
          max={last}
          step={1}
          style={{ flex: `${last - first} 1 0` }}
          onValueCommit={handleCommit}
          {...dragProps}
        />
        {gapEnd > 0 && (
          <span
            data-testid="coverage-gap-end"
            aria-hidden
            className="h-1 rounded-full bg-coverage-muted"
            style={{ flex: `${gapEnd} 1 0` }}
          />
        )}
      </div>
      {(gapStart > 0 || gapEnd > 0) && (
        <p className="text-xs text-muted-foreground">
          {t("beyond_coverage", { start: String(first), end: String(last) })}
        </p>
      )}
      {years < minYears && (
        <p role="status" className="text-too-short">
          {t("record_guard", { years, min: minYears })}
        </p>
      )}
    </div>
  );
}

/** The later pinned month of the two stores. "YYYY-MM" strings sort as dates. */
function pinnedMonth(catalog: Catalog): string {
  const { daily, monthly } = catalog.datasets;
  return daily.last_valid_month > monthly.last_valid_month
    ? daily.last_valid_month
    : monthly.last_valid_month;
}

function yearOf(yearMonth: string): number {
  return Number.parseInt(yearMonth.slice(0, YEAR_DIGITS), 10);
}
