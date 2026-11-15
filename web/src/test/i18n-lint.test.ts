import { spawnSync } from "node:child_process";
import path from "node:path";

import { expect, test } from "vitest";

import { findProblems } from "../../scripts/i18n-lint.mjs";

const SCRIPT_FILE = path.join(
  import.meta.dirname,
  "../../scripts/i18n-lint.mjs",
);
const FAILURE_EXIT_CODE = 1;

test("should run the check when a test starts the script as a command", () => {
  const command = spawnSync(process.execPath, [
    SCRIPT_FILE,
    "--ns",
    "no-such-namespace",
  ]);

  expect(command.status).toBe(FAILURE_EXIT_CODE);
});

test.each([
  {
    name: "no problem when both languages hold the same filled keys",
    en: { title: "Trend", card: { rate: "Rate" } },
    ko: { title: "추세", card: { rate: "변화율" } },
    expected: [],
  },
  {
    name: "a key that ko lacks",
    en: { title: "Trend", card: { rate: "Rate" } },
    ko: { title: "추세", card: {} },
    expected: ["card.rate: missing in ko"],
  },
  {
    name: "a key that en lacks",
    en: {},
    ko: { title: "추세" },
    expected: ["title: missing in en"],
  },
  {
    name: "an empty string",
    en: { title: "Trend" },
    ko: { title: "" },
    expected: ["title: empty in ko"],
  },
  {
    name: "a string that holds only spaces",
    en: { title: " " },
    ko: { title: "추세" },
    expected: ["title: empty in en"],
  },
])("should report $name", ({ en, ko, expected }) => {
  expect(findProblems({ en, ko })).toEqual(expected);
});
