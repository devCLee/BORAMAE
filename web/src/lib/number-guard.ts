/**
 * The number guard (DES-017, FR-24): every number in AI text must equal an allowed
 * value after rounding to the decimals that the text shows, directly or after one
 * conversion of the units table, or its sentence is withheld. number-guard-cite.ts
 * resolves the citation IDs of an answer.
 *
 * It keeps the app's own screen clean. It is not a security control: the agent
 * socket carries the model text unchecked (DEC-005). It does not see a number written
 * in words; the system prompt of the guide asks for digits.
 */
import type { Catalog, DraftSpec, RequestMeta, ResultKind } from "@/contracts/types";
import type { ProvenanceTarget } from "@/features/provenance/provenance-state";
import type { AppState } from "@/state/types";

import type { ResultByKind } from "./fetch-layer";
import {
  appStateFields,
  caseBoardFields,
  type GuardField,
  type RecordFields,
  scanFields,
  specFields,
  trendFields,
  type YearRange,
} from "./guard-fields";
import {
  CITATION_MARKER,
  extractNumbers,
  hasStrayDigit,
  maskIdentifiers,
  type ShownNumber,
  splitSentences,
  toHalfWidth,
} from "./number-guard-text";
import { type Conversion, CONVERSIONS, convert } from "./units";

export { buildCitations, type Citation, resolveCitations } from "./number-guard-cite";
export { extractNumbers, maskIdentifiers, splitSentences } from "./number-guard-text";

/** A loaded result, by the key that the answer names. */
export type GuardResult = {
  [K in ResultKind]: { kind: K; key: string; body: ResultByKind[K]; meta: RequestMeta | null };
}[ResultKind];

export type GuardState = Pick<AppState, "area" | "window" | "cellPreview">;

export interface AllowedValue {
  field: string;
  value: number;
  /** The value, and the value after each conversion of the units table that applies. */
  candidates: number[];
  isPValue: boolean;
  /** A share of 1, which a percent sign reads as its share of 100. */
  isFraction: boolean;
  /** The provenance that the number links to. Null for a value that the user set. */
  source: ProvenanceTarget | null;
}

export interface Allowed {
  values: AllowedValue[];
  years: YearRange[];
  /** Catalog names and dataset IDs, masked before extraction. */
  names: string[];
}

/** A piece of a kept sentence. A matched number with a provenance record has its source. */
export interface SentencePart {
  text: string;
  source: ProvenanceTarget | null;
}

export interface KeptSentence {
  /** The sentence without its citation markers. */
  text: string;
  parts: SentencePart[];
}

export interface CheckedText {
  kept: KeptSentence[];
  withheld: string[];
}

// ponytail: the rounding rule (half a unit of the last digit shown), the unit list of
// the year rule, the multiplier list and the sign rule are Proposed working values (TRD Q-03).
const HALF_UNIT = 0.5;
const PERCENT = 100;
/** Room for binary rounding: 0.315 - 0.31 is a little more than 0.005 in a double. */
const FLOAT_SLACK = 1 + 1e-9;
// A unit after a 4-digit number makes it a value, not a year. "in" stays off the list,
// because prose puts it after a year; the m of "2000 more" is no unit.
const UNIT_AFTER =
  /^\s*(?:[°℃℉%‰]|(?:mm|cm|km|kg|m|mi|miles?|(?:milli|centi|kilo)?met(?:er|re)s?|inch(?:es)?|hours?|hrs?|days?|years?|yrs?|months?|times|cells?|points?|percent|degrees?|DU|hPa|[CFK])(?![A-Za-z])|일|도|개월|개|회|번|배|시간|미터|밀리미터|센티미터|킬로미터|퍼센트|포인트)/;
// A power or a multiplier scales the number before it, as in 10^6, 3e6, 3.3 million or
// 3.3만, so the guard would read a number that the screen does not show.
const SCALED_AFTER =
  /^(?:\s*[\^⁰¹²³⁴⁵⁶⁷⁸⁹⁻]|[eE][+−-]?\d|\s*(?:hundred|thousand|million|billion|trillion)s?(?![A-Za-z])|[백천만억조])/;
const YEAR_MATCH = { source: null };

/** A matched number, or a citation marker that the kept sentence drops. */
interface Span {
  start: number;
  end: number;
  source: ProvenanceTarget | null;
  isDropped: boolean;
}

/**
 * The allowed values of an answer: the named fields of the results that it names,
 * the confirmed spec and the app state. The catalog gives the data unit of a
 * threshold and the names to mask. A linked trend, such as the focus of a named
 * board, gives the provenance of a number and no allowed value.
 */
export function buildAllowed(
  results: GuardResult[],
  confirmedSpec: DraftSpec | null,
  appState: GuardState,
  catalog: Catalog | null,
  linked: GuardResult[] = [],
): Allowed {
  const trends = new Map(
    [...linked, ...results].flatMap((result) =>
      result.kind === "trend" ? [[result.key, toTarget(result)] as const] : [],
    ),
  );
  const records: RecordFields[] = [
    ...results.map((result) => fieldsOf(result, catalog)),
    { fields: confirmedSpec === null ? [] : specFields(confirmedSpec, catalog), years: [] },
    appStateFields(appState),
  ];
  return {
    values: records.flatMap(({ fields }) => fields.map((field) => toAllowedValue(field, trends))),
    years: records.flatMap(({ years }) => years),
    names: namesOf(results, catalog),
  };
}

/** The trend keys whose provenance the numbers of the results carry, once each. */
export function linkedKeys(results: GuardResult[]): string[] {
  const links = results.flatMap((result) => fieldsOf(result, null).fields.map(({ link }) => link));
  return [...new Set(links.filter((link) => link !== undefined))];
}

/** For a news or paper summary: only the numbers of the cited item pass (FR-24). */
export function buildAllowedFromText(itemText: string): Allowed {
  const values = extractNumbers(maskIdentifiers(itemText, [])).map(({ value }) => ({
    field: "item",
    value,
    candidates: [value],
    isPValue: false,
    isFraction: false,
    source: null,
  }));
  return { values, years: [], names: [] };
}

/** Splits the text and withholds each sentence with a number that matches no allowed value. */
export function checkText(text: string, allowed: Allowed): CheckedText {
  const checked: CheckedText = { kept: [], withheld: [] };
  for (const sentence of splitSentences(text)) {
    const parts = checkSentence(sentence, allowed);
    if (parts === null) {
      checked.withheld.push(sentence);
    } else if (parts.length > 0) {
      checked.kept.push({ text: parts.map((part) => part.text).join(""), parts });
    }
  }
  return checked;
}

function fieldsOf(result: GuardResult, catalog: Catalog | null): RecordFields {
  switch (result.kind) {
    case "trend":
      return trendFields(result.body, result.key, catalog);
    case "caseboard":
      return caseBoardFields(result.body, catalog);
    case "scan":
      return scanFields(result.body, catalog);
  }
}

function toAllowedValue(
  field: GuardField,
  trends: ReadonlyMap<string, ProvenanceTarget>,
): AllowedValue {
  const conversions = conversionsFor(field.unit, field.scale ?? "level");
  return {
    field: field.name,
    value: field.value,
    candidates: [field.value, ...conversions.map((conversion) => convert(field.value, conversion))],
    isPValue: field.isPValue === true,
    isFraction: field.isFraction === true || conversions.includes(CONVERSIONS.share_fraction),
    source: field.link === undefined ? null : (trends.get(field.link) ?? null),
  };
}

/**
 * The conversions of the units table from the unit, or from its numerator, so that
 * mm/day converts as mm. An offset never applies to a change, and a level whose unit
 * has one takes it: 43.3 °C is 110 °F, and a rate of 0.31 °C is 0.56 °F.
 * ponytail: one conversion and no chain is a Proposed working value (TRD Q-03); a
 * unit with no row in the units table gets no conversion.
 */
function conversionsFor(unit: string | undefined, scale: "level" | "change"): Conversion[] {
  const base = unit?.split("/")[0];
  const ofUnit: Conversion[] = Object.values(CONVERSIONS).filter(({ from }) => from === base);
  const hasOffset = ofUnit.some(({ offset }) => offset !== 0);
  return ofUnit.filter(({ offset }) =>
    scale === "change" ? offset === 0 : !hasOffset || offset !== 0,
  );
}

function namesOf(results: GuardResult[], catalog: Catalog | null): string[] {
  const entries = catalog === null ? [] : [...catalog.variables, ...catalog.metrics];
  const datasets = [
    ...(catalog === null ? [] : [catalog.datasets.daily, catalog.datasets.monthly]),
    ...results.flatMap((result) => (result.kind === "trend" ? [result.body.provenance] : [])),
  ];
  return [
    ...entries.flatMap(({ name }) => [name.en, name.ko]),
    ...datasets.flatMap(({ dataset_id: id, dataset_version: version }) => [id, version]),
  ];
}

/** The parts of a sentence whose every number matches, or null. Its citation markers drop out. */
function checkSentence(sentence: string, allowed: Allowed): SentencePart[] | null {
  const masked = maskIdentifiers(sentence, allowed.names);
  const numbers = extractNumbers(masked);
  if (hasStrayDigit(masked, numbers)) {
    return null;
  }
  const spans: Span[] = [];
  for (const shown of numbers) {
    const match = matchNumber(shown, masked.slice(shown.end), allowed);
    if (match === undefined) {
      return null;
    }
    spans.push({ start: shown.start, end: shown.end, source: match.source, isDropped: false });
  }
  // The mask reads full-width brackets as markers, so the drop reads them the same way.
  for (const marker of toHalfWidth(sentence).matchAll(CITATION_MARKER)) {
    const end = marker.index + marker[0].length;
    spans.push({ start: marker.index, end, source: null, isDropped: true });
  }
  spans.sort((first, second) => first.start - second.start);
  const parts: SentencePart[] = [];
  let at = 0;
  for (const span of spans) {
    parts.push({ text: sentence.slice(at, span.start), source: null });
    if (!span.isDropped) {
      parts.push({ text: sentence.slice(span.start, span.end), source: span.source });
    }
    at = span.end;
  }
  parts.push({ text: sentence.slice(at), source: null });
  return parts.filter((part) => part.text !== "");
}

function matchNumber(
  shown: ShownNumber,
  after: string,
  allowed: Allowed,
): { source: ProvenanceTarget | null } | undefined {
  if (SCALED_AFTER.test(after)) {
    return undefined;
  }
  const isYear =
    shown.isBareYear &&
    !UNIT_AFTER.test(after) &&
    allowed.years.some(([from, to]) => shown.value >= from && shown.value <= to);
  return isYear ? YEAR_MATCH : allowed.values.find((entry) => isMatch(shown, entry));
}

function isMatch(shown: ShownNumber, entry: AllowedValue): boolean {
  const half = HALF_UNIT * 10 ** -shown.decimals;
  // ponytail: a percent sign reads a fraction as its share of 100 (95% for 0.95) and
  // every other value as written, so 52% never passes for an r of 0.52. Proposed
  // working value (TRD Q-03).
  const targets = shown.isPercent && entry.isFraction ? [entry.value * PERCENT] : entry.candidates;
  const isRounded = targets.some((target) => isWithin(shown, target, half));
  // ponytail: the cards cut a p-value toward zero (VerdictStats.tsx), so the cut form
  // passes as well. Proposed working value (TRD Q-03); drop it if the cards round.
  const gap = entry.value - shown.value;
  const isCut = entry.isPValue && !shown.hasSign && gap >= 0 && gap < 2 * half;
  return isRounded || isCut;
}

/** An unsigned number states a size, as in "fell by 1.5 days"; a signed one, the value. */
function isWithin(shown: ShownNumber, candidate: number, half: number): boolean {
  const target = shown.hasSign ? candidate : Math.abs(candidate);
  return Math.abs(target - shown.value) <= half * FLOAT_SLACK;
}

function toTarget(trend: Extract<GuardResult, { kind: "trend" }>): ProvenanceTarget {
  return { provenance: trend.body.provenance, footprint: trend.body.footprint, meta: trend.meta };
}
