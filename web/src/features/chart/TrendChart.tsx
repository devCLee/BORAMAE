"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { useTrend } from "@/hooks/queries";

import { ChartFigure } from "./ChartFigure";

/** The chart of the tested series (FR-10, TR-F-017), read from the trend result. */
export function TrendChart() {
  const t = useTranslations("chart");
  const { data, error, isFetching, refetch } = useTrend();

  let content: ReactNode = null;
  if (error) {
    content = (
      <EmptyState messageKey={error.code} onRetry={() => void refetch()} />
    );
  } else if (data && data.body.series.yearly.years.length === 0) {
    content = (
      <p className="p-6 text-center text-sm text-muted-foreground">
        {t("no_values")}
      </p>
    );
  } else if (data) {
    content = <ChartFigure result={data.body} />;
  } else if (isFetching) {
    content = (
      <div role="status" aria-label={t("loading")}>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return <div data-testid="slot-chart">{content}</div>;
}
