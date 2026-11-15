/**
 * Fails when the static export or the demo bundle holds a key-like value (TR-Q-003,
 * SECURITY.md "Before every deploy"). Run it after next build:
 * node scripts/scan-export.mjs [folder ...]. Without a folder it walks web/out and
 * web/public/demo. A finding names the file, the line and the kind of value, never the
 * value itself, so the output is safe to paste.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";

const DEFAULT_FOLDERS = ["../out", "../public/demo"].map((folder) =>
  path.join(import.meta.dirname, folder),
);
const PUBLIC_KEY_NAME = /\bNEXT_PUBLIC_\w*(?:KEY|SECRET)/;
/**
 * Kind of value -> pattern. AKIA starts a long-term and ASIA a temporary AWS key ID.
 * ponytail: the five kinds of the build plan only, and a bearer value needs 20 characters
 * to count. Add a pattern when the app holds another kind of key, such as a map key.
 */
const KEY_PATTERNS = [
  ["AWS access key ID", /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/],
  ["private-key block", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ["bearer string", /\bBearer\s+[\w~+/.-]{20,}/i],
  ["URL with credentials", /\b[a-z][a-z\d+.-]*:\/\/[^\s/?#@:"'`<>]+:[^\s/?#@"'`<>]+@/i],
  ["NEXT_PUBLIC_ name with KEY or SECRET", PUBLIC_KEY_NAME],
];

function main() {
  const { positionals } = parseArgs({ allowPositionals: true });
  const folders = positionals.length > 0 ? positionals : DEFAULT_FOLDERS;
  // Next copies a NEXT_PUBLIC_ value into the bundle, so the name is a finding in the
  // environment of the build too, which a scan right after the build shares.
  const problems = Object.keys(process.env)
    .filter((name) => PUBLIC_KEY_NAME.test(name))
    .map((name) => `environment: ${name} would reach the browser bundle`);
  let fileCount = 0;
  for (const folder of folders) {
    if (!existsSync(folder)) {
      problems.push(`${folder}: no such folder, so nothing in it was scanned`);
      continue;
    }
    const files = listFiles(folder);
    fileCount += files.length;
    problems.push(...files.flatMap((file) => scanFile(file, path.relative(folder, file))));
  }

  for (const problem of problems) {
    process.stderr.write(`${problem}\n`);
  }
  process.stdout.write(
    `scan:export checked ${fileCount} files in ${folders.length} folders and found ${problems.length} problems\n`,
  );
  process.exitCode = problems.length > 0 ? 1 : 0;
}

function listFiles(folder) {
  return readdirSync(folder, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => path.join(entry.parentPath, entry.name));
}

/** One line for each line of the file that matches a pattern, with its kind of value. */
function scanFile(file, name) {
  const lines = readFileSync(file, "utf8").split("\n");
  return lines.flatMap((line, index) =>
    KEY_PATTERNS.filter(([, pattern]) => pattern.test(line)).map(
      ([kind]) => `${name.replaceAll("\\", "/")}:${index + 1}: ${kind}`,
    ),
  );
}

main();
