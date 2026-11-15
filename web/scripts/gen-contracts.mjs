import { existsSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import path from "node:path";

import { compileFromFile } from "json-schema-to-typescript";

const CONTRACTS_DIR = path.join(import.meta.dirname, "../src/contracts");
const SCHEMA_PATH = path.join(CONTRACTS_DIR, "schema.json");
const OUTPUT_PATH = path.join(CONTRACTS_DIR, "api.gen.ts");

if (existsSync(SCHEMA_PATH)) {
  const source = await compileFromFile(SCHEMA_PATH, {
    // Emit every model in $defs, also one that the root schema does not reference.
    unreachableDefinitions: true,
    // Without this, each model gets an index signature and a misspelled field passes the typecheck.
    additionalProperties: false,
  });
  await writeFile(OUTPUT_PATH, source);
  process.stdout.write("gen:contracts wrote src/contracts/api.gen.ts\n");
} else {
  process.stdout.write(
    "gen:contracts skipped: src/contracts/schema.json does not exist yet\n",
  );
}
