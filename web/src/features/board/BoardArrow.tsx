"use client";

import { cn } from "cn";
import {
  BanIcon,
  ChevronDownIcon,
  CircleCheckIcon,
  CircleDashedIcon,
  ExternalLinkIcon,
  type LucideIcon,
  TriangleAlertIcon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useId, useState } from "react";

import { Num } from "@/components/Num";
import { Button } from "@/components/ui/button";
import type {
  ArrowLabel,
  BoardNode,
  Catalog,
  Lang,
  RegistryRow,
} from "@/contracts/types";

import { ArrowInputs } from "./ArrowInputs";
import { nameOf, type NumSource, P_SHOWN, Row, SHOWN, SideTitle } from "./board-parts";

const DOI_BASE = "https://doi.org/";
// ponytail: one arrow lights up every 300 ms, each over 500 ms (duration-500 below);
// DESIGN_SYSTEM.md "Motion" gives no durations.
const LIGHT_UP_STEP_MS = 300;

// Color is never the only signal: each label also has its own icon and word.
// ponytail: the icons and roles of the four labels are working values; the PRD gives none
// (DESIGN_SYSTEM.md "Case board"), and every Korean word waits for the wording review.
const LABEL_STYLES: Record<ArrowLabel, { icon: LucideIcon; role: string }> = {
  consistent: { icon: CircleCheckIcon, role: "text-foreground" },
  weak: { icon: CircleDashedIcon, role: "text-not-yet" },
  contradicts: { icon: TriangleAlertIcon, role: "text-too-short" },
  not_testable_here: { icon: BanIcon, role: "text-muted-foreground" },
};

interface BoardArrowProps {
  node: BoardNode;
  /** The place of the arrow on the board, which sets when it lights up. */
  order: number;
  isAnimated: boolean;
  catalog: Catalog | undefined;
  /** Null until the focus trend is there, and the link numbers wait for it. */
  linkSource: NumSource | null;
}

/** One arrow: its tested link, its source, and a toggle that opens its inputs. */
export function BoardArrow({ node, order, isAnimated, catalog, linkSource }: BoardArrowProps) {
  const t = useTranslations("board");
  const lang = useLocale() as Lang;
  const titleId = useId();
  const inputsId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const { row, link } = node;
  const side = node.role === "driver" ? row.driver : row.response;
  const reasonKey = `reasons.${link.reason}`;

  return (
    <li
      aria-labelledby={titleId}
      style={isAnimated ? { animationDelay: `${order * LIGHT_UP_STEP_MS}ms` } : undefined}
      className={cn(
        "flex flex-col gap-2 rounded-lg border bg-card p-3 text-sm text-card-foreground",
        isAnimated && "animate-in fade-in fill-mode-backwards duration-500",
      )}
    >
      <p id={titleId} className="font-medium">
        <SideTitle side={side} catalog={catalog} />
      </p>
      <p>{row.mechanism[lang]}</p>
      <dl className="grid gap-1.5">
        <Row label={t("fields.link")}>
          <span className="inline-flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
            {link.label !== null && <LabelChip label={link.label} />}
            {linkSource && <LinkNumbers r={link.r} p={link.p} source={linkSource} />}
          </span>
        </Row>
        <Row label={t("fields.scale")}>{row.scale}</Row>
        <Row label={t("fields.status")}>{t(`statuses.${row.status}`)}</Row>
        <Row label={t("fields.source")}>
          <SourceLink row={row} />
        </Row>
      </dl>
      {link.reason !== null && (
        <p className="text-muted-foreground">
          {t.has(reasonKey) ? t(reasonKey) : t("reasons.other")}
        </p>
      )}
      <Button
        variant="ghost"
        aria-expanded={isOpen}
        aria-controls={isOpen ? inputsId : undefined}
        onClick={() => setIsOpen((wasOpen) => !wasOpen)}
        className="h-auto min-h-11 self-start text-left whitespace-normal"
      >
        <ChevronDownIcon aria-hidden className={cn(isOpen && "rotate-180")} />
        {t("open_inputs", { name: nameOf(catalog, side.var, lang) })}
      </Button>
      {isOpen && (
        <ArrowInputs id={inputsId} node={node} catalog={catalog} linkSource={linkSource} />
      )}
    </li>
  );
}

function LabelChip({ label }: { label: ArrowLabel }) {
  const t = useTranslations("board");
  const { icon: Icon, role } = LABEL_STYLES[label];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-current px-2.5 py-0.5 font-medium",
        role,
      )}
    >
      <Icon aria-hidden className="size-4" />
      {t(`labels.${label}`)}
    </span>
  );
}

function LinkNumbers({ r, p, source }: { r: number | null; p: number | null; source: NumSource }) {
  const t = useTranslations("board");

  return (
    <>
      {r !== null && (
        <span>{t.rich("numbers.r", { num: () => <Num value={r} options={SHOWN} {...source} /> })}</span>
      )}
      {p !== null && (
        <span>{t.rich("numbers.p", { num: () => <Num value={p} options={P_SHOWN} {...source} /> })}</span>
      )}
    </>
  );
}

function SourceLink({ row }: { row: RegistryRow }) {
  const t = useTranslations("board");
  const href = row.doi !== null ? DOI_BASE + row.doi : row.url;

  return (
    <>
      {href === null ? (
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
      )}
      {row.doi !== null && (
        <span className="block text-xs text-muted-foreground">{t("doi", { doi: row.doi })}</span>
      )}
    </>
  );
}
