"use client";

import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import type { RequestMeta } from "@/contracts/types";
import { formatMegabytes, formatMonth } from "@/lib/format";

import type { ProvenanceTarget } from "./provenance-state";

/** The record of FR-26: dataset, access path, period, cells, method, data moved, compute location. */
export function ProvenanceDetails({ target }: { target: ProvenanceTarget }) {
  const t = useTranslations("provenance");
  const locale = useLocale();
  const { provenance, footprint, meta } = target;
  const methodKey = `methods.${provenance.method}`;

  return (
    <div className="flex flex-col gap-4 px-4 pb-4 text-sm">
      {provenance.data_kind === "model" && (
        <p className="rounded-md bg-muted p-3">
          <span className="block font-medium">{t("model.label")}</span>
          {t("model.observing_system")}
        </p>
      )}
      <dl className="grid gap-3">
        <Field label={t("fields.dataset")}>
          <code className="break-all">{provenance.dataset_id}</code>{" "}
          {t("dataset_version", { version: provenance.dataset_version })}
        </Field>
        <Field label={t("fields.access_path")}>
          <code className="break-all">{provenance.access_path}</code>
        </Field>
        <Field label={t("fields.period")}>
          {t("period_range", {
            start: formatMonth(provenance.period.start, locale),
            end: formatMonth(provenance.period.end, locale),
          })}
        </Field>
        <Field label={t("fields.cells")}>
          {t("cell_count", { count: provenance.cells.length })}{" "}
          <code className="break-all">
            {provenance.cells.map((cell) => `[${cell.join(", ")}]`).join(" ")}
          </code>
        </Field>
        <Field label={t("fields.method")}>
          {t.has(methodKey) ? t(methodKey) : provenance.method}
        </Field>
        <Field label={t("fields.data_moved")}>
          {footprint && (
            <p>
              {t("footprint", {
                chunks: footprint.chunk_count,
                size: formatMegabytes(footprint.stored_bytes, locale),
              })}
            </p>
          )}
          {meta && <RequestFacts meta={meta} />}
        </Field>
        <Field label={t("fields.compute_location")}>
          <code>{provenance.compute_location}</code>
        </Field>
        {provenance.day_basis === "UTC" && (
          <Field label={t("fields.day_basis")}>{t("day_basis_utc")}</Field>
        )}
      </dl>
      {meta && (
        <a
          href={meta.sourceUrl}
          download
          className="inline-flex min-h-11 items-center self-start font-medium underline underline-offset-4"
        >
          {t("download")}
        </a>
      )}
    </div>
  );
}

/** The facts of the request that answered the number, as the meta holds them (TR-O-003). */
function RequestFacts({ meta }: { meta: RequestMeta }) {
  const t = useTranslations("provenance");

  return (
    <>
      {meta.bytesFetched !== null && (
        <p>{t("request.bytes_fetched", { bytes: meta.bytesFetched })}</p>
      )}
      {meta.cache !== null && (
        <p>{t("request.cache", { status: meta.cache })}</p>
      )}
      {meta.requestId !== null && (
        <p>
          {t("request.request_id")} <code>{meta.requestId}</code>
        </p>
      )}
    </>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
