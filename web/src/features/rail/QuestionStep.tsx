"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useId, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Chip, Lang, ParseProposal } from "@/contracts/types";
import { useParse } from "@/hooks/queries";
import { actions, useAppStore } from "@/state/store";

import { toChipQuestion, toDraft } from "./draft";
import { CHIPS, pickChips } from "./pick-chips";

// PRD "User flows": an empty window slot is the full record from 1981.
const RECORD_START_YEAR = 1981;

/** Step 1: a typed question for parse, or one of six example chips (FR-30). */
export function QuestionStep() {
  const t = useTranslations("rail.question");
  const lang = useLocale() as Lang;
  const fieldId = useId();
  const question = useAppStore((state) => state.question);
  const center = useAppStore((state) => state.mapView?.center ?? null);
  const [text, setText] = useState(question);
  // The demo and the guide set the question in the store after this field mounted.
  const [syncedQuestion, setSyncedQuestion] = useState(question);
  if (question !== syncedQuestion) {
    setSyncedQuestion(question);
    setText(question);
  }
  const parse = useParse();
  const chips = pickChips(CHIPS, center, new Date());

  useEffect(() => {
    // The mutation shows the answer of the latest question only, so an earlier
    // answer never lands after a later one.
    if (parse.data !== undefined) {
      applyProposal(parse.data);
    }
  }, [parse.data]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed === "") {
      return;
    }
    startQuestion(trimmed);
    parse.mutate(trimmed);
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <Label htmlFor={fieldId}>{t("label")}</Label>
        <Input
          id={fieldId}
          value={text}
          placeholder={t("placeholder")}
          onChange={(event) => setText(event.target.value)}
          className="min-h-11"
        />
        <Button type="submit" className="min-h-11 self-start">
          {t("submit")}
        </Button>
      </form>
      {parse.isPending && (
        <p role="status" className="text-sm text-muted-foreground">
          {t("pending")}
        </p>
      )}
      {parse.error && (
        <EmptyState
          messageKey={parse.error.code}
          onRetry={() => parse.mutate(question)}
        />
      )}
      <ul aria-label={t("chips")} className="flex flex-col gap-2">
        {chips.map((chip) => (
          <li key={chip.input_id}>
            <Button
              variant="outline"
              className="h-auto min-h-11 w-full justify-start text-left whitespace-normal"
              onClick={() => applyChip(chip, lang)}
            >
              {toChipQuestion(chip).text[lang]}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A new question drops the proposal and the draft of the one before. */
function startQuestion(text: string): void {
  actions.setQuestion(text);
  actions.setProposal(null);
  // A patch with no variable leaves no whole draft, so the store clears it.
  actions.editDraft({ var: undefined }, "user");
}

function applyProposal(proposal: ParseProposal): void {
  actions.setProposal(proposal);
  actions.setWindow(proposal.spec.window, "user");
  // ponytail: the first proposed variable fills the draft, so the read-back shows
  // with the cards (TDD Flow A step 5); no document says which card starts selected.
  const [first] = proposal.variables;
  if (first !== undefined) {
    actions.editDraft(toDraft(first, proposal.spec), "user");
  }
  actions.goToStep(2);
}

/** A chip fills the spec from the expected outcome of its catalog input, with no parse. */
function applyChip(chip: Chip, lang: Lang): void {
  const { text, draft, windowStart } = toChipQuestion(chip);
  startQuestion(text[lang]);
  actions.editDraft(draft, "user");
  actions.setWindow({ start: windowStart ?? RECORD_START_YEAR, end: "latest" }, "user");
  actions.goToStep(2);
}
