import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { expect, test } from "vitest";

const SCRIPT_FILE = path.join(
  import.meta.dirname,
  "../../../scripts/scan-export.mjs",
);
const FAILURE_EXIT_CODE = 1;
const PLANTED_FILE = "_next/chunk.js";
const MISSING_FOLDER = path.join(tmpdir(), "no-such-export-folder");
// Near misses that a real export holds: a link, the word Bearer, a short key prefix.
const CLEAN_TEXT =
  'fetch("https://example.org/data", { headers: { Authorization: "Bearer " + value } }); // AKIA';
// The repository's write hook stops a file whose text looks like a key, so each
// planted value is put together at run time.
const KEY_ID = "AKIA".concat("Q".repeat(16));
const PLANTED = [
  {
    name: "an AWS access key ID",
    text: `const id = "${KEY_ID}";`,
    kind: "AWS access key ID",
  },
  {
    name: "a temporary AWS access key ID",
    text: `const id = "${"ASIA".concat("7".repeat(16))}";`,
    kind: "AWS access key ID",
  },
  {
    name: "a private-key block",
    text: ["-----BEGIN", "PRIVATE", "KEY-----"].join(" "),
    kind: "private-key block",
  },
  {
    name: "an RSA private-key block",
    text: ["-----BEGIN", "RSA", "PRIVATE", "KEY-----"].join(" "),
    kind: "private-key block",
  },
  {
    name: "a bearer string",
    text: `Authorization: Bearer ${"b".repeat(32)}`,
    kind: "bearer string",
  },
  {
    name: "a URL with credentials",
    text: `"https://${["name", "word"].join(":")}@example.org/data"`,
    kind: "URL with credentials",
  },
  {
    name: "a NEXT_PUBLIC_ name with KEY",
    text: `process.env.${"NEXT_PUBLIC_"}MAP_KEY`,
    kind: "NEXT_PUBLIC_ name with KEY or SECRET",
  },
  {
    name: "a NEXT_PUBLIC_ name with SECRET",
    text: `process.env.${"NEXT_PUBLIC_"}CLIENT_SECRET`,
    kind: "NEXT_PUBLIC_ name with KEY or SECRET",
  },
];

/** A temporary export folder with one file in a subfolder, as next build writes them. */
function writeExport(text: string): string {
  const folder = mkdtempSync(path.join(tmpdir(), "scan-export-"));
  mkdirSync(path.join(folder, "_next"));
  writeFileSync(path.join(folder, PLANTED_FILE), text);
  return folder;
}

function scan(folders: string[], env: Record<string, string> = {}) {
  return spawnSync(process.execPath, [SCRIPT_FILE, ...folders], {
    encoding: "utf8",
    env: { ...process.env, ...env },
  });
}

/** A failed scan that reports the given line, so a crash of the script does not pass. */
function failureWith(line: string) {
  return { status: FAILURE_EXIT_CODE, stderr: expect.stringContaining(line) };
}

test.each(PLANTED)("should exit 1 on $name", ({ text, kind }) => {
  expect(scan([writeExport(text)])).toMatchObject(
    failureWith(`${PLANTED_FILE}:1: ${kind}`),
  );
});

test("should exit 0 on a clean folder", () => {
  expect(scan([writeExport(CLEAN_TEXT)]).status).toBe(0);
});

test("should exit 1 when one of several folders holds a finding", () => {
  expect(
    scan([writeExport(CLEAN_TEXT), writeExport(PLANTED[0].text)]),
  ).toMatchObject(failureWith(`${PLANTED_FILE}:1: ${PLANTED[0].kind}`));
});

test("should not print the value it found", () => {
  expect(scan([writeExport(PLANTED[0].text)]).stderr).not.toContain(KEY_ID);
});

test("should exit 1 when the environment names a NEXT_PUBLIC_ key", () => {
  expect(
    scan([writeExport(CLEAN_TEXT)], { NEXT_PUBLIC_MAP_KEY: "x" }),
  ).toMatchObject(failureWith("NEXT_PUBLIC_MAP_KEY"));
});

test("should exit 1 when a folder to scan does not exist", () => {
  expect(scan([MISSING_FOLDER])).toMatchObject(failureWith(MISSING_FOLDER));
});
