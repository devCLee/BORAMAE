"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId } from "react";

import { Term } from "@/components/Term";
import { VerdictChip } from "@/components/VerdictChip";
import type {
  CatalogMetric,
  CatalogVariable,
  Lang,
  RequestMeta,
  TrendResult,
} from "@/contracts/types";

import { outcomeOf } from "./outcome";
import { VerdictStats } from "./VerdictStats";

export interface VerdictCardProps {
  result: TrendResult;
  /** The facts of the request of the trend panel. Null for none. */
  meta: RequestMeta | null;
  variable: CatalogVariable;
  metric: CatalogMetric;
}

/**
 * The verdict card (FR-13 to FR-15): the verdict of the result file in plain words
 * first, then the numbers behind it. The browser applies no rule to the statistics.
 * The sentence is a message template, not AI text, so it carries no badge.
 * ponytail: the sentences, the not-yet sentence that also serves p below 0.05 with zero
 * inside the interval, and all Korean copy wait for the wording review of FR-13.
 */
export function VerdictCard({ result, meta, variable, metric }: VerdictCardProps) {
  const t = useTranslations("verdict");
  const lang = useLocale() as Lang;
  const titleId = useId();
  const outcome = outcomeOf(result);
  const olsNoteKey = `notes.ols_missing.${result.stats.ols.reason}`;

  return (
    <article
      aria-labelledby={titleId}
      className="flex flex-col gap-3 rounded-xl border bg-card p-4 text-sm text-card-foreground"
    >
      <header className="flex flex-wrap items-center gap-2">
        {outcome !== "no_data" && <VerdictChip verdict={outcome} />}
        <span className="text-xs text-muted-foreground">
          <Term id="model_data" />
        </span>
      </header>
      <h2 id={titleId} className="text-base font-medium">
        <Term id={variable.id} definition={variable.definition}>
          {variable.name[lang]}
        </Term>
        {" · "}
        <Term id={metric.id} definition={metric.definition}>
          {metric.name[lang]}
        </Term>
      </h2>
      <p>{t(`sentences.${outcome}`)}</p>
      {outcome !== "no_data" && (
        <>
          {result.stats.reason !== null && (
            <p>{t(`stats_reasons.${result.stats.reason}`)}</p>
          )}
          <VerdictStats result={result} meta={meta} variable={variable} />
          <ul className="flex flex-col gap-1 text-muted-foreground">
            {result.flags.includes("methods_disagree") && (
              <li>{t("notes.methods_disagree")}</li>
            )}
            {result.flags.includes("ols_p_missing") && (
              <li>
                {t.has(olsNoteKey) ? t(olsNoteKey) : t("notes.ols_missing.other")}
              </li>
            )}
            {meta?.usedContainingCell && <li>{t("notes.containing_cell")}</li>}
            <li>
              <Term id="not_independent" />
            </li>
          </ul>
        </>
      )}
    </article>
  );
}
