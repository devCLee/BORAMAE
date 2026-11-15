import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { expect, test } from "vitest";

const SCRIPT_FILE = path.join(
  import.meta.dirname,
  "../../../scripts/list-links.mjs",
);
const DOI = "10.1175/JCLI3850.1";
const SENTENCE_DOI = "10.1175/JCLI-D-16-0758.1";

/** A temporary content folder: bare DOIs, URL fields, URLs inside sentences, a subfolder. */
function writeContent(): string {
  const folder = mkdtempSync(path.join(tmpdir(), "list-links-"));
  mkdirSync(path.join(folder, "demo"));
  writeFileSync(
    path.join(folder, "registry.json"),
    JSON.stringify([
      { doi: DOI, url: null, citation: "Knowles et al. 2006" },
      { doi: DOI, url: null, citation: "Knowles et al. 2006" },
    ]),
  );
  writeFileSync(
    path.join(folder, "licenses.json"),
    JSON.stringify([
      {
        url: "https://registry.opendata.aws/nasa-power/",
        citation: `Accessed from https://registry.opendata.aws/nasa-power. See doi:${SENTENCE_DOI}.`,
      },
    ]),
  );
  writeFileSync(
    path.join(folder, "demo", "case.json"),
    JSON.stringify({ caption: { en: "See https://example.org/a?b=1, then" } }),
  );
  return folder;
}

const FOLDER = writeContent();
const NAME = path.basename(FOLDER);
const RUN = spawnSync(process.execPath, [SCRIPT_FILE, FOLDER], {
  encoding: "utf8",
});
const LINES = RUN.stdout.trim().split(/\r?\n/);

test.each([
  ["a bare DOI as a doi.org link", `${NAME}/registry.json\thttps://doi.org/${DOI}`],
  [
    "a URL field",
    `${NAME}/licenses.json\thttps://registry.opendata.aws/nasa-power/`,
  ],
  [
    "a URL in a sentence without the closing period",
    `${NAME}/licenses.json\thttps://registry.opendata.aws/nasa-power`,
  ],
  [
    "a DOI in a sentence as a doi.org link",
    `${NAME}/licenses.json\thttps://doi.org/${SENTENCE_DOI}`,
  ],
  [
    "a URL of a subfolder file without the trailing comma",
    `${NAME}/demo/case.json\thttps://example.org/a?b=1`,
  ],
])("should print %s", (_name, line) => {
  expect(LINES).toContain(line);
});

test("should print a link once per file", () => {
  expect(LINES).toHaveLength(5);
});

test("should exit 0", () => {
  expect(RUN.status).toBe(0);
});
