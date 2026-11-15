"use client";

import { CircleCheckIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Term } from "@/components/Term";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CatalogVariable, Lang, ReasonCode } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";

import { CatalogPicker } from "./CatalogPicker";
import { useUnitLabel } from "./use-unit-label";

/** One variable of step 2. A reason exists only for a variable that parse proposed. */
export interface Card {
  var: string;
  metric_id: string;
  reason_code: ReasonCode | null;
}

interface VariableCardProps {
  card: Card;
  /** True when the draft spec holds this variable and metric. */
  isDraft: boolean;
  onConfirm: () => void;
  onSwap: (variable: CatalogVariable) => void;
}

/**
 * A proposed variable with its catalog facts (FR-07): name and definition, unit,
 * dataset, record years and the trend-ready badge, then the reason (FR-03).
 */
export function VariableCard({ card, isDraft, onConfirm, onSwap }: VariableCardProps) {
  const t = useTranslations("rail.variables");
  const lang = useLocale() as Lang;
  const unitLabel = useUnitLabel();
  const { data: catalog } = useCatalog();
  const variable = catalog?.variables.find(({ id }) => id === card.var);
  const name = variable?.name[lang] ?? card.var;

  return (
    <article className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 className="font-medium">
        {variable ? (
          <Term id={variable.id} definition={variable.definition}>
            {name}
          </Term>
        ) : (
          name
        )}
      </h3>
      {variable && (
        <>
          <p className="text-sm">{variable.definition[lang]}</p>
          {variable.is_trend_ready && (
            <Badge>
              <CircleCheckIcon aria-hidden />
              {t("trend_ready")}
            </Badge>
          )}
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted-foreground">{t("unit")}</dt>
            <dd>{unitLabel(variable.unit)}</dd>
            <dt className="text-muted-foreground">{t("dataset")}</dt>
            <dd>
              <span>{variable.dataset}</span> · <Term id="model_data" />
            </dd>
            <dt className="text-muted-foreground">{t("record")}</dt>
            <dd>
              {t("record_years", {
                start: variable.record_start.slice(0, 4),
                end: variable.record_end.slice(0, 4),
              })}
            </dd>
          </dl>
        </>
      )}
      {card.reason_code !== null && (
        <p className="text-xs text-muted-foreground">
          {t(`reasons.${card.reason_code}`)}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={isDraft ? "default" : "outline"}
          className="min-h-11"
          aria-pressed={isDraft}
          aria-label={t("confirm_name", { name })}
          onClick={onConfirm}
        >
          {t("confirm")}
        </Button>
        <CatalogPicker
          label={t("swap")}
          name={t("swap_name", { name })}
          onPick={onSwap}
        />
      </div>
    </article>
  );
}
