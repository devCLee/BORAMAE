/**
 * The citations of the number guard (TDD Flow D, step 10): the model cites by ID from
 * a closed list, and the browser resolves each ID to a glossary entry, the dataset of
 * a loaded result or a registry row of a loaded board. An ID that resolves to nothing
 * is dropped.
 */
import type { GlossaryTerm } from "@/components/Term";
import type { RegistryRow } from "@/contracts/types";
import glossaryMessages from "@/messages/en/glossary.json";

import type { GuardResult } from "./number-guard";

export type Citation =
  | { kind: "glossary"; id: GlossaryTerm }
  | { kind: "dataset"; id: string; version: string }
  | { kind: "registry"; id: string; row: RegistryRow };

// Both languages hold the same glossary keys (lint:i18n), so the English file lists them.
const GLOSSARY_TERMS = Object.keys(glossaryMessages.terms) as GlossaryTerm[];

/** The sources that an answer may cite: glossary entries, datasets and registry rows. */
export function buildCitations(results: GuardResult[]): Map<string, Citation> {
  const citations: Citation[] = [
    ...GLOSSARY_TERMS.map((id) => ({ kind: "glossary" as const, id })),
    ...results.flatMap(citationsOf),
  ];
  return new Map(citations.map((citation) => [citation.id, citation]));
}

/** The cited sources in order, once each. An ID that resolves to nothing is dropped. */
export function resolveCitations(
  ids: string[],
  known: ReadonlyMap<string, Citation>,
): Citation[] {
  return [...new Set(ids)].flatMap((id) => {
    const citation = known.get(id);
    return citation === undefined ? [] : [citation];
  });
}

/** A registry row resolves by its ID and by its DOI. */
function citationsOf(result: GuardResult): Citation[] {
  switch (result.kind) {
    case "trend": {
      const { dataset_id: id, dataset_version: version } = result.body.provenance;
      return [{ kind: "dataset", id, version }];
    }
    case "caseboard":
      return result.body.nodes.flatMap(({ row }) =>
        [row.id, row.doi].flatMap((id) =>
          id === null ? [] : [{ kind: "registry" as const, id, row }],
        ),
      );
    case "scan":
      return [];
  }
}
