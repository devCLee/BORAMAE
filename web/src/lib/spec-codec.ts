import type { RequestSpec } from "@/contracts/types";

/**
 * The query parameter s (docs/BUILD_CONTRACT.md "Encodings"): the canonical JSON
 * of the request spec, in base64url with no padding. The fixture source of the
 * demo matches the whole string, so a spec is encoded as typed: "0.1" and "0.10"
 * give different strings.
 */
export function encodeSpec(spec: RequestSpec): string {
  const bytes = new TextEncoder().encode(toCanonicalJson(spec));
  // btoa takes one character for each byte, so a character outside ASCII goes in as its UTF-8 bytes.
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

/** Keys sorted at every level, no spaces, and no member with the value null. */
function toCanonicalJson(spec: RequestSpec): string {
  return JSON.stringify(spec, (_key, value: unknown) =>
    isRecord(value) ? sortWithoutNulls(value) : value,
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function sortWithoutNulls(
  record: Record<string, unknown>,
): Record<string, unknown> {
  const members = Object.entries(record)
    .filter(([, member]) => member !== null)
    .sort(([left], [right]) => (left < right ? -1 : 1));
  return Object.fromEntries(members);
}
