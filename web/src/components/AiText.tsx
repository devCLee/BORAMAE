"use client";

import { useQueries } from "@tanstack/react-query";
import { ExternalLinkIcon, InfoIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { Fragment, useId } from "react";

import { Term } from "@/components/Term";
import {
  openProvenance,
  type ProvenanceTarget,
} from "@/features/provenance/provenance-state";
import { useCaseBoard, useCatalog, useScan, useTrend } from "@/hooks/queries";
import { FetchError, type FetchErrorCode, fetchResult } from "@/lib/fetch-layer";
import {
  buildAllowed,
  buildCitations,
  checkText,
  type Citation,
  type GuardResult,
  type KeptSentence,
  linkedKeys,
  resolveCitations,
} from "@/lib/number-guard";
import { useAppStore } from "@/state/store";
import type { FetchSource } from "@/state/types";

export interface AiTextProps {
  /** The model text as the service sent it, unchecked. */
  text: string;
  /** The result keys that the answer used (final.result_keys). */
  resultKeys: string[];
  /** The citation IDs of the answer (final.citations). */
  citations: string[];
}

const DOI_BASE = "https://doi.org/";
/**
 * ponytail: a result key names no kind, so a key that no open panel holds is asked
 * as a trend, then as a case board, then as a scan: up to two extra not-found
 * answers. Give final.result_keys their kind if those requests start to matter.
 */
const LOADERS: ((source: FetchSource, key: string) => Promise<GuardResult>)[] = [
  async (source, key) => ({ kind: "trend", key, ...(await fetchResult(source, "trend", key)) }),
  async (source, key) => ({
    kind: "caseboard",
    key,
    ...(await fetchResult(source, "caseboard", key)),
  }),
  async (source, key) => ({ kind: "scan", key, ...(await fetchResult(source, "scan", key)) }),
];
/** After these errors another kind can still hold the key. A lost connection fails every kind. */
const OTHER_KIND_CODES = new Set<FetchErrorCode>(["server", "not_in_offline_demo"]);

interface AnswerResults {
  /** The results that the answer names. Only they give allowed values. */
  named: GuardResult[];
  /** The trends that give their provenance to the numbers of a board or a scan. */
  linked: GuardResult[];
}

/**
 * The only component that renders AI text (DES-017, TR-F-035). It shows nothing of
 * the text until the number guard has checked it, then only the kept sentences, each
 * with the AI badge, and each matched number with the provenance of its field.
 */
export function AiText({ text, resultKeys, citations }: AiTextProps) {
  const t = useTranslations("ai");
  const confirmedSpec = useAppStore((state) => state.confirmedSpec);
  const area = useAppStore((state) => state.area);
  const timeWindow = useAppStore((state) => state.window);
  const cellPreview = useAppStore((state) => state.cellPreview);
  const catalog = useCatalog();
  const results = useAnswerResults(resultKeys);

  if (results === null || catalog.isPending) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        {t("checking")}
      </p>
    );
  }
  const appState = { area, window: timeWindow, cellPreview };
  const { named, linked } = results;
  const allowed = buildAllowed(named, confirmedSpec, appState, catalog.data ?? null, linked);
  const { kept, withheld } = checkText(text, allowed);
  if (kept.length === 0) {
    // An empty text shows nothing. Otherwise the computed results stay on screen;
    // only the answer gives way (TR-F-034).
    return withheld.length === 0 ? null : (
      <p role="status" className="text-sm text-muted-foreground">
        {t("withheld")}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-2 text-sm">
      <p>
        {kept.map((sentence, index) => (
          <Sentence key={index} sentence={sentence} />
        ))}
      </p>
      <Sources citations={resolveCitations(citations, buildCitations(named))} />
    </div>
  );
}

/**
 * The results of the keys, from an open panel or loaded by key, and the trends that
 * their numbers link to (TDD Flow D step 10). Null until each one has loaded or failed.
 * A result that does not load gives no allowed values; a trend, no link.
 */
function useAnswerResults(keys: string[]): AnswerResults | null {
  const source = useAppStore((state) => state.fetchSource);
  const held = useHeldResults();
  const missing = held === null ? [] : [...new Set(keys)].filter((key) => !holds(held, key));
  const loaded = useQueries({
    queries: missing.map((key) => ({
      queryKey: ["ai-result", source, key],
      queryFn: () => loadResult(source, key),
      retry: false,
      staleTime: Infinity,
    })),
  });
  const named =
    held === null || loaded.some((query) => query.isPending)
      ? null
      : [...held, ...loaded.flatMap(({ data }) => (data === undefined ? [] : [data]))].filter(
          (result) => keys.includes(result.key),
        );
  const known = [...(held ?? []), ...(named ?? [])];
  const linkKeys = linkedKeys(named ?? []).filter((key) => !holds(known, key));
  const links = useQueries({
    queries: linkKeys.map((key) => ({
      // The query of ScanLists.tsx, so an open fallback panel shares its request.
      queryKey: ["result", "trend", source, key],
      queryFn: () => fetchResult(source, "trend", key),
      retry: false,
      staleTime: Infinity,
    })),
  });
  if (held === null || named === null || links.some((query) => query.isPending)) {
    return null;
  }
  const linkTrends = links.flatMap(({ data }, index): GuardResult[] =>
    data === undefined ? [] : [{ kind: "trend", key: linkKeys[index], ...data }],
  );
  return { named, linked: [...held, ...linkTrends] };
}

function holds(results: GuardResult[], key: string): boolean {
  return results.some((result) => result.key === key);
}

/** What the open panels show. Null while one of them loads, because it may hold a key. */
function useHeldResults(): GuardResult[] | null {
  const trend = useTrend();
  const caseboard = useCaseBoard();
  const scan = useScan();
  if (trend.isLoading || caseboard.isLoading || scan.isLoading) {
    return null;
  }
  const held: GuardResult[] = [];
  if (trend.data) {
    held.push({ kind: "trend", key: trend.data.meta.resultKey, ...trend.data });
  }
  if (caseboard.data) {
    held.push({ kind: "caseboard", key: caseboard.data.meta.resultKey, ...caseboard.data });
  }
  if (scan.data) {
    held.push({ kind: "scan", key: scan.data.meta.resultKey, ...scan.data });
  }
  return held;
}

async function loadResult(source: FetchSource, key: string): Promise<GuardResult> {
  let lastError: unknown = null;
  for (const load of LOADERS) {
    try {
      return await load(source, key);
    } catch (error) {
      if (!(error instanceof FetchError && OTHER_KIND_CODES.has(error.code))) {
        throw error;
      }
      lastError = error;
    }
  }
  throw lastError;
}

function Sentence({ sentence }: { sentence: KeptSentence }) {
  const t = useTranslations("ai");

  return (
    <>
      {/* The word and the border carry the badge, so color is not its only signal. */}
      <span className="mr-1 inline-flex items-center rounded-sm border border-current px-1 text-xs font-medium text-ai-badge">
        <span aria-hidden>{t("badge")}</span>
        <span className="sr-only">{t("badge_label")}</span>
      </span>
      {sentence.parts.map((part, index) =>
        part.source === null ? (
          <Fragment key={index}>{part.text}</Fragment>
        ) : (
          <SourcedNumber key={index} text={part.text} source={part.source} />
        ),
      )}{" "}
    </>
  );
}

/** A matched number with the info button of Num, which opens the provenance of its field. */
function SourcedNumber({ text, source }: { text: string; source: ProvenanceTarget }) {
  const t = useTranslations("provenance");

  return (
    <span className="inline-flex items-baseline gap-0.5 tabular-nums">
      {text}
      {/* The after: box widens the hit area to 44 px without moving the line. */}
      <button
        type="button"
        aria-label={t("open", { value: text })}
        onClick={(event) => openProvenance(source, event.currentTarget)}
        className="relative inline-flex size-6 shrink-0 items-center justify-center self-center rounded-sm text-muted-foreground after:absolute after:-inset-2.5 hover:text-foreground"
      >
        <InfoIcon aria-hidden className="size-3.5" />
      </button>
    </span>
  );
}

function Sources({ citations }: { citations: Citation[] }) {
  const t = useTranslations("ai");
  const labelId = useId();
  if (citations.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-baseline gap-x-2 text-xs text-muted-foreground">
      <span id={labelId} className="font-medium">
        {t("sources")}
      </span>
      <ul aria-labelledby={labelId} className="flex flex-wrap gap-x-3">
        {citations.map((citation) => (
          <li key={citation.id}>
            <Source citation={citation} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Source({ citation }: { citation: Citation }) {
  const t = useTranslations("ai");
  const tProvenance = useTranslations("provenance");

  switch (citation.kind) {
    case "glossary":
      return <Term id={citation.id} />;
    case "dataset":
      return `${citation.id} (${tProvenance("dataset_version", { version: citation.version })})`;
    case "registry": {
      const { row } = citation;
      const href = row.doi !== null ? DOI_BASE + row.doi : row.url;
      return href === null ? (
        row.citation
      ) : (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 underline underline-offset-4"
        >
          {row.citation}
          <ExternalLinkIcon aria-hidden className="size-3.5 shrink-0" />
          <span className="sr-only">{t("new_tab")}</span>
        </a>
      );
    }
  }
}
