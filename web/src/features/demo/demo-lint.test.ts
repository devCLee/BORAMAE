import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { expect, test } from "vitest";

import type { DemoCase, DemoScript } from "@/contracts/types";
import { caseBoard, manifest } from "@/test/fixtures";

import {
  findCaseProblems,
  findManifestProblems,
  findScriptProblems,
} from "../../../scripts/demo-lint.mjs";
import { DEMO_CASES, findScript } from "./demo-content";

const SNOW_CASE = DEMO_CASES[0];
const SNOW_SCRIPT = findScript(SNOW_CASE.id) as DemoScript;
const [VERDICT_INDEX, PIN_INDEX, LAST_INDEX] = [
  SNOW_SCRIPT.steps.findIndex((step) => step.is_verdict_step),
  SNOW_SCRIPT.steps.findIndex((step) => step.action === "set_pin"),
  SNOW_SCRIPT.steps.length - 1,
];

function withStep(index: number, patch: object): DemoScript {
  const steps = SNOW_SCRIPT.steps.map((step, at) =>
    at === index ? { ...step, ...patch } : step,
  );
  return { ...SNOW_SCRIPT, steps };
}

/** A temporary demo folder with each named file, each holding the sample board. */
function writeDemoFolder(files: string[]): string {
  const folder = mkdtempSync(path.join(tmpdir(), "demo-lint-"));
  files.forEach((file) => {
    const target = path.join(folder, file);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, JSON.stringify(caseBoard));
  });
  return folder;
}

const SAMPLE_FILES = [
  manifest.catalog,
  ...manifest.cases.flatMap((entry) => [
    entry.parse.en,
    entry.parse.ko,
    ...Object.values(entry.kinds).map(({ file }) => file),
    ...Object.values(entry.referenced).flatMap((byKey) => Object.values(byKey)),
  ]),
];

test("should find no problem in the first-snow script", () => {
  expect(findScriptProblems(SNOW_SCRIPT, DEMO_CASES)).toEqual([]);
});

test.each([
  [
    "an unknown case",
    { ...SNOW_SCRIPT, case_id: "no-such-case" },
    "first-snow-seoul: unknown demo case no-such-case",
  ],
  [
    "a second verdict step",
    withStep(PIN_INDEX, { is_verdict_step: true }),
    "first-snow-seoul: 2 verdict steps, expected 1",
  ],
  [
    "no closing card at the end",
    withStep(LAST_INDEX, { action: "show_verdict" }),
    "first-snow-seoul: the last step is not closing_card",
  ],
  [
    "a kind that the case does not declare",
    withStep(VERDICT_INDEX + 1, { action: "open_board" }),
    "first-snow-seoul.open-fallback: the case declares no caseboard spec",
  ],
  [
    "args that differ from the case",
    withStep(PIN_INDEX, { args: { ...SNOW_CASE.area, radius_km: 30 } }),
    "first-snow-seoul.set-pin: the args differ from the case",
  ],
])("should report %s", (_name, script, problem) => {
  expect(findScriptProblems(script, DEMO_CASES)).toEqual([problem]);
});

test("should report a spec whose area differs from the case", () => {
  const scan = { ...SNOW_CASE.specs.trend, kind: "scan" as const, area: { ...SNOW_CASE.area, radius_km: 30 } };
  const demoCase: DemoCase = { ...SNOW_CASE, specs: { ...SNOW_CASE.specs, scan } };

  expect(findCaseProblems(demoCase)).toEqual([
    "first-snow-seoul.specs.scan: the spec differs from the case",
  ]);
});

test("should find no problem when every file of the manifest exists", () => {
  const folder = writeDemoFolder(SAMPLE_FILES);

  expect(findManifestProblems(manifest, folder)).toEqual([]);
});

test("should report a file of the manifest that does not exist", () => {
  const folder = writeDemoFolder(SAMPLE_FILES.slice(1));

  expect(findManifestProblems(manifest, folder)).toEqual([
    "manifest.json: missing file catalog.json",
  ]);
});

test("should report a board node trend that referenced.trend does not hold", () => {
  const folder = writeDemoFolder(SAMPLE_FILES);
  const [first, ...rest] = manifest.cases;
  const unreferenced = { ...manifest, cases: [{ ...first, referenced: {} }, ...rest] };

  expect(findManifestProblems(unreferenced, folder)).toHaveLength(4);
});
