"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId, type ReactNode } from "react";

import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Lang, LocalizedText } from "@/contracts/types";
import type glossaryMessages from "@/messages/en/glossary.json";

export type GlossaryTerm = keyof (typeof glossaryMessages)["terms"];

/**
 * A glossary entry, whose trigger text defaults to the entry name, or a catalog
 * variable (its ID) with its catalog definition and the caller's name text.
 */
type TermProps =
  | { id: GlossaryTerm; definition?: undefined; children?: ReactNode }
  | { id: string; definition: LocalizedText; children: ReactNode };

/** A link from a variable name or a statistic to its plain definition (FR-27). */
export function Term({ id, definition, children }: TermProps) {
  const t = useTranslations("glossary");
  const lang = useLocale() as Lang;
  const titleId = useId();
  const name = definition ? children : (children ?? t(`terms.${id}.name`));

  return (
    <Popover>
      <PopoverTrigger className="cursor-help rounded-sm underline decoration-dotted underline-offset-4">
        {name}
      </PopoverTrigger>
      <PopoverContent aria-labelledby={titleId}>
        <PopoverTitle id={titleId}>
          {definition ? name : t(`terms.${id}.name`)}
        </PopoverTitle>
        {definition ? (
          <PopoverDescription>{definition[lang]}</PopoverDescription>
        ) : (
          <>
            <PopoverDescription>{t(`terms.${id}.definition`)}</PopoverDescription>
            <p>
              <span className="font-medium">{t("meaning_label")}</span>{" "}
              {t(`terms.${id}.meaning`)}
            </p>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
