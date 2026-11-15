"use client";

import { useTranslations } from "next-intl";
import { useEffect, useId } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Num } from "@/components/Num";
import { Skeleton } from "@/components/ui/skeleton";
import type { Catalog, ScanChecked, TrendResult } from "@/contracts/types";
import { outcomeOf } from "@/features/verdict/outcome";
import { useCatalog, useScan, useTrend } from "@/hooks/queries";
import type { Answer } from "@/lib/fetch-layer";
import { runAnalysis } from "@/state/run-analysis";
import { actions } from "@/state/store";

import { findVariable, HitList, NearbyList, VariableName } from "./ScanLists";

/**
 * The no-trend fallback (FR-19, TDD Flow C): other variables here, the same variable
 * nearby, and the years a detection still needs. It asks for the scan only for a tested
 * verdict that is not significant; record too short and no data open no scan.
 */
export function FallbackPanel() {
  const t = useTranslations("fallback");
  const titleId = useId();
  const trend = useTrend();
  const scan = useScan();
  const catalog = useCatalog();
  const outcome = trend.data && outcomeOf(trend.data.body);
  const isScanDue = outcome === "not_yet" || outcome === "no_trend";

  useEffect(() => {
    if (!isScanDue) {
      return;
    }
    // runAnalysis never rejects; the panel reads the outcome through useScan.
    void runAnalysis("scan");
    // The scan and its nearby pins on the map leave with the fallback.
    return () => actions.closePanel("scan");
  }, [isScanDue]);

  if (!isScanDue || trend.data === undefined) {
    return <section data-testid="slot-fallback" />;
  }

  const result = scan.data?.body;
  const isNothingFound = result?.hits.length === 0 && result.nearby.length === 0;

  return (
    <section data-testid="slot-fallback" aria-labelledby={titleId} className="flex flex-col gap-4">
      <h3 id={titleId} className="text-base font-medium">
        {t("title")}
      </h3>
      {scan.isError && (
        <EmptyState messageKey={scan.error.code} onRetry={() => void scan.refetch()} />
      )}
      {result === undefined && !scan.isError && (
        <div role="status" aria-label={t("loading")} className="flex flex-col gap-2">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      )}
      {result && isNothingFound && <p className="text-sm font-medium">{t("nothing_found")}</p>}
      {result && <HitList hits={result.hits} catalog={catalog.data} />}
      {result && <NearbyList nearby={result.nearby} note={result.nearby_note} />}
      <YearsNeededSection trend={trend.data} />
      {result && isNothingFound && <CheckedList checked={result.checked} catalog={catalog.data} />}
    </section>
  );
}

/** FR-15: the years still needed (more), never the total, and never as a forecast. */
function YearsNeededSection({ trend }: { trend: Answer<TrendResult> }) {
  const t = useTranslations("fallback.years");
  const headingId = useId();
  const { years_needed: years, provenance, footprint } = trend.body;
  if (years === null) {
    return null;
  }
  const { more, reason } = years;
  const reasonKey = `reasons.${reason}`;

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-1 text-sm">
      <h4 id={headingId} className="font-medium">
        {t("heading")}
      </h4>
      {reason == null && more !== null ? (
        <>
          <p>
            {t.rich("more", {
              count: more,
              num: () => (
                <Num value={more} provenance={provenance} footprint={footprint} meta={trend.meta} />
              ),
            })}
          </p>
          <p className="text-muted-foreground">{t("estimate")}</p>
        </>
      ) : (
        t.has(reasonKey) && <p>{t(reasonKey)}</p>
      )}
    </section>
  );
}

/** "Nothing found" with what the scan looked at (TR-F-027). */
function CheckedList({ checked, catalog }: { checked: ScanChecked[]; catalog: Catalog | undefined }) {
  const t = useTranslations("fallback.checked");
  const headingId = useId();
  const status = ({ status: kind, reason }: ScanChecked) => {
    if (kind === "tested") {
      return t("tested");
    }
    const reasonKey = `reasons.${reason}`;
    return t.has(reasonKey)
      ? t("not_testable_because", { reason: t(reasonKey) })
      : t("not_testable");
  };

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-1 text-sm">
      <h4 id={headingId} className="font-medium">
        {t("heading")}
      </h4>
      <ul aria-labelledby={headingId} className="flex flex-col gap-1">
        {checked.map((entry) => (
          <li key={entry.var}>
            {t.rich("item", {
              status: status(entry),
              name: () => (
                <VariableName id={entry.var} variable={findVariable(catalog, entry.var)} />
              ),
            })}
          </li>
        ))}
      </ul>
    </section>
  );
}
