import { expect, test } from "vitest";

import type { CatalogInputs, Lang } from "@/contracts/types";
import catalogInputsJson from "@content/catalog-inputs.json";

import { MAX_PLACE_MATCHES, matchPlaces } from "./match-place";

const LANGS: Lang[] = ["en", "ko"];

// TR-F-008 acceptance (1): every place of the catalog inputs, by each of its names.
// A combined country such as "KR+US" accepts a place in either country.
const INPUT_PLACES = (catalogInputsJson as unknown as CatalogInputs).inputs.flatMap(
  ({ id, place }) =>
    place === null
      ? []
      : LANGS.map((lang) => ({
          id,
          lang,
          name: place.name[lang],
          countries: place.country.split("+"),
        })),
);

test.each(INPUT_PLACES)(
  "should resolve the place of input $id by its $lang name '$name'",
  ({ name, countries }) => {
    expect(countries).toContain(matchPlaces(name)[0]?.country);
  },
);

test.each([
  { query: "Seoul", id: "kr-seoul" },
  { query: "서울", id: "kr-seoul" },
  { query: "  SEOUL ", id: "kr-seoul" },
  { query: "NYC", id: "us-new-york" },
  { query: "Washington DC", id: "us-washington-dc" },
  { query: "Seo", id: "kr-seoul" },
  { query: "Busan coast", id: "kr-busan" },
])("should rank $id first for '$query'", ({ query, id }) => {
  expect(matchPlaces(query)[0]?.id).toBe(id);
});

test.each(["Atlantis", "", "   "])(
  "should find no place for '%s'",
  (query) => {
    expect(matchPlaces(query)).toEqual([]);
  },
);

test("should return at most the list size for a query that many names hold", () => {
  expect(matchPlaces("a")).toHaveLength(MAX_PLACE_MATCHES);
});
