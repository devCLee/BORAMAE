"use client";

import { useTranslations } from "next-intl";
import { useId } from "react";

import { Button } from "@/components/ui/button";
import { actions } from "@/state/store";
import type { Mode } from "@/state/types";

const DOORS: Exclude<Mode, null>[] = ["guided", "explore", "demo"];

/** The three doors of the first screen (PRD "User flows"). */
export function Doors() {
  const t = useTranslations("landing");
  const idPrefix = useId();

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-base font-semibold">{t("title")}</h2>
      {DOORS.map((mode) => (
        <div key={mode} className="flex flex-col gap-1">
          <Button
            variant={mode === "guided" ? "default" : "outline"}
            className="min-h-11 justify-start"
            aria-describedby={`${idPrefix}-${mode}`}
            onClick={() => actions.chooseDoor(mode)}
          >
            {t(`doors.${mode}.label`)}
          </Button>
          <p id={`${idPrefix}-${mode}`} className="text-xs text-muted-foreground">
            {t(`doors.${mode}.description`)}
          </p>
        </div>
      ))}
    </div>
  );
}
