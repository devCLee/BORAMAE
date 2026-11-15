import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";

const MESSAGES_DIR = path.join(import.meta.dirname, "../src/messages");
const LOCALES = ["en", "ko"];
const MESSAGE_FILE_EXTENSION = ".json";

/**
 * Compares the messages of one namespace across the languages.
 * Returns one line for each key that a language lacks and for each empty string.
 */
export function findProblems(messagesByLocale) {
  const leavesByLocale = LOCALES.map((locale) => [
    locale,
    flattenLeaves(messagesByLocale[locale]),
  ]);
  const keys = new Set(
    leavesByLocale.flatMap(([, leaves]) => Object.keys(leaves)),
  );

  const problems = [];
  for (const key of [...keys].sort()) {
    for (const [locale, leaves] of leavesByLocale) {
      if (!(key in leaves)) {
        problems.push(`${key}: missing in ${locale}`);
      } else if (isEmptyString(leaves[key])) {
        problems.push(`${key}: empty in ${locale}`);
      }
    }
  }
  return problems;
}

function flattenLeaves(node, prefix = "") {
  const leaves = {};
  for (const [name, value] of Object.entries(node)) {
    const key = prefix + name;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(leaves, flattenLeaves(value, `${key}.`));
    } else {
      leaves[key] = value;
    }
  }
  return leaves;
}

function isEmptyString(value) {
  return typeof value === "string" && value.trim() === "";
}

function main() {
  const { values } = parseArgs({ options: { ns: { type: "string" } } });
  const namespaces = values.ns ? values.ns.split(",") : listNamespaces();
  const problems = namespaces.flatMap(lintNamespace);

  for (const problem of problems) {
    process.stderr.write(`${problem}\n`);
  }
  process.stdout.write(
    `lint:i18n checked ${namespaces.length} namespaces and found ${problems.length} problems\n`,
  );
  process.exitCode = problems.length > 0 ? 1 : 0;
}

function listNamespaces() {
  const names = LOCALES.flatMap((locale) =>
    readdirSync(path.join(MESSAGES_DIR, locale)),
  )
    .filter((name) => name.endsWith(MESSAGE_FILE_EXTENSION))
    .map((name) => path.basename(name, MESSAGE_FILE_EXTENSION));
  return [...new Set(names)].sort();
}

function lintNamespace(namespace) {
  const messagesByLocale = {};
  const problems = [];
  for (const locale of LOCALES) {
    const file = path.join(
      MESSAGES_DIR,
      locale,
      namespace + MESSAGE_FILE_EXTENSION,
    );
    if (existsSync(file)) {
      messagesByLocale[locale] = JSON.parse(readFileSync(file, "utf8"));
    } else {
      problems.push(`${namespace}: no file in ${locale}`);
    }
  }
  if (problems.length > 0) {
    return problems;
  }
  return findProblems(messagesByLocale).map(
    (problem) => `${namespace}.${problem}`,
  );
}

// The unit test imports findProblems. Only a direct start of this file is the command.
if (import.meta.main) {
  main();
}
