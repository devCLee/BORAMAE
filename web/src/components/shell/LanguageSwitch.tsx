"use client";

import { useLocale } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";

import { type AppLocale, LANGUAGE_NAMES, storeLanguage } from "./language-choice";

/** Opens the same route in the other language and remembers that choice (TR-F-001). */
export function LanguageSwitch() {
  const target: AppLocale = useLocale() === "ko" ? "en" : "ko";
  const pathname = usePathname();

  return (
    <Link
      href={pathname}
      locale={target}
      lang={target}
      onClick={() => storeLanguage(target)}
      className="inline-flex h-11 items-center rounded-md px-3 text-sm font-medium hover:bg-muted"
    >
      {LANGUAGE_NAMES[target]}
    </Link>
  );
}
