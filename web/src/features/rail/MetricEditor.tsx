"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DraftSpec, Lang } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";
import { actions } from "@/state/store";

import { effectiveMetric } from "./draft";
import { OP_KEYS } from "./wording";
import { useUnitLabel } from "./use-unit-label";

/**
 * The metric of the draft: its definition and an editable threshold (FR-16,
 * TR-F-015). A threshold edit is a draft edit, so it clears the confirmation.
 */
export function MetricEditor({ draft }: { draft: DraftSpec }) {
  const t = useTranslations("rail");
  const lang = useLocale() as Lang;
  const fieldId = useId();
  const unitLabel = useUnitLabel();
  const { data: catalog } = useCatalog();
  const metric = catalog?.metrics.find(({ id }) => id === draft.metric.id);
  const variable = catalog?.variables.find(({ id }) => id === draft.var);
  if (metric === undefined || variable === undefined) {
    return null;
  }
  const { threshold, op } = effectiveMetric(draft.metric, metric.defaults);
  const unit = unitLabel(variable.unit);

  return (
    <section className="flex flex-col gap-2 rounded-lg bg-muted p-3 text-sm">
      <h3 className="font-medium">{t("metric.heading")}</h3>
      <p className="font-medium">{metric.name[lang]}</p>
      <p>{metric.definition[lang]}</p>
      {threshold !== null && (
        <div className="flex flex-col gap-1">
          <Label htmlFor={fieldId}>{t("metric.threshold", { unit })}</Label>
          <div className="flex items-center gap-2">
            {op !== null && <span>{t(`op.${OP_KEYS[op]}`)}</span>}
            <Input
              // A new variable or metric starts the field from its own threshold.
              key={`${draft.var}:${draft.metric.id}`}
              id={fieldId}
              type="number"
              step="any"
              inputMode="decimal"
              defaultValue={threshold}
              className="min-h-11 w-28"
              onChange={(event) => {
                const value = event.target.value;
                // An empty or half-typed number keeps the last threshold.
                if (value !== "") {
                  actions.editDraft({ metric: { ...draft.metric, threshold: value } }, "user");
                }
              }}
            />
          </div>
        </div>
      )}
    </section>
  );
}
