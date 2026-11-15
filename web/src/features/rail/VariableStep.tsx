"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import type { CatalogVariable, DraftSpec, ParseProposal } from "@/contracts/types";
import { actions, useAppStore } from "@/state/store";

import { CatalogPicker } from "./CatalogPicker";
import { toDraft } from "./draft";
import { MetricEditor } from "./MetricEditor";
import { UnavailableNote } from "./UnavailableNote";
import { type Card, VariableCard } from "./VariableCard";

// FR-03: the parser proposes 1 to 3 variables, and an add stays inside that count.
const MAX_CARDS = 3;

/**
 * Step 2: the variable cards with Confirm and Swap, an add from the catalog, and
 * the metric of the draft with its threshold (FR-03, FR-16). A pick in the catalog
 * puts that variable in the draft, so it clears the confirmation.
 */
export function VariableStep() {
  const t = useTranslations("rail.variables");
  const proposal = useAppStore((state) => state.proposal);
  const draft = useAppStore((state) => state.draftSpec);
  const [cards, setCards] = useState(() => toCards(proposal, draft));

  function pick(variable: CatalogVariable, index: number) {
    const card: Card = {
      var: variable.id,
      metric_id: variable.default_metric,
      reason_code: null,
    };
    setCards((current) => current.toSpliced(index, 1, card));
    actions.editDraft(toDraft(card, null), "user");
  }

  function confirm(card: Card) {
    // Confirming the card of the draft again keeps an edited threshold.
    if (!isDraftOf(draft, card)) {
      actions.editDraft(toDraft(card, proposal?.spec ?? null), "user");
    }
    actions.goToStep(3);
  }

  return (
    <div className="flex flex-col gap-3">
      {proposal?.unavailable && (
        <UnavailableNote unavailable={proposal.unavailable} />
      )}
      {proposal !== null && cards.length === 0 && (
        <p className="text-sm">{t("none")}</p>
      )}
      {cards.length > 0 && (
        <ul aria-label={t("list")} className="flex flex-col gap-2">
          {cards.map((card, index) => (
            // The index keeps a card mounted through a swap, so the focus returns to its Swap.
            <li key={index}>
              <VariableCard
                card={card}
                isDraft={isDraftOf(draft, card)}
                onConfirm={() => confirm(card)}
                onSwap={(variable) => pick(variable, index)}
              />
            </li>
          ))}
        </ul>
      )}
      <CatalogPicker
        label={t("add")}
        isDisabled={cards.length >= MAX_CARDS}
        onPick={(variable) => pick(variable, cards.length)}
      />
      {draft !== null && <MetricEditor draft={draft} />}
    </div>
  );
}

/** The proposed variables, after the draft when the draft is none of them (a chip or a pick). */
function toCards(proposal: ParseProposal | null, draft: DraftSpec | null): Card[] {
  const proposed: Card[] = proposal?.variables ?? [];
  if (draft === null || proposed.some((card) => isDraftOf(draft, card))) {
    return proposed;
  }
  return [{ var: draft.var, metric_id: draft.metric.id, reason_code: null }, ...proposed].slice(
    0,
    MAX_CARDS,
  );
}

function isDraftOf(draft: DraftSpec | null, card: Card): boolean {
  return draft?.var === card.var && draft.metric.id === card.metric_id;
}
