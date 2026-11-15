/**
 * Lists every link of the content files and the message files for the link check on
 * the day before submission (TDD DES-014, PRD "Risks & mitigations").
 * Run: node scripts/list-links.mjs [folder ...]. Without a folder it reads content/ and
 * src/messages/. Prints one line for each link of each JSON file: the file, a tab and
 * the link. A DOI prints as its doi.org link, so every line opens in a browser.
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";

const DEFAULT_FOLDERS = ["../../content", "../src/messages"].map((folder) =>
  path.join(import.meta.dirname, folder),
);
const JSON_EXTENSION = ".json";
// ponytail: a URL ends at a bracket, so a link that holds ( or ) is cut there. No content
// link holds one today; match balanced brackets if one ever does.
const URL_PATTERN = /https?:\/\/[^\s"'<>()[\]{}]+/g;
const DOI_PATTERN = /\b10\.\d{4,9}\/[^\s"'<>]+/g;
const DOI_BASE = "https://doi.org/";
// A sentence can end right after a link; the closing mark is not part of it.
const TRAILING_MARKS = /[.,;:!?]+$/;

function main() {
  const { positionals } = parseArgs({ allowPositionals: true });
  const folders = positionals.length > 0 ? positionals : DEFAULT_FOLDERS;
  const lines = folders.flatMap(listFolder);

  process.stdout.write(lines.map((line) => `${line}\n`).join(""));
  process.stderr.write(`list:links found ${lines.length} links\n`);
}

/** The lines of every JSON file under the folder, named from the folder's own name. */
function listFolder(folder) {
  return readdirSync(folder, { recursive: true })
    .filter((file) => file.endsWith(JSON_EXTENSION))
    .sort()
    .flatMap((file) => {
      const name = path.join(path.basename(folder), file).replaceAll("\\", "/");
      const texts = collectStrings(JSON.parse(readFileSync(path.join(folder, file), "utf8")));
      return [...new Set(texts.flatMap(findLinks))].map((link) => `${name}\t${link}`);
    });
}

function collectStrings(value) {
  if (typeof value === "string") {
    return [value];
  }
  return value !== null && typeof value === "object"
    ? Object.values(value).flatMap(collectStrings)
    : [];
}

/** The URLs of a text, then the DOIs outside those URLs as doi.org links. */
function findLinks(text) {
  const urls = (text.match(URL_PATTERN) ?? []).map(trimMarks);
  const dois = (text.replace(URL_PATTERN, " ").match(DOI_PATTERN) ?? []).map(
    (doi) => DOI_BASE + trimMarks(doi),
  );
  return [...urls, ...dois];
}

function trimMarks(link) {
  return link.replace(TRAILING_MARKS, "");
}

main();
