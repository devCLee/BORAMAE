"use client";

import { useLocale } from "next-intl";
import type { ReactNode } from "react";

import { Term } from "@/components/Term";
import type {
  Catalog,
  Footprint,
  Lang,
  Provenance,
  RequestMeta,
  RowSide,
} from "@/contracts/types";

/** What a Num of the board needs besides its value. */
export interface NumSource {
  provenance: Provenance;
  footprint: Footprint;
  meta: RequestMeta | null;
}

// ponytail: two significant digits, and a p-value cut rather than rounded, as on the
// verdict card (VerdictStats.tsx). No document fixes the precision (Q-42 is open).
export const SHOWN = { maximumSignificantDigits: 2 } satisfies Intl.NumberFormatOptions;
export const P_SHOWN = {
  maximumSignificantDigits: 2,
  roundingMode: "trunc",
} satisfies Intl.NumberFormatOptions;

/** A variable and its metric, each a link to its catalog definition (FR-27). */
export function SideTitle({ side, catalog }: { side: RowSide; catalog: Catalog | undefined }) {
  const lang = useLocale() as Lang;
  const variable = catalog?.variables.find((candidate) => candidate.id === side.var);
  const metric = catalog?.metrics.find((candidate) => candidate.id === side.metric.id);

  return (
    <>
      {variable ? (
        <Term id={variable.id} definition={variable.definition}>
          {variable.name[lang]}
        </Term>
      ) : (
        side.var
      )}
      {metric && (
        <>
          {" · "}
          <Term id={metric.id} definition={metric.definition}>
            {metric.name[lang]}
          </Term>
        </>
      )}
    </>
  );
}

/** The catalog name of a variable, or its ID when the catalog has not loaded. */
export function nameOf(catalog: Catalog | undefined, id: string, lang: Lang): string {
  return catalog?.variables.find((candidate) => candidate.id === id)?.name[lang] ?? id;
}

export function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}
