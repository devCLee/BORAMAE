import { expect, test } from "vitest";

import { caseBoard, manifest, trendSignificant } from "@/test/fixtures";

test("should load a sample record through the typed fixture index", () => {
  expect(trendSignificant.verdict).toBe("significant_rise");
});

test("should hold the trend file of every board node in the manifest sample", () => {
  const listed = Object.keys(manifest.cases[0].referenced.trend);
  const nodeKeys = caseBoard.nodes.flatMap((node) => node.trend_key ?? []);
  expect(listed).toEqual(expect.arrayContaining(nodeKeys));
});
