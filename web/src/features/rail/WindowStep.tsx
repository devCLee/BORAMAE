"use client";

import { useTranslations } from "next-intl";

import { useAppStore } from "@/state/store";

/** Step 4: the time window that the slider below the map sets (FR-09). */
export function WindowStep() {
  const t = useTranslations("rail.window");
  const { start, end } = useAppStore((state) => state.window);

  return (
    <div className="flex flex-col gap-1 text-sm">
      <p>
        {end === "latest"
          ? t("latest", { start: String(start) })
          : t("range", { start: String(start), end: String(end) })}
      </p>
      <p className="text-muted-foreground">{t("hint")}</p>
    </div>
  );
}
