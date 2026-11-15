"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { type MouseEvent, useId } from "react";

import { Num } from "@/components/Num";
import { Term } from "@/components/Term";
import { Button } from "@/components/ui/button";
import { VerdictChip } from "@/components/VerdictChip";
import type {
  Catalog,
  CatalogVariable,
  Lang,
  NearbyArea,
  NearbyNote,
  ScanHit,
  TrendResult,
  Verdict,
} from "@/contracts/types";
import { runAtCell } from "@/features/map/use-map-markers";
import { type Answer, type FetchError, fetchResult } from "@/lib/fetch-layer";
import { formatMonth } from "@/lib/format";
import { actions, useAppStore } from "@/state/store";

// The same two significant digits as the rates of the verdict card.
const SHOWN = { maximumSignificantDigits: 2 } satisfies Intl.NumberFormatOptions;

/** The variables and areas of a scan come from the service; the browser selects none (TR-Q-002). */
export function HitList({ hits, catalog }: { hits: ScanHit[]; catalog: Catalog | undefined }) {
  const t = useTranslations("fallback.hits");
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <h4 id={headingId} className="text-sm font-medium">
        {t("heading")}
      </h4>
      {hits.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("empty")}</p>
      ) : (
        <ul aria-labelledby={headingId} className="flex flex-col gap-2">
          {hits.map((hit) => (
            <HitItem key={hit.var} hit={hit} variable={findVariable(catalog, hit.var)} />
          ))}
        </ul>
      )}
    </section>
  );
}

export function NearbyList({ nearby, note }: { nearby: NearbyArea[]; note: NearbyNote | null }) {
  const t = useTranslations("fallback.nearby");
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <h4 id={headingId} className="text-sm font-medium">
        {t("heading")}
      </h4>
      {nearby.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {note === null ? t("empty") : t(`notes.${note}`)}
        </p>
      ) : (
        <ul aria-labelledby={headingId} className="flex flex-col gap-2">
          {nearby.map((area) => (
            <NearbyItem key={`${area.lat_i}-${area.lon_i}`} area={area} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** A variable name through Term, or its ID while the catalog is not there. */
export function VariableName({ id, variable }: { id: string; variable: CatalogVariable | undefined }) {
  const lang = useLocale() as Lang;
  return variable ? (
    <Term id={variable.id} definition={variable.definition}>
      {variable.name[lang]}
    </Term>
  ) : (
    id
  );
}

export function findVariable(catalog: Catalog | undefined, id: string) {
  return catalog?.variables.find((candidate) => candidate.id === id);
}

/**
 * The case panel root takes the focus of a control that leaves the screen
 * (CasePanel.tsx). Choosing an entry clears or replaces the result, so the entry leaves.
 */
function focusCasePanel(event: MouseEvent<HTMLElement>) {
  event.currentTarget.closest<HTMLElement>('[tabindex="-1"]')?.focus();
}

function HitItem({ hit, variable }: { hit: ScanHit; variable: CatalogVariable | undefined }) {
  const t = useTranslations("fallback.hits");
  const lang = useLocale() as Lang;

  return (
    <li className="flex flex-wrap items-center gap-2 rounded-lg border p-3 text-sm">
      <VerdictChip verdict={toVerdict(hit.sign)} />
      <VariableName id={hit.var} variable={variable} />
      <HitRate hit={hit} variable={variable} />
      <span className="text-xs text-muted-foreground">
        <Term id="found_by_scan" />
      </span>
      <Button
        variant="outline"
        className="min-h-11"
        onClick={(event) => {
          focusCasePanel(event);
          // A new variable clears the confirmation, so the read-back asks again (DES-002).
          actions.editDraft({ var: hit.var, metric: { id: hit.metric_id } }, "user");
        }}
      >
        {t("choose", { variable: variable?.name[lang] ?? hit.var })}
      </Button>
    </li>
  );
}

/**
 * ponytail: the scan result holds no provenance, so a hit rate shows once the stored
 * trend result of the hit (its trend_key) gives one (FR-26). A demo bundle without that
 * file shows the hit without its rate; add the hit trends to referenced.trend to fix it.
 */
function HitRate({ hit, variable }: { hit: ScanHit; variable: CatalogVariable | undefined }) {
  const source = useAppStore((state) => state.fetchSource);
  const stored = useQuery<Answer<TrendResult>, FetchError>({
    queryKey: ["result", "trend", source, hit.trend_key],
    queryFn: () => fetchResult(source, "trend", hit.trend_key),
    retry: false,
    staleTime: Infinity,
  });
  if (hit.rate_per_decade === null || stored.data === undefined) {
    return null;
  }
  return (
    <Num
      value={hit.rate_per_decade}
      rate={{ unit: hit.rate_unit, shareScale: variable?.share_scale ?? null }}
      options={SHOWN}
      provenance={stored.data.body.provenance}
      footprint={stored.data.body.footprint}
      meta={stored.data.meta}
    />
  );
}

function NearbyItem({ area }: { area: NearbyArea }) {
  const t = useTranslations("fallback.nearby");
  const locale = useLocale();
  const lang = locale as Lang;
  const point = { lat: area.lat, lon: area.lon };
  const [start, end] = area.grid_window;

  // ponytail: the distance and the grid window are positions, not data values, and the
  // scan result gives them no provenance record, so they skip Num (TRD Q-42 is open).
  return (
    <li className="flex flex-col gap-2 rounded-lg border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictChip verdict={toVerdict(area.sign)} />
        <span>{t("distance", { distance: area.distance_km })}</span>
        <span className="text-muted-foreground">
          {t("grid_window", { start: String(start), end: formatMonth(end, locale) })}
        </span>
        <span className="text-xs text-muted-foreground">
          <Term id="found_by_scan" />
        </span>
      </div>
      {area.is_opposite && (
        <p>
          <span className="font-medium">{t("opposite")}</span>
          {area.mechanism && <span className="block text-muted-foreground">{area.mechanism[lang]}</span>}
        </p>
      )}
      <Button
        variant="outline"
        className="min-h-11 self-start"
        onClick={(event) => {
          focusCasePanel(event);
          // A nearby click confirms the run, as a nearby pin on the map does (Q-016).
          runAtCell(point);
          actions.setMapTarget({ center: point, zoom: null });
        }}
      >
        {t("run", { distance: area.distance_km })}
      </Button>
    </li>
  );
}

/** Every listed entry is significant, so its sign is its direction. */
function toVerdict(sign: ScanHit["sign"]): Verdict {
  if (sign > 0) {
    return "significant_rise";
  }
  return sign < 0 ? "significant_fall" : "no_trend";
}
