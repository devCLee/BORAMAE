"use client";

import { useTranslations } from "next-intl";

import { useAppStore } from "@/state/store";

import { Doors } from "./Doors";
import { Steps } from "./Steps";

/**
 * The left rail: the three doors until the user picks one, then the four guided
 * steps. Explore mode leaves the map to the user, and a demo drives the steps.
 */
export function Rail() {
  const t = useTranslations("rail");
  const mode = useAppStore((state) => state.mode);

  return (
    <div data-testid="slot-rail" className="flex flex-col gap-4 p-4">
      {mode === null && <Doors />}
      {mode === "explore" && (
        <p className="text-sm text-muted-foreground">{t("explore_hint")}</p>
      )}
      {(mode === "guided" || mode === "demo") && <Steps />}
    </div>
  );
}
