"use client";

import { InfoIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import type {
  Footprint,
  Provenance,
  RequestMeta,
  ShareScale,
} from "@/contracts/types";
import { openProvenance } from "@/features/provenance/provenance-state";
import { formatNumber, useFormatRate } from "@/lib/format";

export interface NumProps {
  value: number;
  provenance: Provenance;
  footprint?: Footprint;
  meta?: RequestMeta | null;
  /** Intl options of the shown value, such as maximumFractionDigits. */
  options?: Intl.NumberFormatOptions;
  /** Shows the value as a rate per decade through formatRate. */
  rate?: { unit: string; shareScale: ShareScale | null };
}

/**
 * Every displayed number (FR-26, DES-018): the value in the UI locale and an info
 * button that opens the provenance drawer with the record of the number.
 */
export function Num({
  value,
  provenance,
  footprint,
  meta,
  options,
  rate,
}: NumProps) {
  const locale = useLocale();
  const t = useTranslations("provenance");
  const formatRate = useFormatRate();
  const text = rate
    ? formatRate(value, rate.unit, rate.shareScale, options)
    : formatNumber(value, locale, options);

  return (
    <span className="inline-flex items-baseline gap-0.5 tabular-nums">
      {text}
      {/* The after: box widens the hit area to 44 px without moving the line. */}
      <button
        type="button"
        aria-label={t("open", { value: text })}
        onClick={(event) =>
          openProvenance(
            { provenance, footprint: footprint ?? null, meta: meta ?? null },
            event.currentTarget,
          )
        }
        className="relative inline-flex size-6 shrink-0 items-center justify-center self-center rounded-sm text-muted-foreground after:absolute after:-inset-2.5 hover:text-foreground"
      >
        <InfoIcon aria-hidden className="size-3.5" />
      </button>
    </span>
  );
}
