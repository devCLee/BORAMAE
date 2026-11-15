"use client";

import { useLocale, useTranslations } from "next-intl";

import type { Lang, UnavailableRequest } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";

/** "Not in this version" with the nearest available variable (TR-F-003). */
export function UnavailableNote({ unavailable }: { unavailable: UnavailableRequest }) {
  const t = useTranslations("rail.variables");
  const lang = useLocale() as Lang;
  const { data: catalog } = useCatalog();
  const { requested, nearest_var: nearestVar } = unavailable;
  const nearest = catalog?.variables.find(({ id }) => id === nearestVar);

  return (
    <div role="status" className="flex flex-col gap-1 rounded-lg border border-dashed p-3 text-sm">
      <p>{t("unavailable", { requested })}</p>
      <p>
        {nearestVar === null
          ? t("no_nearest")
          : t("nearest", { name: nearest?.name[lang] ?? nearestVar })}
      </p>
    </div>
  );
}
