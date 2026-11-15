"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import type { DraftSpec, Lang } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";
import { formatNumber } from "@/lib/format";
import { runAnalysis } from "@/state/run-analysis";
import { actions, useAppStore } from "@/state/store";

import { effectiveMetric } from "./draft";
import { useUnitLabel } from "./use-unit-label";
import { formatMonthName, formatPoint, OP_KEYS } from "./wording";

/**
 * The draft spec read back as one template sentence in the UI language, and the
 * Confirm that lets the first analysis request leave (FR-03, DES-002). A pin or
 * radius change clears the confirmation, so Confirm shows again.
 */
export function ReadBack({ draft }: { draft: DraftSpec }) {
  const t = useTranslations("rail.read_back");
  const tOp = useTranslations("rail.op");
  const locale = useLocale();
  const lang = locale as Lang;
  const headingId = useId();
  const unitLabel = useUnitLabel();
  const { data: catalog } = useCatalog();
  const pin = useAppStore((state) => state.area.pin);
  const radiusKm = useAppStore((state) => state.area.radiusKm);
  const timeWindow = useAppStore((state) => state.window);
  const place = useAppStore((state) => state.proposal?.spec.place ?? null);
  const isConfirmed = useAppStore((state) => state.confirmedSpec !== null);
  const variable = catalog?.variables.find(({ id }) => id === draft.var);
  const metric = catalog?.metrics.find(({ id }) => id === draft.metric.id);
  const { threshold, op, months } = effectiveMetric(draft.metric, metric?.defaults);

  // ponytail: the parsed place names the area only while the pin sits on its exact
  // coordinates; the store keeps no name for a pin, so any other pin reads as numbers.
  const isPinOnPlace = place !== null && pin?.lat === place.lat && pin.lon === place.lon;
  const area =
    pin === null
      ? t("area_view")
      : t("area_pin", {
          place: isPinOnPlace ? place.name : formatPoint(pin, locale),
          radius: formatNumber(radiusKm, locale),
        });
  const condition =
    threshold !== null && op !== null
      ? t("condition", {
          op: tOp(OP_KEYS[op]),
          value: threshold,
          unit: variable ? unitLabel(variable.unit) : "",
        })
      : "";
  const monthText = months?.length
    ? months.length === 1
      ? t("months_one", { from: formatMonthName(months[0], locale) })
      : t("months_range", {
          from: formatMonthName(months[0], locale),
          to: formatMonthName(months[months.length - 1], locale),
        })
    : "";
  const windowText =
    timeWindow.end === "latest"
      ? t("window_latest", { start: String(timeWindow.start) })
      : t("window_range", { start: String(timeWindow.start), end: String(timeWindow.end) });

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 id={headingId} className="text-sm font-medium">
        {t("heading")}
      </h3>
      <p className="text-sm">
        {t("sentence", {
          area,
          metric: metric?.name[lang] ?? draft.metric.id,
          variable: variable?.name[lang] ?? draft.var,
          condition,
          months: monthText,
          window: windowText,
        })}
      </p>
      {isConfirmed ? (
        <p role="status" className="text-sm text-muted-foreground">
          {t("confirmed")}
        </p>
      ) : (
        <Button
          className="min-h-11 self-start"
          onClick={() => {
            actions.confirmSpec();
            // runAnalysis never rejects; the result panel shows its outcome.
            void runAnalysis("trend");
          }}
        >
          {t("confirm")}
        </Button>
      )}
    </section>
  );
}
