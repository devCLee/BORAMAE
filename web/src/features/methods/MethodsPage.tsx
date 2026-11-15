"use client";

import { useTranslations } from "next-intl";
import { useId } from "react";

import { Link } from "@/i18n/navigation";

import { FalseAlarmSection } from "./FalseAlarmSection";
import { SourceList } from "./SourceList";

/**
 * The Methods page (DES-023): the measured false-alarm rates, the data note, one
 * attribution per inventory entry and the AI-use note, in the UI language.
 */
export function MethodsPage() {
  const t = useTranslations("methods");

  return (
    <main
      data-testid="slot-methods"
      className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-6"
    >
      <Link
        href="/"
        className="inline-flex min-h-11 items-center self-start text-sm underline underline-offset-4"
      >
        {t("back")}
      </Link>
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-muted-foreground">{t("intro")}</p>
      </div>
      <FalseAlarmSection />
      <TextSection heading={t("data.heading")} body={t("data.model")} />
      <SourceList />
      <TextSection heading={t("ai.heading")} body={t("ai.note")} />
    </main>
  );
}

function TextSection({ heading, body }: { heading: string; body: string }) {
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <h2 id={headingId} className="text-lg font-semibold">
        {heading}
      </h2>
      <p>{body}</p>
    </section>
  );
}
