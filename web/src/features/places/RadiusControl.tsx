"use client";

import { useLocale, useTranslations } from "next-intl";

import { LabeledSlider, useDragValues } from "@/features/window/LabeledSlider";
import { RADIUS_MIN_KM } from "@/lib/cells";
import { formatNumber } from "@/lib/format";
import { actions, useAppStore } from "@/state/store";

/** The largest radius of an area (FR-04, RADIUS_MAX_KM in api/boramae/constants.py). */
const RADIUS_MAX_KM = 300;

/** The radius of the pinned circle, 10 to 300 km (TR-F-007). A release sends it. */
export function RadiusControl() {
  const t = useTranslations("places.radius");
  const locale = useLocale();
  const radiusKm = useAppStore((state) => state.area.radiusKm);
  const { shown, dragProps } = useDragValues([radiusKm]);

  return (
    <div className="flex flex-col text-sm">
      <p className="flex justify-between">
        <span>{t("label")}</span>
        <span className="tabular-nums">
          {t("value", { radius: formatNumber(shown[0], locale) })}
        </span>
      </p>
      <LabeledSlider
        data-testid="radius-slider"
        thumbLabels={[t("label")]}
        min={RADIUS_MIN_KM}
        max={RADIUS_MAX_KM}
        step={1}
        onValueCommit={([km]) => actions.setRadius(km, "user")}
        {...dragProps}
      />
    </div>
  );
}
