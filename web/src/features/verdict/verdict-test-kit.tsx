/**
 * Helpers of the verdict card tests: the render with the sample catalog, the rows
 * of the card and the numbers that its Num elements show.
 */
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import type { RequestMeta, TrendResult } from "@/contracts/types";
import { ProvenanceDrawer } from "@/features/provenance/ProvenanceDrawer";
import { messages } from "@/i18n/messages";
import { catalog } from "@/test/fixtures";

import { VerdictCard } from "./VerdictCard";

const RESULT_KEY = "b5bae5463e95eff888bca78a896bf62a";
const NUM_PREFIX = "Source of ";
const NUM_BUTTONS = `button[aria-label^="${NUM_PREFIX}"], button[aria-label$="의 출처"]`;

/** The facts of the request. sourceUrl is the file that the download link of the drawer names. */
export const META: RequestMeta = {
  resultKey: RESULT_KEY,
  requestId: "req-verdict-1",
  cache: "hit",
  bytesFetched: 0,
  serverTiming: null,
  usedContainingCell: false,
  sourceUrl: `/r/trend/${RESULT_KEY}.json`,
};

export function renderCard(
  result: TrendResult,
  { locale = "en", meta = META }: { locale?: "en" | "ko"; meta?: RequestMeta } = {},
) {
  return render(
    <NextIntlClientProvider locale={locale} messages={messages[locale]} timeZone="UTC">
      <VerdictCard
        result={result}
        meta={meta}
        variable={findById(catalog.variables, result.spec.var)}
        metric={findById(catalog.metrics, result.spec.metric.id)}
      />
      <ProvenanceDrawer />
    </NextIntlClientProvider>,
  );
}

/** The value cell of the row whose label starts with the text. */
export function definitionOf(label: string): HTMLElement | null {
  const term = screen
    .getAllByRole("term")
    .find((candidate) => candidate.textContent?.startsWith(label));
  return (term?.nextElementSibling as HTMLElement | null) ?? null;
}

/** The Num elements inside an element. */
export function numsIn(element: HTMLElement | null): Element[] {
  return [...(element?.querySelectorAll(NUM_BUTTONS) ?? [])];
}

/** The shown texts of the card that no number of the file gives at their shown precision. */
export function numbersMissingFrom(file: unknown): string[] {
  const fileNumbers = numbersIn(file);
  return screen
    .getAllByRole("button", { name: new RegExp(`^${NUM_PREFIX}`) })
    .map((button) => button.getAttribute("aria-label")?.slice(NUM_PREFIX.length) ?? "")
    .filter((shown) => !isInFile(shown, fileNumbers));
}

/** The text of the element once every Num is taken out. */
export function textOutsideNum(element: HTMLElement): string {
  const copy = element.cloneNode(true) as HTMLElement;
  copy.querySelectorAll(NUM_BUTTONS).forEach((button) => button.parentElement?.remove());
  return copy.textContent ?? "";
}

function findById<T extends { id: string }>(items: T[], id: string): T {
  const item = items.find((candidate) => candidate.id === id);
  if (item === undefined) {
    throw new Error(`The sample catalog holds no ${id}.`);
  }
  return item;
}

/** Every number of a result file. A string such as "2026-09" or "0.1" gives its numbers too. */
function numbersIn(value: unknown): number[] {
  if (typeof value === "number") {
    return [value];
  }
  if (typeof value === "string") {
    return (value.match(/\d+(?:\.\d+)?/g) ?? []).map(Number);
  }
  if (value !== null && typeof value === "object") {
    return Object.values(value).flatMap(numbersIn);
  }
  return [];
}

function isInFile(shown: string, fileNumbers: number[]): boolean {
  const text = shown.match(/-?\d[\d,]*(?:\.\d+)?%?/)?.[0] ?? "";
  const scale = text.endsWith("%") ? 100 : 1;
  const digits = text.replace(/[,%]/g, "");
  const decimals = digits.split(".")[1]?.length ?? 0;
  const value = Number(digits) / scale;
  // One unit of the last shown digit covers a rounded and a truncated value.
  const tolerance = 10 ** -decimals / scale;
  return fileNumbers.some((number) => Math.abs(number - value) <= tolerance * (1 + 1e-9));
}
