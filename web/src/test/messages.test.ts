import { expect, test } from "vitest";

import { messages } from "@/i18n/messages";

const NAMESPACES = [
  "a11y",
  "ai",
  "board",
  "case",
  "chart",
  "common",
  "demo",
  "errors",
  "fallback",
  "glossary",
  "guide",
  "landing",
  "map",
  "methods",
  "places",
  "provenance",
  "rail",
  "suggestions",
  "units",
  "verdict",
  "window",
];

test.each(["en", "ko"] as const)(
  "should hold all 21 namespaces in %s",
  (locale) => {
    expect(Object.keys(messages[locale]).sort()).toEqual(NAMESPACES);
  },
);
