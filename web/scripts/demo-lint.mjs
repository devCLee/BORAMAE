import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

const CONTENT_DEMO_DIR = path.join(import.meta.dirname, "../../content/demo");
const PUBLIC_DEMO_DIR = path.join(import.meta.dirname, "../public/demo");
const MANIFEST_FILE = "manifest.json";
const JSON_EXTENSION = ".json";
const LAST_ACTION = "closing_card";
/** The result kind that a step asks for. */
const KIND_OF_ACTION = {
  confirm_spec: "trend",
  open_board: "caseboard",
  open_fallback: "scan",
};
/**
 * The value of the case that the args of a step must equal. The fixture source
 * matches the whole encoded spec, so "0.10" for "0.1" shows the offline empty state.
 */
const CASE_VALUE_OF_ACTION = {
  choose_language: (demoCase) => ({ lang: demoCase.lang }),
  type_question: (demoCase) => ({ text: demoCase.question[demoCase.lang] }),
  confirm_variables: ({ specs }) => ({
    var: specs.trend.var,
    metric: specs.trend.metric,
  }),
  set_pin: (demoCase) => demoCase.area,
  set_window: (demoCase) => demoCase.window,
};

/** Each spec of a case asks for the area, the window, the variable and the metric of the case. */
export function findCaseProblems(demoCase) {
  const { trend } = demoCase.specs;
  return Object.entries(demoCase.specs)
    .filter(([, spec]) => spec !== null)
    .filter(
      ([kind, spec]) =>
        spec.kind !== kind ||
        !isSame(
          [spec.area, spec.window, spec.var, spec.metric],
          [demoCase.area, demoCase.window, trend.var, trend.metric],
        ),
    )
    .map(([kind]) => `${demoCase.id}.specs.${kind}: the spec differs from the case`);
}

/** Checks one script against the demo cases. Returns one line for each problem. */
export function findScriptProblems(script, cases) {
  const demoCase = cases.find((candidate) => candidate.id === script.case_id);
  if (demoCase === undefined) {
    return [`${script.id}: unknown demo case ${script.case_id}`];
  }
  const problems = [];
  const verdictCount = script.steps.filter((step) => step.is_verdict_step).length;
  if (verdictCount !== 1) {
    problems.push(`${script.id}: ${verdictCount} verdict steps, expected 1`);
  }
  if (script.steps.at(-1)?.action !== LAST_ACTION) {
    problems.push(`${script.id}: the last step is not ${LAST_ACTION}`);
  }
  for (const step of script.steps) {
    const kind = KIND_OF_ACTION[step.action];
    if (kind !== undefined && demoCase.specs[kind] === null) {
      problems.push(`${script.id}.${step.id}: the case declares no ${kind} spec`);
    }
    const toCaseValue = CASE_VALUE_OF_ACTION[step.action];
    if (toCaseValue !== undefined && !isSame(step.args, toCaseValue(demoCase))) {
      problems.push(`${script.id}.${step.id}: the args differ from the case`);
    }
  }
  return problems;
}

/**
 * Every file that the manifest names exists, and every node trend of a bundled
 * board is listed under referenced.trend of its case.
 */
export function findManifestProblems(manifest, demoDir) {
  const exists = (file) => existsSync(path.join(demoDir, file));
  const problems = [manifest.catalog, ...manifest.cases.flatMap(listFiles)]
    .filter((file) => !exists(file))
    .map((file) => `${MANIFEST_FILE}: missing file ${file}`);
  for (const demoCase of manifest.cases) {
    const board = demoCase.kinds.caseboard;
    if (board === undefined || !exists(board.file)) {
      continue;
    }
    const referenced = demoCase.referenced.trend ?? {};
    const { nodes } = readJson(path.join(demoDir, board.file));
    problems.push(
      ...nodes
        .filter(({ trend_key }) => trend_key !== null && !Object.hasOwn(referenced, trend_key))
        .map(
          ({ trend_key }) =>
            `${board.file}: node trend ${trend_key} is not in referenced.trend of ${demoCase.case_id}`,
        ),
    );
  }
  return problems;
}

function listFiles(demoCase) {
  return [
    demoCase.parse.en,
    demoCase.parse.ko,
    ...Object.values(demoCase.kinds).map(({ file }) => file),
    ...Object.values(demoCase.referenced).flatMap((byKey) => Object.values(byKey)),
    ...[demoCase.answers.en, demoCase.answers.ko].filter((file) => file !== null),
  ];
}

/** Equal as the spec codec of the browser compares: keys in any order, null members left out. */
function isSame(left, right) {
  return toCanonicalJson(left) === toCanonicalJson(right);
}

function toCanonicalJson(value) {
  return JSON.stringify(value, (_key, member) =>
    member !== null && typeof member === "object" && !Array.isArray(member)
      ? Object.fromEntries(
          Object.entries(member)
            .filter(([, item]) => item !== null)
            .sort(([left], [right]) => (left < right ? -1 : 1)),
        )
      : member,
  );
}

function readJson(file) {
  return JSON.parse(readFileSync(file, "utf8"));
}

function main() {
  const cases = readJson(path.join(CONTENT_DEMO_DIR, "cases.json"));
  const scriptsDir = path.join(CONTENT_DEMO_DIR, "scripts");
  const scripts = readdirSync(scriptsDir)
    .filter((name) => name.endsWith(JSON_EXTENSION))
    .map((name) => readJson(path.join(scriptsDir, name)));
  const manifestPath = path.join(PUBLIC_DEMO_DIR, MANIFEST_FILE);
  const hasManifest = existsSync(manifestPath);
  const problems = [
    ...cases.flatMap(findCaseProblems),
    ...scripts.flatMap((script) => findScriptProblems(script, cases)),
    ...(hasManifest ? findManifestProblems(readJson(manifestPath), PUBLIC_DEMO_DIR) : []),
  ];

  for (const problem of problems) {
    process.stderr.write(`${problem}\n`);
  }
  process.stdout.write(
    `lint:demo checked ${cases.length} cases, ${scripts.length} scripts and ${hasManifest ? "the" : "no"} manifest, and found ${problems.length} problems\n`,
  );
  process.exitCode = problems.length > 0 ? 1 : 0;
}

// The unit test imports the checks. Only a direct start of this file is the command.
if (import.meta.main) {
  main();
}
