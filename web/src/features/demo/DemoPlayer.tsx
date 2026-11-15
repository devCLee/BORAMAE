"use client";

import {
  PauseIcon,
  PlayIcon,
  SkipForwardIcon,
  StepForwardIcon,
  XIcon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useEffect, useEffectEvent, useRef } from "react";

import { LanguageGate } from "@/components/shell/LanguageGate";
import { Button } from "@/components/ui/button";
import type { DemoScript, Lang } from "@/contracts/types";
import { useParse } from "@/hooks/queries";
import { usePathname, useRouter } from "@/i18n/navigation";
import { actions, useAppStore } from "@/state/store";

import { verdictIndexOf } from "./demo-content";
import { applyProposal, catchUp, STEP_MS } from "./play-step";

const CONTROL_CLASS = "min-h-11 aria-disabled:opacity-50";

/**
 * The player (DES-020, FR-06): a caption bar, a step indicator and the controls
 * over the real UI, which the script drives through the store actions. It mounts
 * only while a case runs, because the next-intl router needs the Next.js router.
 */
export function DemoPlayer({ script }: { script: DemoScript }) {
  const t = useTranslations("demo");
  const locale = useLocale() as Lang;
  const router = useRouter();
  const pathname = usePathname();
  const stepIndex = useAppStore((state) => state.demo?.stepIndex ?? 0);
  const isPaused = useAppStore((state) => state.demo?.isPaused ?? true);
  const { mutate: submitQuestion, data: proposal } = useParse();
  const pauseRef = useRef<HTMLButtonElement>(null);
  const step = script.steps[stepIndex];
  const lastIndex = script.steps.length - 1;
  const verdictIndex = verdictIndexOf(script);
  const isAtLast = stepIndex >= lastIndex;
  const isPastVerdict = stepIndex >= verdictIndex;

  function moveTo(target: number): void {
    if (target <= stepIndex || target > lastIndex) {
      return;
    }
    if (step.action === "choose_language") {
      // FR-06 starts at the language screen: leaving it opens the route of the script's language.
      const lang = step.args.lang as Lang;
      actions.setLang(lang);
      if (lang !== locale) {
        router.replace(pathname, { locale: lang });
      }
    }
    actions.setDemoStep(target);
  }

  const handleTimer = useEffectEvent(() => moveTo(stepIndex + 1));

  useEffect(() => {
    pauseRef.current?.focus();
  }, []);

  useEffect(() => {
    catchUp(script, stepIndex, submitQuestion);
  }, [script, stepIndex, submitQuestion]);

  useEffect(() => {
    if (proposal !== undefined) {
      applyProposal(script, proposal);
    }
  }, [script, proposal]);

  useEffect(() => {
    if (isPaused || isAtLast) {
      return;
    }
    const timer = setTimeout(() => handleTimer(), STEP_MS);
    return () => clearTimeout(timer);
  }, [stepIndex, isPaused, isAtLast]);

  return (
    <>
      <section
        aria-label={t("label")}
        className="relative z-50 flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-background px-4 py-2"
      >
        <p className="text-xs text-muted-foreground">
          {t("step", { current: stepIndex + 1, total: script.steps.length })}
        </p>
        <p aria-live="polite" className="min-w-0 flex-1 text-sm font-medium">
          {step.caption[locale]}
        </p>
        <div role="group" aria-label={t("controls.label")} className="flex flex-wrap gap-2">
          <Button
            ref={pauseRef}
            variant="outline"
            className={CONTROL_CLASS}
            onClick={() => actions.pauseDemo(!isPaused)}
          >
            {isPaused ? <PlayIcon aria-hidden /> : <PauseIcon aria-hidden />}
            {isPaused ? t("controls.play") : t("controls.pause")}
          </Button>
          {/* aria-disabled and not disabled, so a control keeps the focus at the end. */}
          <Button
            variant="outline"
            className={CONTROL_CLASS}
            aria-disabled={isAtLast}
            onClick={() => moveTo(stepIndex + 1)}
          >
            <StepForwardIcon aria-hidden />
            {t("controls.next")}
          </Button>
          <Button
            variant="outline"
            className={CONTROL_CLASS}
            aria-disabled={isPastVerdict}
            onClick={() => moveTo(verdictIndex)}
          >
            <SkipForwardIcon aria-hidden />
            {t("controls.skip")}
          </Button>
          <Button variant="ghost" className={CONTROL_CLASS} onClick={actions.endDemo}>
            <XIcon aria-hidden />
            {t("controls.leave")}
          </Button>
        </div>
      </section>
      {step.action === "choose_language" && (
        <Overlay label={t("overlay.language")}>
          <LanguageGate onChoose={() => moveTo(stepIndex + 1)} />
        </Overlay>
      )}
      {step.action === "closing_card" && (
        <Overlay label={t("overlay.closing")}>
          <ClosingCard />
        </Overlay>
      )}
    </>
  );
}

/** Covers the app below the player bar, which stays on top with its controls. */
function Overlay({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      role="dialog"
      aria-label={label}
      className="fixed inset-0 z-40 grid place-items-center bg-background/95 p-6"
    >
      {children}
    </div>
  );
}

function ClosingCard() {
  const t = useTranslations("demo.closing");
  const tCommon = useTranslations("common");

  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <p className="text-3xl font-semibold tracking-tight">{tCommon("app_name")}</p>
      <p>{t("sources")}</p>
      <p className="text-muted-foreground">{t("about")}</p>
      {/* ponytail: the address that serves the page; the public URL exists only after
          the deployment of wave 8. Put it in the closing_card args then. */}
      <p className="font-medium">{window.location.origin}</p>
    </div>
  );
}
