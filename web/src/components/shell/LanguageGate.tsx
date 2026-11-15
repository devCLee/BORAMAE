"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { routing } from "@/i18n/routing";
import enCommon from "@/messages/en/common.json";
import koCommon from "@/messages/ko/common.json";

import {
  type AppLocale,
  LANGUAGE_NAMES,
  readStoredLanguage,
  storeLanguage,
} from "./language-choice";

const PROMPTS: Record<AppLocale, string> = {
  en: enCommon.gate.prompt,
  ko: koCommon.gate.prompt,
};

/**
 * The first screen: English or 한국어 (FR-01). The root route has no next-intl provider,
 * so the gate speaks both languages at once and uses the Next.js router.
 * With onChoose (the demo overlay) the caller owns the choice: the gate then stores
 * nothing, navigates nowhere and skips the stored-choice redirect.
 */
export function LanguageGate({
  onChoose,
}: {
  onChoose?: (locale: AppLocale) => void;
}) {
  const router = useRouter();

  useEffect(() => {
    if (onChoose) {
      return;
    }
    const stored = readStoredLanguage();
    if (stored) {
      router.replace(toLocaleRoute(stored));
    }
  }, [onChoose, router]);

  function handleChoose(locale: AppLocale) {
    if (onChoose) {
      onChoose(locale);
      return;
    }
    storeLanguage(locale);
    router.push(toLocaleRoute(locale));
  }

  return (
    <div className="flex flex-col items-center gap-8 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">
        {enCommon.app_name}
      </h1>
      <div className="flex flex-col gap-1 text-muted-foreground">
        {routing.locales.map((locale) => (
          <p key={locale} lang={locale}>
            {PROMPTS[locale]}
          </p>
        ))}
      </div>
      <div className="flex flex-wrap justify-center gap-3">
        {routing.locales.map((locale) => (
          <Button
            key={locale}
            lang={locale}
            size="lg"
            className="h-11 min-w-32 px-6 text-base"
            onClick={() => handleChoose(locale)}
          >
            {LANGUAGE_NAMES[locale]}
          </Button>
        ))}
      </div>
    </div>
  );
}

// The export uses trailing slashes, so /ko/ is the file the static host serves.
function toLocaleRoute(locale: AppLocale) {
  return `/${locale}/`;
}
