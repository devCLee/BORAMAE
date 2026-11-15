import { expect, test } from "vitest";

import { getPathname } from "@/i18n/navigation";

test("should put the locale before the path of a route", () => {
  expect(getPathname({ href: "/methods", locale: "ko" })).toBe("/ko/methods");
});
