"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { Num } from "@/components/Num";
import { Term } from "@/components/Term";
import type { BoardNode, Catalog, Lang, ShareScale, TrendResult } from "@/contracts/types";
import { type Answer, type FetchError, fetchResult } from "@/lib/fetch-layer";
import { useAppStore } from "@/state/store";

import { nameOf, type NumSource, P_SHOWN, Row, SHOWN } from "./board-parts";

const DIRECTIONS = { "+": "same", "-": "opposite" } as const;

interface ArrowInputsProps {
  id: string;
  node: BoardNode;
  catalog: Catalog | undefined;
  linkSource: NumSource | null;
}

/**
 * What an arrow was tested on (DESIGN_SYSTEM.md "Case board"): the pair, the expected
 * direction, the link numbers and the trend of the node, each number through Num.
 */
export function ArrowInputs({ id, node, catalog, linkSource }: ArrowInputsProps) {
  const t = useTranslations("board");
  const lang = useLocale() as Lang;
  const { row, link } = node;
  const side = node.role === "driver" ? row.driver : row.response;
  const { n_eff: nEff } = link;
  const variable = catalog?.variables.find((candidate) => candidate.id === side.var);

  return (
    <div id={id} className="flex flex-col gap-1.5 border-t pt-2">
      <dl className="grid gap-1.5">
        <Row label={t("fields.pair")}>
          {t("pair_value", {
            driver: nameOf(catalog, row.driver.var, lang),
            response: nameOf(catalog, row.response.var, lang),
          })}
        </Row>
        <Row label={t("fields.direction")}>
          {t(`directions.${DIRECTIONS[row.expected_sign]}`)}
        </Row>
        {linkSource && link.r !== null && (
          <>
            <Row label={t("fields.lag")}>
              {t.rich("years", {
                count: link.lag_years,
                num: () => <Num value={link.lag_years} {...linkSource} />,
              })}
            </Row>
            <Row label={t("fields.overlap")}>
              <Num value={link.n_overlap} {...linkSource} />
            </Row>
            {nEff !== null && (
              <Row label={t("fields.n_eff")}>
                <Num value={nEff} options={SHOWN} {...linkSource} />
              </Row>
            )}
          </>
        )}
      </dl>
      {node.trend_key !== null && (
        <NodeTrend
          trendKey={node.trend_key}
          name={nameOf(catalog, side.var, lang)}
          shareScale={variable?.share_scale ?? null}
        />
      )}
    </div>
  );
}

interface NodeTrendProps {
  trendKey: string;
  name: string;
  shareScale: ShareScale | null;
}

/** The rate and the p-value of the node, from its stored trend result. */
function NodeTrend({ trendKey, name, shareScale }: NodeTrendProps) {
  const t = useTranslations("board");
  const tErrors = useTranslations("errors");
  const trend = useStoredTrend(trendKey);

  if (trend.isError) {
    return <p className="text-muted-foreground">{tErrors(`messages.${trend.error.code}`)}</p>;
  }
  if (trend.data === undefined) {
    return (
      <p role="status" className="text-muted-foreground">
        {t("node_loading", { name })}
      </p>
    );
  }
  const { body, meta } = trend.data;
  const source = { provenance: body.provenance, footprint: body.footprint, meta };
  const { sen } = body.stats.rates;
  const { p } = body.stats.mk;

  return (
    <dl className="grid gap-1.5">
      {sen !== null && (
        <Row label={t("fields.node_rate", { name })}>
          <Num value={sen} rate={{ unit: body.rate_unit, shareScale }} options={SHOWN} {...source} />
        </Row>
      )}
      {p !== null && (
        <Row
          label={
            <>
              <Term id="mann_kendall" /> <Term id="p_value" />
            </>
          }
        >
          <Num value={p} options={P_SHOWN} {...source} />
        </Row>
      )}
    </dl>
  );
}

/** A stored trend by its key, from the service or from the demo bundle. */
function useStoredTrend(key: string) {
  const source = useAppStore((state) => state.fetchSource);
  return useQuery<Answer<TrendResult>, FetchError>({
    queryKey: ["result", "trend", source, key],
    queryFn: () => fetchResult(source, "trend", key),
    retry: false,
    // A stored result never changes.
    staleTime: Infinity,
  });
}
