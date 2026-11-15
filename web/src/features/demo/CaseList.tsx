"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef } from "react";

import { Button } from "@/components/ui/button";
import type { Lang } from "@/contracts/types";
import { fetchManifest } from "@/lib/fetch-layer";

import { DEMO_CASES } from "./demo-content";
import { startCase } from "./play-step";

/** The demo cases that the bundle holds, behind the demo door while no case runs. */
export function CaseList() {
  const t = useTranslations("demo.cases");
  const locale = useLocale() as Lang;
  const headingId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  // /demo/manifest.json answers 404 until export-demo runs; the list then says so.
  const manifest = useQuery({
    queryKey: ["demo-manifest"],
    queryFn: fetchManifest,
    retry: false,
    staleTime: Infinity,
  });
  const bundled = DEMO_CASES.filter((demoCase) =>
    manifest.data?.cases.some(({ case_id }) => case_id === demoCase.id),
  );

  useEffect(() => {
    // The door or the player that held the focus is gone.
    headingRef.current?.focus();
  }, []);

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-2 border-b bg-background px-4 py-3"
    >
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className="text-sm font-semibold"
      >
        {t("heading")}
      </h2>
      {manifest.isPending && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("loading")}
        </p>
      )}
      {manifest.isError && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("missing")}
        </p>
      )}
      <ul className="flex flex-wrap gap-2">
        {bundled.map((demoCase) => (
          <li key={demoCase.id}>
            <Button
              variant="outline"
              className="h-auto min-h-11 flex-col items-start py-2 text-left whitespace-normal"
              onClick={() => startCase(demoCase.id)}
            >
              <span>{demoCase.question[locale]}</span>{" "}
              <span className="text-xs text-muted-foreground">
                {t(`plays_in.${demoCase.lang}`)}
              </span>
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
