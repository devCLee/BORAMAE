"use client";

import { useLocale, useTranslations } from "next-intl";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { CatalogVariable, Lang } from "@/contracts/types";
import { useCatalog } from "@/hooks/queries";

interface CatalogPickerProps {
  /** The visible text of the trigger. */
  label: string;
  /** The accessible name of the trigger, when the label alone is not enough. */
  name?: string;
  /** The trigger stays focusable, so the focus can return to it after a pick. */
  isDisabled?: boolean;
  onPick: (variable: CatalogVariable) => void;
}

/**
 * The catalog of every variable in a dialog (FR-07, TR-F-005). The dialog returns
 * the focus to its trigger when it closes.
 */
export function CatalogPicker({
  label,
  name,
  isDisabled = false,
  onPick,
}: CatalogPickerProps) {
  const t = useTranslations("rail.picker");
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          className="min-h-11"
          aria-label={name}
          aria-disabled={isDisabled || undefined}
          onClick={(event) => {
            if (isDisabled) {
              event.preventDefault();
            }
          }}
        >
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <VariableList
          onPick={(variable) => {
            onPick(variable);
            setIsOpen(false);
          }}
        />
        <DialogClose asChild>
          <Button variant="outline" className="min-h-11">
            {t("close")}
          </Button>
        </DialogClose>
      </DialogContent>
    </Dialog>
  );
}

/** Mounts with the open dialog only, so a closed picker reads no catalog. */
function VariableList({ onPick }: Pick<CatalogPickerProps, "onPick">) {
  const lang = useLocale() as Lang;
  const idPrefix = useId();
  const { data: catalog } = useCatalog();

  return (
    <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
      {catalog?.variables.map((variable) => (
        <li key={variable.id} className="flex flex-col">
          <Button
            variant="ghost"
            className="min-h-11 justify-start"
            aria-describedby={`${idPrefix}-${variable.id}`}
            onClick={() => onPick(variable)}
          >
            {variable.name[lang]}
          </Button>
          <p
            id={`${idPrefix}-${variable.id}`}
            className="px-2.5 text-xs text-muted-foreground"
          >
            {variable.definition[lang]}
          </p>
        </li>
      ))}
    </ul>
  );
}
