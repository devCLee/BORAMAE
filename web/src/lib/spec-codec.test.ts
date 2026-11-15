import { Buffer } from "node:buffer";

import { expect, test } from "vitest";

import type { RequestSpec } from "@/contracts/types";
import { encodeSpec } from "@/lib/spec-codec";
import goldenVectors from "@content/golden/request-spec.json";

// TypeScript gives a JSON import wide types, so the vectors are cast one time here.
const VECTORS = goldenVectors as unknown as { spec: RequestSpec; s: string }[];
const VECTOR_COUNT = 8;
/** The vector with the fewest members: T2M annual mean on a 10 km circle. */
const PLAIN = VECTORS[5];

test("should read every golden vector of the contract", () => {
  expect(VECTORS).toHaveLength(VECTOR_COUNT);
});

test.each(VECTORS)(
  "should encode the $spec.kind request of $spec.var as its golden string",
  ({ spec, s }) => {
    expect(encodeSpec(spec)).toBe(s);
  },
);

test("should sort the keys at every level", () => {
  const unsorted: RequestSpec = {
    window: { start: 1981, end: "latest" },
    var: "T2M",
    v: 1,
    metric: { id: "annual_mean" },
    kind: "trend",
    area: { radius_km: 10, lon: 139, lat: 35 },
  };

  expect(encodeSpec(unsorted)).toBe(PLAIN.s);
});

test("should leave out a member with the value null", () => {
  const withNulls: RequestSpec = {
    ...PLAIN.spec,
    metric: {
      id: "annual_mean",
      threshold: null,
      op: null,
      months: null,
      season_start: null,
    },
  };

  expect(encodeSpec(withNulls)).toBe(PLAIN.s);
});

test("should encode a character outside ASCII as UTF-8", () => {
  const canonicalJson =
    '{"area":{"lat":35,"lon":139,"radius_km":10},"kind":"trend","metric":{"id":"annual_mean"},"v":1,"var":"눈","window":{"end":"latest","start":1981}}';

  expect(encodeSpec({ ...PLAIN.spec, var: "눈" })).toBe(
    Buffer.from(canonicalJson, "utf8").toString("base64url"),
  );
});
