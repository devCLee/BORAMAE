"use client";

import { cn } from "cn";
import { ChevronDownIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import type { Lang } from "@/contracts/types";
import { CasePanel } from "@/features/case/CasePanel";
import { DemoBar } from "@/features/demo/DemoBar";
import { GuideLauncher } from "@/features/guide/GuideLauncher";
import { MapView } from "@/features/map/MapView";
import { PlaceControls } from "@/features/places/PlaceControls";
import { ProvenanceDrawer } from "@/features/provenance/ProvenanceDrawer";
import { Rail } from "@/features/rail/Rail";
import { TimeSlider } from "@/features/window/TimeSlider";
import { actions } from "@/state/store";

import { LanguageSwitch } from "./LanguageSwitch";

const MAIN_ID = "main";
const CASE_BODY_ID = "case-panel-body";

/**
 * One screen (PRD "UX & design direction"): the map full-bleed behind the rail, the
 * place controls and the case panel, with the time window along the bottom.
 * ponytail: below md (768 px, the Tailwind default) the rail sits on top and the case
 * panel is a bottom sheet that opens by default, so a judge on a phone sees the result
 * first. No document places the rail or the guide on a phone, and the column widths
 * are working values too.
 */
export function AppShell() {
  const t = useTranslations("common");
  const [isCaseOpen, setIsCaseOpen] = useState(true);
  const locale = useLocale() as Lang;

  useEffect(() => {
    // The store starts with the stored choice, or English. The route is the language
    // on screen (FR-01), so parse and the guide must get the language of the route.
    actions.setLang(locale);
  }, [locale]);

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <a
        href={`#${MAIN_ID}`}
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-3"
      >
        {t("shell.skip_to_main")}
      </a>
      <header className="flex h-12 shrink-0 items-center justify-between border-b px-4">
        <span className="font-semibold tracking-tight">{t("app_name")}</span>
        <LanguageSwitch />
      </header>
      <main id={MAIN_ID} tabIndex={-1} className="flex min-h-0 flex-1 flex-col">
        <DemoBar />
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden md:grid md:grid-cols-[16rem_minmax(0,1fr)_20rem] md:grid-rows-1 lg:grid-cols-[20rem_minmax(0,1fr)_24rem]">
          <div className="absolute inset-0">
            <MapView />
          </div>
          <aside
            aria-label={t("shell.rail")}
            className="relative max-h-[35dvh] overflow-y-auto border-b bg-background md:max-h-none md:border-r md:border-b-0"
          >
            <Rail />
          </aside>
          {/* The map takes the drags and clicks that land between the controls. */}
          <div className="pointer-events-none relative flex min-h-0 flex-1 flex-col items-center justify-between gap-3 p-3">
            <div className="pointer-events-auto">
              <PlaceControls />
            </div>
            <div className="pointer-events-auto self-end">
              <GuideLauncher />
            </div>
          </div>
          <section
            aria-label={t("shell.case")}
            className="relative flex min-h-0 flex-col rounded-t-xl border-t bg-background shadow-lg md:rounded-none md:border-t-0 md:border-l md:shadow-none"
          >
            <button
              type="button"
              aria-expanded={isCaseOpen}
              aria-controls={CASE_BODY_ID}
              onClick={() => setIsCaseOpen((isOpen) => !isOpen)}
              className="flex h-11 shrink-0 items-center justify-center gap-2 text-sm font-medium md:hidden"
            >
              {t("shell.case")}
              <ChevronDownIcon
                aria-hidden
                className={cn(
                  "size-4 transition-transform",
                  !isCaseOpen && "rotate-180",
                )}
              />
            </button>
            <div
              id={CASE_BODY_ID}
              className={cn(
                "min-h-0 flex-1 overflow-y-auto",
                isCaseOpen ? "max-md:max-h-[50dvh]" : "max-md:hidden",
              )}
            >
              <CasePanel />
            </div>
          </section>
        </div>
        <section
          aria-label={t("shell.window")}
          className="shrink-0 border-t bg-background px-4 py-2"
        >
          <TimeSlider />
        </section>
      </main>
      <ProvenanceDrawer />
    </div>
  );
}
