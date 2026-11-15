"use client";

import { ExternalLinkIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useId } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useNews } from "@/hooks/queries";

import { toNewsParams } from "./news-params";

const MAX_ITEMS = 10;
const SAFE_URL = /^https?:\/\//;

/** Non-NASA news for the case on screen, as labeled context (FR-20). No AI summary. */
export function NewsPanel({
  variableName,
  placeName,
  window,
}: {
  variableName: string;
  placeName: string | null;
  window: [number, string];
}) {
  const t = useTranslations("case");
  const locale = useLocale();
  const headingId = useId();
  const news = useNews(toNewsParams(variableName, placeName, window, new Date()));
  // A query that never asks, as with the bundled demo, shows no panel.
  if (news.isPending && news.fetchStatus === "idle") {
    return null;
  }
  const items = news.data?.items.filter((item) => SAFE_URL.test(item.url)).slice(0, MAX_ITEMS);
  const formatDate = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" });

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2 text-sm">
      <h3 id={headingId} className="text-base font-medium">
        {t("news.heading")}
      </h3>
      <p className="text-muted-foreground">{t("news.label")}</p>
      {news.isPending && (
        <div role="status" aria-label={t("news.loading")} className="flex flex-col gap-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      )}
      {news.isError && <p role="alert">{t("news.error")}</p>}
      {items?.length === 0 && <p>{t("news.empty")}</p>}
      {items !== undefined && items.length > 0 && (
        <ul aria-labelledby={headingId} className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={item.url} className="flex flex-col gap-0.5">
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 self-start underline underline-offset-4"
              >
                {item.title}
                <ExternalLinkIcon aria-hidden className="size-3.5 shrink-0" />
                <span className="sr-only">{t("new_tab")}</span>
              </a>
              <span className="text-muted-foreground">
                {item.source} · {formatDate.format(new Date(item.published))}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
