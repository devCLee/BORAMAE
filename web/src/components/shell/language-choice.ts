import { hasLocale } from "next-intl";

import { routing } from "@/i18n/routing";
import enCommon from "@/messages/en/common.json";
import koCommon from "@/messages/ko/common.json";

export type AppLocale = (typeof routing.locales)[number];

export const LANGUAGE_STORAGE_KEY = "boramae.lang";

/** Each language is named in its own words, whatever the language of the page. */
export const LANGUAGE_NAMES: Record<AppLocale, string> = {
  en: enCommon.language_name,
  ko: koCommon.language_name,
};

export function readStoredLanguage(): AppLocale | null {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return hasLocale(routing.locales, stored) ? stored : null;
  } catch {
    // Blocked storage (private window, site settings) reads as no choice, so the gate shows.
    return null;
  }
}

export function storeLanguage(locale: AppLocale): void {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, locale);
  } catch {
    // Blocked or full storage: the route still carries the language for this visit.
  }
}
