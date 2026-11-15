import { expect, test } from "vitest";

import { toScholarUrl } from "./scholar-url";

const paramsOf = (url: string) => new URL(url).searchParams;

test("should search the variable name and the place name", () => {
  const url = toScholarUrl("Snowfall", "Seoul", [1981, "2025-12"]);

  expect(paramsOf(url).get("q")).toBe("Snowfall Seoul");
});

test("should start the search at the start year of the window", () => {
  const url = toScholarUrl("Snowfall", "Seoul", [1981, "2025-12"]);

  expect(paramsOf(url).get("as_ylo")).toBe("1981");
});

test("should end the search at the end year of the window", () => {
  const url = toScholarUrl("Snowfall", "Seoul", [1981, "2025-12"]);

  expect(paramsOf(url).get("as_yhi")).toBe("2025");
});

test("should search the variable name alone when the case has no place name", () => {
  const url = toScholarUrl("Snowfall", null, [1981, "2025-12"]);

  expect(paramsOf(url).get("q")).toBe("Snowfall");
});

test("should open the Google Scholar search page", () => {
  const url = new URL(toScholarUrl("Snowfall", null, [1981, "2025-12"]));

  expect(`${url.origin}${url.pathname}`).toBe("https://scholar.google.com/scholar");
});
