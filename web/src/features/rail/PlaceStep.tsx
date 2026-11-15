"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatNumber } from "@/lib/format";
import { useAppStore } from "@/state/store";

import { formatPoint } from "./wording";

/**
 * Step 3: the pin, the radius and the cells inside, as the map and the place
 * controls leave them in the store (FR-04). This step sets none of them.
 */
export function PlaceStep() {
  const t = useTranslations("rail.place");
  const locale = useLocale();
  const pin = useAppStore((state) => state.area.pin);
  const radiusKm = useAppStore((state) => state.area.radiusKm);
  const preview = useAppStore((state) => state.cellPreview);

  if (pin === null) {
    return <p className="text-sm">{t("no_pin")}</p>;
  }
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p>{t("pin", { point: formatPoint(pin, locale) })}</p>
      <p>{t("radius", { radius: formatNumber(radiusKm, locale) })}</p>
      {preview !== null && (
        <p role="status">
          {preview.usedContainingCell
            ? t("containing_cell")
            : t("cells", { count: preview.count })}
        </p>
      )}
    </div>
  );
}
