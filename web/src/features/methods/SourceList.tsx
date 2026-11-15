"use client";

import { useTranslations } from "next-intl";
import { useId } from "react";

import licenses from "@content/licenses.json";
import type { LicenseEntry } from "@/contracts/types";

// ponytail: no document fixes the inventory kinds; these four groups are a working value.
// An entry of another kind shows in no group, so the page test that counts one
// attribution per entry fails on it. Add the kind here and in the messages first.
const KINDS = ["data", "font", "code", "literature"] as const;
const ENTRIES: LicenseEntry[] = licenses;

type Kind = (typeof KINDS)[number];

/** One attribution per entry of content/licenses.json (TR-O-004), grouped by kind. */
export function SourceList() {
  const t = useTranslations("methods.sources");
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-4">
      <h2 id={headingId} className="text-lg font-semibold">
        {t("heading")}
      </h2>
      <p>{t("intro")}</p>
      {KINDS.map((kind) => (
        <SourceGroup key={kind} kind={kind} />
      ))}
    </section>
  );
}

function SourceGroup({ kind }: { kind: Kind }) {
  const t = useTranslations("methods.sources");
  const headingId = useId();

  return (
    <div className="flex flex-col gap-2">
      <h3 id={headingId} className="font-medium">
        {t(`kinds.${kind}`)}
      </h3>
      <ul aria-labelledby={headingId} className="flex flex-col gap-3 text-sm">
        {ENTRIES.filter((entry) => entry.kind === kind).map((entry) => (
          <li key={entry.name} className="flex flex-col">
            <a
              href={entry.url}
              className="inline-flex min-h-11 items-center self-start font-medium underline underline-offset-4"
            >
              {entry.name}
            </a>
            <p className="text-muted-foreground">
              {t("license", { license: entry.license })}
            </p>
            <p>{entry.citation}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
