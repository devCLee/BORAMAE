import { expect, test } from "vitest";

import probe from "@content/probe.json";

test("should resolve @content to the content folder of the repository", () => {
  expect(probe.ok).toBe(true);
});
