"use client";

import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { CaseBoard } from "@/features/board/CaseBoard";
import { TrendChart } from "@/features/chart/TrendChart";
import { FallbackPanel } from "@/features/fallback/FallbackPanel";
import { Suggestions } from "@/features/suggestions/Suggestions";
import { outcomeOf } from "@/features/verdict/outcome";
import { VerdictCard } from "@/features/verdict/VerdictCard";
import { useCatalog, useTrend } from "@/hooks/queries";
import { useAppStore } from "@/state/store";

/**
 * The right case panel: the verdict card, the chart, then the case board for a
 * significant verdict or the fallback for any other tested verdict, and the next
 * steps (TDD Flow C). "Record too short" and no data open neither.
 */
export function CasePanel() {
  const t = useTranslations("case");
  const isTrendOpen = useAppStore((state) => state.openPanels.includes("trend"));
  // A control that leaves the screen, such as the retry, hands its focus to the panel.
  const rootRef = useRef<HTMLDivElement>(null);

  return (
    <div
      data-testid="slot-case"
      ref={rootRef}
      tabIndex={-1}
      className="flex flex-col gap-4 p-4"
    >
      {isTrendOpen ? (
        <TrendCase onFocusPanel={() => rootRef.current?.focus()} />
      ) : (
        <p className="text-sm text-muted-foreground">{t("idle")}</p>
      )}
    </div>
  );
}

function TrendCase({ onFocusPanel }: { onFocusPanel: () => void }) {
  const t = useTranslations("case");
  const trend = useTrend();
  const catalog = useCatalog();
  const gate = useAppStore((state) => state.verdictGate);
  // The last answer stays while a new request loads, and after it fails.
  const [last, setLast] = useState(trend.data);
  if (trend.data !== undefined && trend.data !== last) {
    setLast(trend.data);
  }
  const answer = trend.data ?? last;
  const retry = () => {
    onFocusPanel();
    void trend.refetch();
  };

  if (answer === undefined) {
    return trend.isError ? (
      <EmptyState messageKey={trend.error.code} onRetry={retry} />
    ) : (
      <PanelSkeleton label={t("loading")} />
    );
  }

  const result = answer.body;
  const outcome = outcomeOf(result);
  const variable = catalog.data?.variables.find(
    (candidate) => candidate.id === result.spec.var,
  );
  const metric = catalog.data?.metrics.find(
    (candidate) => candidate.id === result.spec.metric.id,
  );
  // ponytail: a no-data result has no series to guess at, so it skips the chart tap
  // of the verdict gate (FR-10). Every other result waits for the gate.
  const isRevealed = gate === "revealed" || outcome === "no_data";
  const isSignificant =
    outcome === "significant_rise" || outcome === "significant_fall";

  return (
    <>
      {trend.isPending && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("updating")}
        </p>
      )}
      {trend.isError && (
        <EmptyState messageKey={trend.error.code} onRetry={retry} />
      )}
      {isRevealed &&
        (variable && metric ? (
          <VerdictCard
            result={result}
            meta={answer.meta}
            variable={variable}
            metric={metric}
          />
        ) : (
          <PanelSkeleton label={t("loading")} />
        ))}
      {!trend.isError && <TrendChart />}
      {isRevealed &&
        (isSignificant ? <CaseBoard /> : result.verdict !== null && <FallbackPanel />)}
      {isRevealed && variable && (
        <Suggestions
          outcome={outcome}
          recordStartYear={Number.parseInt(variable.record_start, 10)}
        />
      )}
    </>
  );
}

function PanelSkeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-3">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="h-28" />
    </div>
  );
}
