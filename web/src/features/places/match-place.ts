/**
 * The local place search over the bundled gazetteer (TR-F-008, TDD DEC-011). It
 * matches every name of a place in both languages, so a Korean or an English
 * name finds the same place in either UI language. Fuzzy matching is P1 (FR-29).
 */
import type { Place } from "@/contracts/types";
import gazetteerJson from "@content/gazetteer.json";

// ponytail: 8 names fit under the search field on a phone; no document sets the size.
export const MAX_PLACE_MATCHES = 8;

// The names are normalized once, not on every keystroke.
const ENTRIES = (gazetteerJson as unknown as Place[]).map((place) => ({
  place,
  names: [place.name.en, place.name.ko, ...place.alt].map(normalize),
}));

/** Exact, a name that starts with the query, a name that holds it, a name inside it. */
type Rank = 0 | 1 | 2 | 3;

/**
 * The places whose names match the query, best first. The last rank holds a
 * place whose name stands inside the query, so "Busan coast" finds Busan; the
 * longer name wins there. A rank keeps the order of the gazetteer file.
 */
export function matchPlaces(query: string): Place[] {
  const needle = normalize(query);
  if (needle === "") {
    return [];
  }
  return ENTRIES.flatMap(({ place, names }) => {
    const scored = scoreNames(names, needle);
    return scored === null ? [] : [{ place, ...scored }];
  })
    .sort((a, b) => a.rank - b.rank || b.length - a.length)
    .slice(0, MAX_PLACE_MATCHES)
    .map(({ place }) => place);
}

function scoreNames(
  names: string[],
  needle: string,
): { rank: Rank; length: number } | null {
  if (names.includes(needle)) {
    return { rank: 0, length: 0 };
  }
  if (names.some((name) => name.startsWith(needle))) {
    return { rank: 1, length: 0 };
  }
  if (names.some((name) => name.includes(needle))) {
    return { rank: 2, length: 0 };
  }
  const inside = names.filter((name) => name !== "" && needle.includes(name));
  return inside.length === 0
    ? null
    : { rank: 3, length: Math.max(...inside.map((name) => name.length)) };
}

/** Case, Unicode form, punctuation and runs of spaces never decide a match. */
function normalize(text: string): string {
  return text
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\p{P}\s]+/gu, " ")
    .trim();
}
