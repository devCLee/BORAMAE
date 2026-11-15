/**
 * The text steps of the number guard: masking, sentence splitting and number
 * extraction. Masking replaces each span with spaces of the same length, so a
 * position in the masked text is the same position in the sentence.
 */

export interface ShownNumber {
  /** The number as the text writes it, with its sign and its percent sign. */
  text: string;
  value: number;
  /** The digits after the decimal point: the precision that the text shows. */
  decimals: number;
  hasSign: boolean;
  isPercent: boolean;
  /** Four digits with no sign, separator, decimals or percent: a year, inside a window. */
  isBareYear: boolean;
  start: number;
  end: number;
}

/**
 * A citation marker such as "[power_merra2]", with the space before it. Kept text drops it.
 * ponytail: an ID in square brackets is a Proposed marker syntax (TDD Flow D step 7). A
 * marker in another syntax reads as text, so its digits withhold the sentence.
 */
export const CITATION_MARKER = /\s*\[[^[\]\n]*\]/g;

// ponytail: the masking lists are Proposed working values (TRD Q-03). They are closed
// lists, not shapes, so a digit glued to any other word stays and withholds its
// sentence. A new ID with a digit, such as a P1 dataset name, needs its entry here.
/** The catalog IDs that hold a digit (constants.py). A catalog test checks the list. */
const DIGIT_IDS = [
  "T2M",
  "T2M_MAX",
  "T2M_MIN",
  "RH2M",
  "WS10M",
  "CDD18_3",
  "HDD18_3",
  "TO3",
  "rx1day",
  "spi3_months",
];
/** The dataset and index names with a digit that an answer cites. */
const CITED_NAMES = ["MERRA-2", "MERRA2", "SPI-3"];
const MASKS = [
  CITATION_MARKER,
  /\b[a-z][a-z\d+.-]*:\/\/\S+|\bwww\.\S+/gi, // URLs
  /\b10\.\d{4,9}\/\S+/g, // DOIs
  /\bCB-\d{2}\b/g, // board IDs
  /(?<=[A-Za-z])\^-?\d+/g, // the power of a unit, such as m^2
  /(?<![\d.])10\s*년\s*(?:당|마다)|\b(?:per|every)\s+10\s+years?\b/gi, // "per decade", as Korean writes it
];
// Sign, then digits with thousands separators or a fraction alone, then a percent sign
// or word. No word character or point stands before it, so a digit inside a word is no
// number.
const NUMBER =
  /(?<![\w.])([-+−]?)(?:(\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?:\.(\d+))?|\.(\d+))(?!\.?\d)(\s*%|[\s-]?percent(?![A-Za-z])|\s*퍼센트)?/g;
// A sentence ends at . ! ? 。 or … before a space, with its citation markers and closing
// quotes, or at a line break. ponytail: an abbreviation such as "e.g." also ends one; a
// shorter sentence is checked the same way.
const SENTENCE_BREAK = /(?<=[.!?。…](?:\s*\[[^[\]\n]*\])*["'”’)]*)\s+(?![\s[])|\n+/;
/** Invisible characters, such as a zero-width space: "9​9" shows as 99. */
const FORMAT_CHARS = /\p{Cf}/gu;
const HAS_LETTER = /\p{L}/u;
/** A version such as 10.0.0: two points or more, so it reads as no number. */
const DOTTED_VERSION = /^\d+(?:\.\d+){2,}$/;
const REGEX_SYNTAX = /[.*+?^${}()|[\]\\]/g;
const FULL_WIDTH = /[！-～]/g;
const FULL_WIDTH_OFFSET = 0xfee0;
const MINUS_SIGNS = new Set(["-", "−"]);
const YEAR_DIGITS = /^\d{4}$/;
/** A decimal digit of any script. A superscript such as the 2 of m² is no decimal digit. */
const DIGIT = /\p{Nd}/u;

/**
 * Blanks what holds digits but states no number: citation markers, URLs, DOIs, the
 * catalog IDs, board IDs, and the names of the catalog and the datasets, such as the
 * version 10.0.0. It first maps full-width characters to ASCII one to one, so that
 * "１２" counts as 12.
 */
export function maskIdentifiers(text: string, names: string[]): string {
  const patterns = [namePattern([...DIGIT_IDS, ...CITED_NAMES, ...names]), ...MASKS];
  return patterns.reduce((masked, pattern) => masked.replace(pattern, blank), toHalfWidth(text));
}

export function splitSentences(text: string): string[] {
  return text
    .replace(FORMAT_CHARS, "")
    .split(SENTENCE_BREAK)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence !== "");
}

/** Every digit-based number, with its sign, decimals, thousands separators and percent sign. */
export function extractNumbers(text: string): ShownNumber[] {
  return [...text.matchAll(NUMBER)].map((match) => {
    const [whole, sign, integer, fraction, fractionOnly, percent] = match;
    const decimals = fraction ?? fractionOnly ?? "";
    const magnitude = Number(`${(integer ?? "0").replaceAll(",", "")}.${decimals}`);
    return {
      text: whole,
      value: MINUS_SIGNS.has(sign) ? -magnitude : magnitude,
      decimals: decimals.length,
      hasSign: sign !== "",
      isPercent: percent !== undefined,
      isBareYear:
        sign === "" && YEAR_DIGITS.test(integer ?? "") && decimals === "" && percent === undefined,
      start: match.index,
      end: match.index + whole.length,
    };
  });
}

/**
 * True when a digit of the masked text lies outside every number, as in 2026.09.15:
 * a number that the guard cannot read, so its sentence cannot pass.
 * ponytail: every number form that the extractor does not read, such as Top7, is
 * withheld this way (TRD Q-03). Read a new form in NUMBER if valid answers need it.
 */
export function hasStrayDigit(masked: string, numbers: ShownNumber[]): boolean {
  const rest = numbers.reduce(
    (text, { start, end }) => text.slice(0, start) + blank(text.slice(start, end)) + text.slice(end),
    masked,
  );
  return DIGIT.test(rest);
}

/** Maps full-width characters to ASCII one to one, so positions stay the same. */
export function toHalfWidth(text: string): string {
  return text.replace(FULL_WIDTH, (char) =>
    String.fromCharCode(char.charCodeAt(0) - FULL_WIDTH_OFFSET),
  );
}

/**
 * One pattern for every name with a letter. A name with no letter names no
 * identifier, except a dotted version, which cannot read as a number.
 */
function namePattern(names: string[]): RegExp {
  const patterns = names
    .filter((name) => HAS_LETTER.test(name) || DOTTED_VERSION.test(name))
    .sort((first, second) => second.length - first.length)
    .map(toNamePattern);
  return new RegExp(patterns.join("|"), "gi");
}

function toNamePattern(name: string): string {
  // A name that starts or ends with a digit must not take a digit of a number next to it.
  const before = /^\d/.test(name) ? "(?<![\\d.])" : "";
  const after = /\d$/.test(name) ? "(?!\\d)" : "";
  return before + name.replace(REGEX_SYNTAX, "\\$&") + after;
}

function blank(span: string): string {
  return " ".repeat(span.length);
}
